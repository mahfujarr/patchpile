import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from src.core.logger import IS_GITHUB, abort, epr, pr, wpr

APK_PATTERN = re.compile(
    r"^(?P<base>.+?)-v(?P<ver>\d.*?)-(?P<arch>arm64-v8a|armeabi-v7a|[a-zA-Z0-9_]+)\.apk$"
)


def _require_ci(script: str) -> None:
    if not IS_GITHUB:
        abort(f"'{script}' is only available in GitHub Actions")


def parse_apk_name(filename: str) -> dict[str, str] | None:
    match = APK_PATTERN.match(filename)
    if not match:
        return None
    return match.groupdict()


def get_release_assets(tag: str, repo: str | None = None) -> list[dict[str, Any]]:
    target_repo = repo or os.getenv("GITHUB_REPOSITORY")
    if not target_repo:
        epr("GITHUB_REPOSITORY is not set")
        return []

    # 1. Try gh CLI if installed
    if shutil.which("gh"):
        cmd = ["gh", "release", "view", tag, "--repo", target_repo, "--json", "assets"]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)
            if isinstance(data, dict) and "assets" in data and isinstance(data["assets"], list):
                return data["assets"]
        except (subprocess.CalledProcessError, json.JSONDecodeError) as exc:
            wpr(f"gh release view failed for tag '{tag}': {exc}")

    # 2. Fallback to GitHub REST API
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN") or ""
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "patchpile-release-assets",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    url = f"https://api.github.com/repos/{target_repo}/releases/tags/{tag}"
    req = Request(url, headers=headers)
    try:
        with urlopen(req) as resp:
            data = json.load(resp)
            if isinstance(data, dict) and "assets" in data and isinstance(data["assets"], list):
                return data["assets"]
    except (HTTPError, json.JSONDecodeError) as exc:
        epr(f"Failed to fetch release assets for '{tag}' via REST API: {exc}")

    return []


def delete_release_asset(asset: dict[str, Any], tag: str, repo: str | None = None) -> bool:
    target_repo = repo or os.getenv("GITHUB_REPOSITORY")
    asset_name = str(asset.get("name") or "")
    asset_api_url = str(asset.get("apiUrl") or asset.get("url") or "")
    asset_id = asset.get("id")

    # 1. gh api -X DELETE <apiUrl>
    if shutil.which("gh") and asset_api_url:
        try:
            subprocess.run(
                ["gh", "api", "-X", "DELETE", asset_api_url],
                capture_output=True,
                text=True,
                check=True,
            )
            pr(f"Deleted asset '{asset_name}' via gh api")
            return True
        except subprocess.CalledProcessError as exc:
            wpr(f"gh api DELETE failed for '{asset_name}': {exc.stderr.strip() if exc.stderr else exc}")

    # 2. gh release delete-asset
    if shutil.which("gh") and target_repo and asset_name:
        try:
            subprocess.run(
                ["gh", "release", "delete-asset", tag, asset_name, "--yes", "--repo", target_repo],
                capture_output=True,
                text=True,
                check=True,
            )
            pr(f"Deleted asset '{asset_name}' via gh release delete-asset")
            return True
        except subprocess.CalledProcessError as exc:
            wpr(f"gh release delete-asset failed for '{asset_name}': {exc.stderr.strip() if exc.stderr else exc}")

    # 3. Direct REST API DELETE
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN") or ""
    del_url = asset_api_url
    if not del_url and target_repo and asset_id:
        del_url = f"https://api.github.com/repos/{target_repo}/releases/assets/{asset_id}"

    if del_url and token:
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "patchpile-release-assets",
        }
        req = Request(del_url, headers=headers, method="DELETE")
        try:
            with urlopen(req) as resp:
                if resp.status in (200, 204):
                    pr(f"Deleted asset '{asset_name}' via REST API")
                    return True
        except HTTPError as exc:
            epr(f"HTTP DELETE failed for '{asset_name}': {exc}")

    return False


def replace_previous_assets(tag: str, apks: list[str | Path], repo: str | None = None) -> list[str]:
    new_apks_by_app: dict[tuple[str, str], str] = {}
    for item in apks:
        p = Path(item)
        if not p.name.endswith(".apk"):
            continue
        parsed = parse_apk_name(p.name)
        if parsed:
            key = (parsed["base"], parsed["arch"])
            new_apks_by_app[key] = p.name

    if not new_apks_by_app:
        pr("No valid APKs provided to replace_previous_assets")
        return []

    assets = get_release_assets(tag, repo)
    if not assets:
        pr(f"No existing assets found in release '{tag}'")
        return []

    deleted: list[str] = []
    for a in assets:
        name = str(a.get("name") or "")
        if not name.endswith(".apk"):
            continue
        parsed = parse_apk_name(name)
        if not parsed:
            continue
        key = (parsed["base"], parsed["arch"])
        if key in new_apks_by_app:
            new_filename = new_apks_by_app[key]
            if name != new_filename:
                pr(f"Found outdated asset '{name}' for '{key[0]}' ({key[1]}), replacing with '{new_filename}'")
                if delete_release_asset(a, tag, repo):
                    deleted.append(name)
                else:
                    epr(f"Failed to delete outdated asset '{name}'")

    return deleted


def prune_release(tag: str, repo: str | None = None) -> list[str]:
    assets = get_release_assets(tag, repo)
    if not assets:
        return []

    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for a in assets:
        name = str(a.get("name") or "")
        if not name.endswith(".apk"):
            continue
        parsed = parse_apk_name(name)
        if not parsed:
            continue
        key = (parsed["base"], parsed["arch"])
        groups.setdefault(key, []).append(a)

    deleted: list[str] = []
    for (base, arch), items in groups.items():
        if len(items) <= 1:
            continue
        # Multiple versions of the same app and arch exist in the release!
        items.sort(
            key=lambda x: str(x.get("updated_at") or x.get("created_at") or ""),
            reverse=True,
        )
        keep = items[0]
        pr(f"Duplicate APKs detected for '{base}' ({arch}). Keeping newest: '{keep.get('name')}'")
        for old in items[1:]:
            old_name = str(old.get("name") or "")
            pr(f"Pruning older version '{old_name}'")
            if delete_release_asset(old, tag, repo):
                deleted.append(old_name)
            else:
                epr(f"Failed to prune older asset '{old_name}'")

    return deleted


def main() -> None:
    _require_ci("release_assets.py")
    match sys.argv[1:]:
        case ["replace-assets", tag, *apks]:
            replace_previous_assets(tag, apks)
        case ["prune-release", tag]:
            prune_release(tag)
        case _:
            abort("Usage: release_assets.py replace-assets <tag> <apk...> | prune-release <tag>")


if __name__ == "__main__":
    main()

