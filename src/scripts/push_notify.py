# ---------------------------------------------------------
# Patchpile Web Push Notifications Dispatcher
# Broadcasts instant push notifications to registered devices
# upon a successful GitHub Actions build release.
# ---------------------------------------------------------

# pyright: reportMissingImports=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

from curl_cffi import requests as curl_requests

from src.core.logger import abort, epr, pr

DEFAULT_SUPABASE_URL = "https://anikploodichlpgfymiq.supabase.co"
DEFAULT_SUPABASE_KEY = "sb_publishable_r6Q5fgqVFu9TkH21jtmGjw_9MRXOYz8"
DEFAULT_VAPID_PUBLIC_KEY = "BKHQ6jfcI8aUOUHR10SH2DmKDTEz9kX9thkdzR-8ZEY462f8LMutAfe9XLcxMnFye4rCS1tZ0i3Gnx1oNy-tjmE"
DEFAULT_VAPID_PRIVATE_KEY = "qUNcnHcAYe7H80Kdr-yh68e3dIFABfv-PUV0MfIINMQ"
DEFAULT_CLAIMS_EMAIL = "mailto:mahfu63@gmail.com"
DEFAULT_STALE_DAYS = 30
DEFAULT_PUSH_TTL = 43200  # 12 hours
SITE_URL = "https://mahfujarr.github.io/patchpile/"


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
    seen: set[str] = set()
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


def _build_payload(target: str, final_md: Path | None = None) -> dict[str, Any]:
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
            "morphe": "YouTube Stable & YT Music Stable",
            "morphe-dev": "YT Music Experimental & YouTube Experimental",
            "gphotos": "Google Photos",
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
        f"patchpile-{apps[0].lower().replace(' ', '-')}" if apps else "patchpile-update"
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


def fetch_subscriptions(
    supabase_url: str, supabase_key: str
) -> list[dict[str, Any]] | None:
    url = f"{supabase_url.rstrip('/')}/rest/v1/push_subscriptions?select=id,endpoint,p256dh,auth,user_agent,updated_at"
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
            raw_json: Any = resp.json()
            return raw_json if isinstance(raw_json, list) else None
        except Exception as e:
            epr(f"Failed to parse Supabase JSON: {e}")
            return None


def delete_subscription(supabase_url: str, supabase_key: str, endpoint: str) -> bool:
    url = f"{supabase_url.rstrip('/')}/rest/v1/push_subscriptions?endpoint=eq.{quote(endpoint, safe='')}"
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Prefer": "return=representation",
    }
    try:
        with curl_requests.Session() as session:
            resp = session.delete(url, headers=headers, timeout=(5, 10))
            if resp.status_code in (200, 204):
                try:
                    deleted = resp.json()
                    if isinstance(deleted, list) and len(deleted) == 0:
                        epr(
                            "Warning: Supabase returned 0 deleted rows (check if SUPABASE_SERVICE_ROLE_KEY is set in GitHub Secrets or if RLS policy allows DELETE)."
                        )
                        return False
                except Exception:
                    pass
                return True
            else:
                epr(f"Supabase delete failed ({resp.status_code}): {resp.text}")
                return False
    except Exception as e:
        epr(f"Error deleting subscription from Supabase: {e}")
        return False


def _is_stale(sub: dict[str, Any], max_days: int = DEFAULT_STALE_DAYS) -> bool:
    updated_at_str = sub.get("updated_at")
    if not updated_at_str:
        return False
    try:
        clean_iso = updated_at_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        age_days = (now - dt).total_seconds() / 86400
        return age_days > max_days
    except Exception:
        return False


