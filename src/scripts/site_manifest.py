import argparse
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

CHANGELOG_URL = re.compile(
    r"https://github\.com/([^/\s]+/[^/\s]+)/releases/tag/([^\s)]+)"
)


def fetch_json(url: str, token: str) -> object:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "patchpile-manifest",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, headers=headers)
    with urlopen(request) as response:
        return json.load(response)


def upstream_release(release: dict[str, object], token: str) -> dict[str, str] | None:
    body = str(release.get("body") or "")
    match = CHANGELOG_URL.search(body)
    if not match:
        return None

    repo, tag = match.groups()
    url = f"https://api.github.com/repos/{repo}/releases/tags/{quote(tag, safe='')}"
    try:
        data = fetch_json(url, token)
    except HTTPError:
        return None
    if not isinstance(data, dict):
        return None
    return {
        "tag_name": str(data.get("tag_name") or tag),
        "body": str(data.get("body") or ""),
        "html_url": str(data.get("html_url") or match.group(0)),
    }


def enrich_releases(releases: object, token: str) -> list[dict[str, object]]:
    if not isinstance(releases, list):
        return []
    enriched: list[dict[str, object]] = []
    for release in releases:
        if not isinstance(release, dict):
            continue
        item = dict(release)
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
    releases = fetch_json(
        f"https://api.github.com/repos/{args.repo}/releases?per_page=100",
        token,
    )
    workflow = fetch_json(
        f"https://api.github.com/repos/{args.repo}/actions/workflows/ci.yml/runs?per_page=1",
        token,
    )
    ytdlnis = fetch_json(
        "https://api.github.com/repos/deniscerri/ytdlnis/releases/latest",
        token,
    )

    workflow_runs = (
        workflow.get("workflow_runs", []) if isinstance(workflow, dict) else []
    )
    last_sync = workflow_runs[0].get("updated_at") if workflow_runs else None
    manifest = {
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "repos": {args.repo: enrich_releases(releases, token)},
        "actions": {"last_sync": last_sync},
        "ytdlnis": ytdlnis,
    }
    args.output.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
