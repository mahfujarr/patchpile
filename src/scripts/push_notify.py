# ---------------------------------------------------------
# Patchpile Web Push Notifications Dispatcher
# Broadcasts instant push notifications to registered devices
# upon a successful GitHub Actions build release.
# ---------------------------------------------------------

import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import quote

from curl_cffi import requests as curl_requests
import pywebpush

from src.core.logger import abort, epr, pr

_BACKTICK_RE = re.compile(r"`([^`]+)`")

DEFAULT_SUPABASE_URL = "https://anikploodichlpgfymiq.supabase.co"
DEFAULT_SUPABASE_KEY = "sb_publishable_r6Q5fgqVFu9TkH21jtmGjw_9MRXOYz8"
DEFAULT_VAPID_PUBLIC_KEY = "BKHQ6jfcI8aUOUHR10SH2DmKDTEz9kX9thkdzR-8ZEY462f8LMutAfe9XLcxMnFye4rCS1tZ0i3Gnx1oNy-tjmE"
DEFAULT_VAPID_PRIVATE_KEY = "qUNcnHcAYe7H80Kdr-yh68e3dIFABfv-PUV0MfIINMQ"
DEFAULT_CLAIMS_EMAIL = "mailto:admin@patchpile.app"
SITE_URL = "https://mahfujarr.me/patchpile/"


def _clean_app_name(raw: str) -> str:
    cleaned = raw.strip()
    # Normalize abbreviations and hyphenation while preserving tags like Experimental / Stable
    cleaned = cleaned.replace("YT-Music", "YT Music").replace(
        "Google-Photos", "Google Photos"
    )
    if cleaned.startswith("GPhotos"):
        cleaned = cleaned.replace("GPhotos", "Google Photos", 1)
    return cleaned


def _parse_apps(text: str) -> list[dict]:
    apps: list[dict] = []
    seen = set()
    for line in text.splitlines():
        if "🟢" not in line:
            continue
        m = re.search(
            r"»\s*([^:(]+)(?:\s*\(([^)]+)\))?(?::\s*\[`?([^`\]]+)`?\](?:\((https?://[^\s)]+)\))?)?",
            line,
        )
        if not m:
            continue
        raw_name = m.group(1).strip()
        app_name = _clean_app_name(raw_name)
        ver = m.group(3).replace("`", "").strip() if m.group(3) else ""
        dl_url = m.group(4).strip() if m.group(4) else ""
        if app_name not in seen:
            seen.add(app_name)
            apps.append({"name": app_name, "version": ver, "dl_url": dl_url})
    return apps


def _parse_patch_version(text: str) -> str:
    """Extract patch version from '» Patches: `owner/patches-1.6.0.mpp`' lines."""
    for line in text.splitlines():
        if "» Patches:" not in line:
            continue
        m = re.search(r"patches[- _](\d+\.\d+(?:\.\d+)*)", line, re.IGNORECASE)
        if m:
            return m.group(1)
    return ""


def _lookup_apps_from_manifest(target: str) -> tuple[list[dict], str]:
    manifest_path = Path("assets/releases.json")
    if not manifest_path.exists():
        return [], ""
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        all_releases = [
            r for sublist in data.get("repos", {}).values() for r in sublist
        ]
        norm = target.lower().strip()
        matching = [
            r
            for r in all_releases
            if r.get("tag_name", "").lower().endswith(f"-{norm}")
        ]
        if not matching:
            matching = [
                r for r in all_releases if norm in r.get("tag_name", "").lower()
            ]
        if matching:
            matching.sort(
                key=lambda r: r.get("published_at") or r.get("created_at") or "",
                reverse=True,
            )
            rel = matching[0]
            tag = rel.get("tag_name", "")
            body = rel.get("body", "")
            apps = _parse_apps(body)

            # Match any missing dl_url from assets
            assets = rel.get("assets", [])
            for app in apps:
                if not app.get("dl_url"):
                    for a in assets:
                        aname = a.get("name", "").lower()
                        n_clean = app["name"].lower().replace(" ", "-")
                        if n_clean in aname and aname.endswith(".apk"):
                            app["dl_url"] = a.get("browser_download_url", "")
                            break

            if not apps and assets:
                for a in assets:
                    aname = a.get("name", "")
                    if aname.endswith(".apk"):
                        app_name = _clean_app_name(aname.split("-")[0].capitalize())
                        apps.append(
                            {
                                "name": app_name,
                                "version": "",
                                "dl_url": a.get("browser_download_url", ""),
                            }
                        )

            return apps, tag
    except Exception as e:
        epr(f"Error inspecting manifest for app names: {e}")
    return [], ""


