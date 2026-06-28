import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from src.core.config import CONFIG_PATH, AppEntry, load_toml, parse_app_entries, parse_config
from src.core.logger import IS_GITHUB, abort, epr
from src.core.network import NetworkManager, ResourceNotFoundError


def _require_ci(script: str) -> None:
    if not IS_GITHUB:
        abort(f"'{script}' is only available in GitHub Actions")


def _parse_dt(raw: str) -> datetime:
    return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)


def _fetch_latest_release(source: str, net: NetworkManager) -> tuple[str, str]:
    scheme, clean_src = source.split(":", 1)
    if scheme == "gitlab":
        project = clean_src.replace("/", "%2F")
        rel = json.loads(net.get(f"https://gitlab.com/api/v4/projects/{project}/releases/permalink/latest"))
        return rel.get("description", "") or "", rel.get("released_at", "") or ""

    rel = json.loads(net.get(f"https://api.github.com/repos/{clean_src}/releases/latest", headers=net._gh_headers))
    return rel.get("body", "") or "", rel.get("published_at", "") or ""


def _fetch_our_releases(repo: str, net: NetworkManager) -> tuple[dict[str, str], set[str]]:
    our_dates: dict[str, str] = {}
    compiled_versions: set[str] = set()
    try:
        raw = net.get(f"https://api.github.com/repos/{repo}/releases?per_page=100", headers=net._gh_headers)
        for rel in json.loads(raw):
            tag = rel.get("tag_name", "")
            brand = tag.rsplit("-", 1)[1] if "-" in tag else ""
            if brand and brand not in our_dates:
                our_dates[brand] = rel.get("published_at", "") or ""

            body = rel.get("body", "") or ""
            for ver in re.findall(r"🟢\s+[\w\-]+\s+\([^)]+\):\s*([^\s\n\r\[]+)", body):
                compiled_versions.add(ver.strip().lower())
    except Exception as exc:
        epr(f"Failed to fetch our releases: {exc}")
    return our_dates, compiled_versions


def _fetch_latest_app_version(entry: AppEntry, net: NetworkManager) -> str | None:
    from src.scrapers.apkmirror import APKMirrorScraper
    from src.scrapers.github import GitHubScraper
    from src.scrapers.uptodown import UptodownScraper
    from src.core.prebuilts import get_highest_ver

    scraper_map = {
        "apkmirror": APKMirrorScraper,
        "github": GitHubScraper,
        "uptodown": UptodownScraper,
    }

    for src, url in entry.dl_urls.items():
        cls = scraper_map.get(src)
        if not cls:
            continue
        try:
            metadata = cls(net).cached_metadata(url)
            if metadata.versions:
                return get_highest_ver(metadata.versions)
        except Exception as exc:
            epr(f"Could not fetch app version for '{entry.table}' from '{src}': {exc}")

    return None


def get_matrix(source: str) -> None:
    data = load_toml(CONFIG_PATH)
    main_cfg = parse_config(data)
    source_lower = source.lower()
    filter_changelog = os.getenv("FILTER_CHANGELOG", "false").lower() == "true"

    patches_source = ""
    has_changelog_keywords = False
    for entry in parse_app_entries(data, main_cfg):
        if entry.enabled and entry.brand.lower() == source_lower:
            patches_source = next(iter(entry.patches), "")
            if entry.changelog_keywords:
                has_changelog_keywords = True
                break

    changelog_text = ""
    if filter_changelog and has_changelog_keywords and patches_source:
        with NetworkManager() as net:
            repo = os.getenv("GITHUB_REPOSITORY")
            if repo:
                our_dates, _ = _fetch_our_releases(repo, net)
                if our_dates.get(source_lower):
                    try:
                        changelog_text, _ = _fetch_latest_release(patches_source, net)
                    except Exception as exc:
                        epr(f"Failed to fetch changelog for '{patches_source}': {exc}")

    include: list[dict[str, str]] = []
    for entry in parse_app_entries(data, main_cfg):
        if not entry.enabled or entry.brand.lower() != source_lower:
            continue

        if filter_changelog and entry.changelog_keywords and changelog_text and not any(kw in changelog_text.lower() for kw in entry.changelog_keywords):
            continue

        if entry.arch == "both":
            include.extend([
                {"id": entry.table, "arch": "arm64-v8a"},
                {"id": entry.table, "arch": "armeabi-v7a"},
            ])
        else:
            include.append({"id": entry.table, "arch": entry.arch or "arm64-v8a"})

    if not include:
        abort(f"No apps found for patch source '{source}'")

    print(json.dumps({"include": include}, ensure_ascii=False))


def check_builds_needed(force_all: bool = False) -> None:
    data = load_toml(CONFIG_PATH)
    main_cfg = parse_config(data)

    seen: dict[str, str] = {}
    for entry in parse_app_entries(data, main_cfg):
        if entry.enabled and entry.brand.lower() not in seen:
            seen[entry.brand.lower()] = next(iter(entry.patches), "")

    if not seen:
        print(json.dumps([]))
        return

    if force_all:
        print(json.dumps(list(seen.keys())))
        return

    repo = os.getenv("GITHUB_REPOSITORY")
    if not repo:
        abort("GITHUB_REPOSITORY environment variable is not set")

    with NetworkManager() as net:
        our_dates, compiled_versions = _fetch_our_releases(repo, net)
        brands_to_build: set[str] = set()

        for brand, patches_source in seen.items():
            our_date = our_dates.get(brand, "")

            if not our_date:
                brands_to_build.add(brand)
                continue

            changelog_text = ""
            upstream_date = ""
            try:
                changelog_text, upstream_date = _fetch_latest_release(patches_source, net)
            except ResourceNotFoundError:
                epr(f"No upstream release found for '{patches_source}', skipping brand '{brand}'")
                continue
            except Exception as exc:
                epr(f"Failed to fetch upstream release for '{patches_source}': {exc}")
                brands_to_build.add(brand)
                continue

            if upstream_date and _parse_dt(upstream_date) > _parse_dt(our_date):
                has_apps = any(
                    app.enabled and app.brand.lower() == brand
                    and (not app.changelog_keywords or any(kw in changelog_text.lower() for kw in app.changelog_keywords))
                    for app in parse_app_entries(data, main_cfg)
                )
                if has_apps:
                    print(f"::notice::🔄 Patch update detected for brand '{brand}'.", file=sys.stderr)
                    brands_to_build.add(brand)
                continue

            for app in parse_app_entries(data, main_cfg):
                if not app.enabled or app.brand.lower() != brand:
                    continue
                latest_ver = _fetch_latest_app_version(app, net)
                if not latest_ver:
                    continue
                if latest_ver.lower() not in compiled_versions:
                    print(f"::notice::🔄 New app version '{latest_ver}' detected for '{app.table}'.", file=sys.stderr)
                    brands_to_build.add(brand)
                    break
                print(f"::notice::✅ '{app.table}' version '{latest_ver}' already compiled. Skipping.", file=sys.stderr)

    print(json.dumps(list(brands_to_build)))


def main() -> None:
    _require_ci("matrix.py")
    match sys.argv[1:]:
        case ["check-builds"]:
            check_builds_needed()
        case ["check-builds-force"]:
            check_builds_needed(force_all=True)
        case ["get-matrix", source]:
            get_matrix(source)
        case _:
            abort("Usage: matrix.py get-matrix <source> | check-builds | check-builds-force")


if __name__ == "__main__":
    main()