def list_subscribers() -> None:
    supabase_url = os.getenv("SUPABASE_URL", DEFAULT_SUPABASE_URL)
    supabase_key = os.getenv("SUPABASE_KEY", DEFAULT_SUPABASE_KEY)
    subs = fetch_subscriptions(supabase_url, supabase_key)
    if subs is None:
        epr("Failed to load subscribers from Supabase.")
        return
    if not subs:
        pr("No subscriptions found in Supabase.")
        return

    pr(f"\n--- Supabase Push Subscriptions ({len(subs)} total) ---")
    now = datetime.now(timezone.utc)
    for i, s in enumerate(subs, 1):
        sub_id = s.get("id", "N/A")
        ua = s.get("user_agent") or "Unknown"
        updated_str = s.get("updated_at") or "Unknown"
        age_str = ""
        is_stale = False
        if updated_str != "Unknown":
            try:
                dt = datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                days = int((now - dt).total_seconds() // 86400)
                age_str = f" ({days}d ago)"
                is_stale = days > DEFAULT_STALE_DAYS
            except Exception:
                pass
        stale_tag = " [STALE]" if is_stale else " [ACTIVE]"
        ep = s.get("endpoint", "")
        pr(f"[{i}]{stale_tag} ID: {sub_id} | Updated: {updated_str}{age_str}")
        pr(f"    UA: {ua}")
        pr(f"    Endpoint: {ep[:60]}...")
    pr("----------------------------------------------------\n")


def prune_subscribers(max_days: int = DEFAULT_STALE_DAYS, force: bool = False) -> None:
    supabase_url = os.getenv("SUPABASE_URL", DEFAULT_SUPABASE_URL)
    supabase_key = os.getenv("SUPABASE_KEY", DEFAULT_SUPABASE_KEY)

    if supabase_key == DEFAULT_SUPABASE_KEY:
        pr("ℹ Note: Using default publishable key. To bypass RLS, provide SUPABASE_KEY=<secret_key>.")

    subs = fetch_subscriptions(supabase_url, supabase_key)
    if subs is None:
        epr("Failed to load subscribers from Supabase.")
        return
    if not subs:
        pr("No subscriptions found in Supabase.")
        return

    to_prune = [s for s in subs if _is_stale(s, max_days=max_days)]
    if not to_prune:
        pr(
            f"No stale subscriptions found older than {max_days} days (out of {len(subs)} total)."
        )
        return

    pr(f"\nFound {len(to_prune)} stale subscription(s) older than {max_days} days:")
    for s in to_prune:
        ua = s.get("user_agent", "unknown")[:60]
        pr(f"  • {ua} (Last active: {s.get('updated_at', 'unknown')})")

    if sys.stdin.isatty() and not force:
        try:
            confirm = (
                input(f"\nDelete these {len(to_prune)} subscriptions from Supabase? [y/N]: ")
                .strip()
                .lower()
            )
            if confirm not in ("y", "yes"):
                pr("Aborted. No subscriptions were deleted.")
                return
        except (KeyboardInterrupt, EOFError):
            pr("\nAborted.")
            return

    pr(f"\nDeleting {len(to_prune)} subscription(s)...")
    pruned = 0
    for s in to_prune:
        ep = s.get("endpoint", "")
        ua = s.get("user_agent", "unknown")[:40]
        if ep:
            pr(f"Deleting [{ua}]: {ep[:50]}...")
            if delete_subscription(supabase_url, supabase_key, ep):
                pruned += 1

    pr(f"Prune finished: {pruned}/{len(to_prune)} successfully deleted.")


def notify(brand: str, final_md_path: str = "final.md") -> None:
    try:
        import pywebpush
    except ImportError:
        abort(
            "pywebpush is required to send push notifications. Run with: uv run --with pywebpush ..."
        )

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

    # Automatically identify and prune stale subscriptions (e.g. uninstalled browsers > 30 days old)
    active_subs: list[dict[str, Any]] = []
    stale_subs: list[dict[str, Any]] = []
    for sub in subscriptions:
        if _is_stale(sub, max_days=DEFAULT_STALE_DAYS):
            stale_subs.append(sub)
        else:
            active_subs.append(sub)

    if stale_subs:
        pr(
            f"Found {len(stale_subs)} stale subscription(s) inactive for >{DEFAULT_STALE_DAYS} days. Auto-pruning..."
        )
        for sub in stale_subs:
            ep = sub.get("endpoint", "")
            ua = sub.get("user_agent", "unknown")[:35]
            if ep:
                pr(f"Auto-pruning stale device [{ua}]: {ep[:45]}...")
                delete_subscription(supabase_url, supabase_key, ep)

    if not active_subs:
        pr("No active subscriptions remaining to notify.")
        return

    pr(f"Found {len(active_subs)} active subscriber(s). Broadcasting Web Push...")
    success = 0
    expired = 0
    failed = 0

    for sub in active_subs:
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
            # Pass fresh claims copy per subscriber: pywebpush mutates the dictionary in-place
            # by adding 'aud' and 'exp', which breaks subsequent subscribers from other providers (e.g. Mozilla vs Google FCM)
            claims = {"sub": vapid_email}
            resp = pywebpush.webpush(
                subscription_info=sub_info,
                data=payload_str,
                vapid_private_key=vapid_private_key,
                vapid_claims=claims,
                timeout=8,
                ttl=DEFAULT_PUSH_TTL,
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
        case ["list"]:
            list_subscribers()
        case ["prune"]:
            prune_subscribers()
        case ["prune", "-y" | "--yes" | "--force"]:
            prune_subscribers(force=True)
        case ["prune", days]:
            try:
                prune_subscribers(int(days))
            except ValueError:
                abort("Error: days must be an integer.")
        case ["prune", days, "-y" | "--yes" | "--force"]:
            try:
                prune_subscribers(int(days), force=True)
            except ValueError:
                abort("Error: days must be an integer.")
        case _:
            abort(
                "Usage: push_notify.py notify <brand> [final_md_path] | list | prune [days] [-y]"
            )


if __name__ == "__main__":
    main()
