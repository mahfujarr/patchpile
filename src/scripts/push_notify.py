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


def _parse_apps(text: str) -> list[str]:
    apps: list[str] = []
    seen = set()
    for line in text.splitlines():
        if "🟢" not in line:
            continue
        m = re.search(r"»\s*([^:(]+)", line)
        if not m:
            continue
        app_name = _clean_app_name(m.group(1).strip())
        if app_name and app_name not in seen:
            seen.add(app_name)
            apps.append(app_name)
    return apps


def _lookup_apps_from_manifest(target: str) -> list[str]:
    manifest_path = Path("assets/releases.json")
    if not manifest_path.exists():
        return []
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
            apps = _parse_apps(rel.get("body", ""))
            if not apps and rel.get("assets"):
                for a in rel["assets"]:
                    aname = a.get("name", "")
                    if aname.endswith(".apk"):
                        cleaned = _clean_app_name(aname.split("-")[0].capitalize())
                        if cleaned not in apps:
                            apps.append(cleaned)
            return apps
    except Exception as e:
        epr(f"Error inspecting manifest for app names: {e}")
    return []


def _format_app_list(names: list[str]) -> str:
    if not names:
        return "App"
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} & {names[1]}"
    return f"{names[0]}, {names[1]}"


def _build_payload(target: str, final_md: Path | None = None) -> dict:
    apps: list[str] = []

    # 1. Parse final_md if available
    if final_md and final_md.exists() and final_md.stat().st_size:
        apps = _parse_apps(final_md.read_text(encoding="utf-8"))

    # 2. Check releases.json for matching release
    if not apps:
        apps = _lookup_apps_from_manifest(target)

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
                apps = [n.strip() for n in known_app.split("&")]
            else:
                apps = [known_app]
        else:
            apps = [_clean_app_name(target)]

    primary_title_str = _format_app_list(apps)
    title = f"New {primary_title_str} Update"
    body = "Click to download."
    tag = (
        f"patchpile-{apps[0].lower().replace(' ', '-')}"
        if apps
        else "patchpile-update"
    )

    return {
        "title": title,
        "body": body,
        "icon": "./assets/favicon.svg",
        "badge": "./assets/favicon.svg",
        "tag": tag,
        "data": {
            "url": SITE_URL,
            "site_url": SITE_URL,
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
            # WNS (Edge/Windows) returns 401 for expired subscriptions instead of 404/410
            is_wns = "notify.windows.com" in endpoint
            if (
                status in (404, 410)
                or (status == 401 and is_wns)
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