def _format_app_list(names: list[str]) -> str:
    if not names:
        return "App"
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} & {names[1]}"
    return f"{names[0]}, {names[1]}"


def _build_payload(target: str, final_md: Path | None = None) -> dict:
    apps: list[dict] = []
    tag_name = ""
    patch_ver = ""

    # 1. Parse final_md if available
    if final_md and final_md.exists() and final_md.stat().st_size:
        final_text = final_md.read_text(encoding="utf-8")
        apps = _parse_apps(final_text)
        patch_ver = _parse_patch_version(final_text)

    # 2. Check releases.json for matching release and tag
    manifest_apps, manifest_tag = _lookup_apps_from_manifest(target)
    if not tag_name:
        tag_name = manifest_tag
    if not apps:
        apps = manifest_apps
    else:
        # Fill in any missing dl_urls from manifest
        for app in apps:
            if not app.get("dl_url"):
                for m_app in manifest_apps:
                    if m_app["name"].lower() == app["name"].lower() and m_app.get(
                        "dl_url"
                    ):
                        app["dl_url"] = m_app["dl_url"]
                        break

    # 3. Fallback mapping if still no apps
    if not apps:
        norm = target.lower().strip()
        brand_map = {
            "piko": "Instagram",
            "piko-dev": "Instagram Experimental",
            "morphe": "YouTube Stable & YT Music Stable",
            "morphe-dev": "YT Music Experimental & YouTube Experimental",
            "devanced": "Google Photos",
            "de-vanced": "Google Photos",
            "rushi": "Google Photos",
            "hoo-dles": "YouTube",
            "hooman": "YouTube",
            "paresh": "YouTube",
            "tiktok": "TikTok",
        }
        known_app = brand_map.get(norm)
        if known_app:
            if "&" in known_app:
                apps = [
                    {"name": n.strip(), "version": "", "dl_url": ""}
                    for n in known_app.split("&")
                ]
            else:
                apps = [{"name": known_app, "version": "", "dl_url": ""}]
        else:
            apps = [{"name": _clean_app_name(target), "version": "", "dl_url": ""}]

    app_names = [a["name"] for a in apps if a.get("name")]
    primary_title_str = _format_app_list(app_names)
    title = f"New {primary_title_str} Update"

    # Format body: single app uses patch version, multi-app uses app list
    if len(apps) == 1:
        name = apps[0]["name"]
        if patch_ver:
            body = f"{name} patched to v{patch_ver} is ready for download."
        elif apps[0].get("version"):
            body = f"{name} (v{apps[0]['version']}) is ready for download."
        else:
            body = f"New {name} build is ready for download."
    elif len(apps) > 1:
        if patch_ver:
            body = f"Patched with {target} v{patch_ver}, ready for download."
        else:
            body = f"Patched with {target}, ready for download."
    else:
        body = "New patched APKs are ready for download."

    tag = (
        f"patchpile-{app_names[0].lower().replace(' ', '-')}"
        if app_names
        else "patchpile-update"
    )

    dl_apps = [a for a in apps if a.get("dl_url")]
    direct_url = dl_apps[0]["dl_url"] if len(dl_apps) == 1 else ""

    # Build click URL:
    # - Single app with known URL → direct APK link (browser downloads immediately)
    # - Multi-app with known URLs → site with ?dl=url1&dl=url2 (site fast-path downloads all)
    # - Fallback → site with ?autodownload=tag
    if direct_url:
        click_url = direct_url
    elif len(dl_apps) >= 2:
        dl_params = "&".join(f"dl={quote(a['dl_url'], safe='')}" for a in dl_apps)
        click_url = f"{SITE_URL}?{dl_params}"
    else:
        autodl_tag = tag_name or target
        click_url = f"{SITE_URL}?autodownload={quote(autodl_tag, safe='')}"

    return {
        "title": title,
        "body": body,
        "icon": "./assets/favicon.svg",
        "badge": "./assets/favicon.svg",
        "tag": tag,
        "data": {
            "url": click_url,
            "site_url": SITE_URL,
            "direct_url": direct_url,
            "download_urls": [a["dl_url"] for a in dl_apps],
            "apps": [{"name": a["name"], "dl_url": a.get("dl_url", "")} for a in apps],
        },
    }


