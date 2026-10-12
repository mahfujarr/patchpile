import argparse
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

CHANGELOG_URL = re.compile(
    r"https://github\.com/([^/\s]+/[^/\s]+)/releases/tag/([^\s)]+)"
)


def fetch_json(url: str, token: str) -> Any:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "patchpile-manifest",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, headers=headers)
    with urlopen(request) as response:
        return json.load(response)


_upstream_cache: dict[tuple[str, str], dict[str, str] | None] = {}


def upstream_release(release: dict[str, Any], token: str) -> dict[str, str] | None:
    body = str(release.get("body") or "")
    match = CHANGELOG_URL.search(body)
    if not match:
        return None

    repo, tag = match.groups()
    key = (repo, tag)
    if key in _upstream_cache:
        return _upstream_cache[key]

    url = f"https://api.github.com/repos/{repo}/releases/tags/{quote(tag, safe='')}"
    try:
        data: Any = fetch_json(url, token)
    except HTTPError:
        _upstream_cache[key] = None
        return None
    if not isinstance(data, dict):
        _upstream_cache[key] = None
        return None

    data_dict = cast(dict[str, Any], data)
    res = {
        "tag_name": str(data_dict.get("tag_name") or tag),
        "body": str(data_dict.get("body") or ""),
        "html_url": str(data_dict.get("html_url") or match.group(0)),
    }
    _upstream_cache[key] = res
    return res


def enrich_releases(releases: Any, token: str) -> list[dict[str, Any]]:
    if not isinstance(releases, list):
        return []
    enriched: list[dict[str, Any]] = []
    for release in cast(list[object], releases):
        if not isinstance(release, dict):
            continue
        item = dict(cast(dict[str, Any], release))
        upstream = upstream_release(item, token)
        if upstream:
            item["upstream_release"] = upstream
        enriched.append(item)
    return enriched


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN") or ""
    releases: Any = fetch_json(
        f"https://api.github.com/repos/{args.repo}/releases?per_page=100",
        token,
    )
    workflow: Any = fetch_json(
        f"https://api.github.com/repos/{args.repo}/actions/workflows/ci.yml/runs?per_page=1",
        token,
    )
    ytdlnis: Any = fetch_json(
        "https://api.github.com/repos/deniscerri/ytdlnis/releases/latest",
        token,
    )

    workflow_dict = cast(dict[str, Any], workflow) if isinstance(workflow, dict) else {}
    workflow_runs_raw = workflow_dict.get("workflow_runs", [])
    workflow_runs = cast(list[Any], workflow_runs_raw) if isinstance(workflow_runs_raw, list) else []
    first_run = cast(dict[str, Any], workflow_runs[0]) if workflow_runs and isinstance(workflow_runs[0], dict) else None
    last_sync: str | None = cast(str | None, first_run.get("updated_at")) if first_run else None
    manifest: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "repos": {args.repo: enrich_releases(releases, token)},
        "actions": {"last_sync": last_sync},
        "ytdlnis": ytdlnis,
    }
    args.output.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
