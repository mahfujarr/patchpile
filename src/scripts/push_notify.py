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
DEFAULT_VAPID_PUBLIC_KEY = (
    "BKHQ6jfcI8aUOUHR10SH2DmKDTEz9kX9thkdzR-8ZEY462f8LMutAfe9XLcxMnFye4rCS1tZ0i3Gnx1oNy-tjmE"
)
DEFAULT_VAPID_PRIVATE_KEY = "qUNcnHcAYe7H80Kdr-yh68e3dIFABfv-PUV0MfIINMQ"
DEFAULT_CLAIMS_EMAIL = "mailto:admin@patchpile.app"
SITE_URL = "https://mahfujarr.me/patchpile/"


def _parse_final_md(final_md: Path) -> list[str]:
    green_lines: list[str] = []
    if not final_md.exists() or not final_md.stat().st_size:
        return green_lines
    for line in final_md.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("- 🟢"):
            cleaned = _BACKTICK_RE.sub(r"\1", stripped.removeprefix("- "))
            green_lines.append(cleaned)
    return green_lines


def _build_payload(brand: str, green_lines: list[str]) -> dict:
    app_names = []
    for line in green_lines:
        m = re.search(r"»\s*([^:(]+)", line)
        if m:
            app_names.append(m.group(1).strip())

    if app_names:
        body = f"Updated: {', '.join(app_names)}. Tap to download."
    else:
        body = f"New {brand.capitalize()} patched APKs are ready for download!"

    title = f"Patchpile: New {brand.capitalize()} Build!"
    return {
        "title": title,
        "body": body,
        "icon": "./assets/favicon.svg",
        "badge": "./assets/favicon.svg",
        "tag": f"patchpile-{brand.lower()}",
        "data": {
            "url": SITE_URL,
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
            epr(f"Failed to fetch subscriptions from Supabase ({resp.status_code}): {resp.text}")
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
    green_lines = _parse_final_md(path) if path.exists() else []
    payload = _build_payload(brand, green_lines)
    payload_str = json.dumps(payload)

    pr("Fetching push subscribers from Supabase...")
    subscriptions = fetch_subscriptions(supabase_url, supabase_key)
    if subscriptions is None:
        epr("Failed to load subscribers from Supabase.")
        return
    if not subscriptions:
        pr("Supabase connected successfully, but 0 devices have subscribed yet.")
        pr("👉 Visit the website and click the notification bell to register your device first.")
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
            if ex.response is not None and ex.response.status_code in (404, 410):
                pr(f"Pruning expired subscription: {endpoint[:45]}...")
                delete_subscription(supabase_url, supabase_key, endpoint)
                expired += 1
            else:
                epr(f"WebPushException for {endpoint[:45]}: {ex}")
                failed += 1
        except Exception as e:
            epr(f"Failed to send to {endpoint[:45]}: {e}")
            failed += 1

    pr(f"Web Push broadcast finished: {success} sent, {expired} pruned, {failed} failed.")


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