def fetch_subscriptions(supabase_url: str, supabase_key: str) -> list[dict] | None:
    url = f"{supabase_url.rstrip('/')}/rest/v1/push_subscriptions?select=id,endpoint,p256dh,auth"
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
    }
    with curl_requests.Session() as session:
        resp = session.get(url, headers=headers, timeout=(5, 10))
        if resp.status_code != 200:
            epr(
                f"Failed to fetch subscriptions from Supabase ({resp.status_code}): {resp.text}"
            )
            return None
        try:
            return resp.json()
        except Exception as e:
            epr(f"Failed to parse Supabase JSON: {e}")
            return None


def delete_subscription(supabase_url: str, supabase_key: str, endpoint: str) -> None:
    url = f"{supabase_url.rstrip('/')}/rest/v1/push_subscriptions?endpoint=eq.{quote(endpoint, safe='')}"
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
    }
    with curl_requests.Session() as session:
        session.delete(url, headers=headers, timeout=(5, 10))


def notify(brand: str, final_md_path: str = "final.md") -> None:
    vapid_private_key = os.getenv("VAPID_PRIVATE_KEY", DEFAULT_VAPID_PRIVATE_KEY)
    if not vapid_private_key:
        epr("VAPID_PRIVATE_KEY not set in secrets, skipping Web Push notification")
        return

    supabase_url = os.getenv("SUPABASE_URL", DEFAULT_SUPABASE_URL)
    supabase_key = os.getenv("SUPABASE_KEY", DEFAULT_SUPABASE_KEY)
    vapid_email = os.getenv("VAPID_CLAIMS_EMAIL", DEFAULT_CLAIMS_EMAIL)

    path = Path(final_md_path)
    payload = _build_payload(brand, final_md=path)
    payload_str = json.dumps(payload)
    pr(f"Notification: '{payload['title']}' — '{payload['body']}'")

    pr("Fetching push subscribers from Supabase...")
    subscriptions = fetch_subscriptions(supabase_url, supabase_key)
    if subscriptions is None:
        epr("Failed to load subscribers from Supabase.")
        return
    if not subscriptions:
        pr("Supabase connected successfully, but 0 devices have subscribed yet.")
        pr(
            "👉 Visit the website and click the notification bell to register your device first."
        )
        return

    pr(f"Found {len(subscriptions)} subscriber(s). Broadcasting Web Push...")
    success = 0
    expired = 0
    failed = 0

    claims = {"sub": vapid_email}

    for sub in subscriptions:
        endpoint = sub.get("endpoint")
        p256dh = sub.get("p256dh")
        auth = sub.get("auth")
        if not endpoint or not p256dh or not auth:
            continue

        sub_info = {
            "endpoint": endpoint,
            "keys": {
                "p256dh": p256dh,
                "auth": auth,
            },
        }

        try:
            resp = pywebpush.webpush(
                subscription_info=sub_info,
                data=payload_str,
                vapid_private_key=vapid_private_key,
                vapid_claims=claims,
                timeout=8,
                ttl=86400,
            )
            status_code = getattr(resp, "status_code", 201)
            if status_code in (200, 201, 204):
                success += 1
            elif status_code in (404, 410):
                pr(f"Pruning expired subscription ({status_code}): {endpoint[:45]}...")
                delete_subscription(supabase_url, supabase_key, endpoint)
                expired += 1
            else:
                epr(f"Web push error {status_code} for {endpoint[:45]}...")
                failed += 1
        except pywebpush.WebPushException as ex:
            status = (
                getattr(ex.response, "status_code", None)
                if ex.response is not None
                else None
            )
            text = getattr(ex.response, "text", "") if ex.response is not None else ""
            if (
                status in (404, 410)
                or "NotRegistered" in text
                or "InvalidRegistration" in text
            ):
                pr(
                    f"Pruning dead/uninstalled subscription ({status or 'expired'}): {endpoint[:45]}..."
                )
                delete_subscription(supabase_url, supabase_key, endpoint)
                expired += 1
            else:
                epr(f"WebPushException for {endpoint[:45]}: {ex}")
                failed += 1
        except Exception as e:
            epr(f"Failed to send to {endpoint[:45]}: {e}")
            failed += 1

    pr(
        f"Web Push broadcast finished: {success} sent, {expired} pruned, {failed} failed."
    )


def main() -> None:
    match sys.argv[1:]:
        case ["notify", brand]:
            notify(brand)
        case ["notify", brand, final_md]:
            notify(brand, final_md)
        case _:
            abort("Usage: push_notify.py notify <brand> [final_md_path]")


if __name__ == "__main__":
    main()
