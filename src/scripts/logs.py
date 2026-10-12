# ---------------------------------------------------------
# Copyright (C) 2026 krvstek (Original Author)
# Copyright (C) 2026 The uni-apks Contributors (Modifications)
# 
# DO NOT REMOVE OR ALTER THIS COPYRIGHT HEADER.
# This file is part of uni-apks.
# Canonical source: https://github.com/krvstek/uni-apks
#
# Licensed under the GNU GPLv3. You may modify this file,
# but you MUST keep this original copyright notice intact
# and prominently state any changes made.
# See the AUTHORS file in the root directory for details.
# ---------------------------------------------------------

import json
import re
import sys
from pathlib import Path

from src.core.logger import IS_GITHUB, abort


def _require_ci(script: str) -> None:
    if not IS_GITHUB:
        abort(f"'{script}' is only available in GitHub Actions")


def _parse_log_file(
    log: Path,
    green_map: dict[str, str],
    collected: list[str],
    valid_assets: set[str] | None = None,
) -> str:
    microg_line = ""
    lines = [s for ln in log.read_text(encoding="utf-8").splitlines() if (s := ln.strip())]
    for i, line in enumerate(lines):
        if line.startswith("- 🟢"):
            if valid_assets is not None:
                apk_match = re.search(r"/([^/\s)]+\.apk)", line)
                if apk_match and apk_match.group(1) not in valid_assets:
                    continue
            m = re.search(r"»\s*([^:]+):", line)
            key = m.group(1).strip() if m else line
            green_map[key] = f"{line.rstrip()}  "
        elif not microg_line and line.startswith("▶️") and "MicroG" in line:
            microg_line = line
        elif line.startswith("> ⚙️ » CLI:"):
            collected.append(f"{line}  ")
        elif line.startswith("> ⚙️ » Patches:"):
            next_line = lines[i + 1] if i + 1 < len(lines) else ""
            collected.append(f"{line}  \n{next_line}  ")
    return microg_line


def combine_logs(
    logs_dir: Path | str,
    existing_notes: Path | str | None = None,
    assets_file: Path | str | None = None,
) -> None:
    green_map: dict[str, str] = {}
    collected: list[str] = []
    microg_line = ""

    valid_assets: set[str] | None = None
    if assets_file and Path(assets_file).is_file():
        try:
            raw = json.loads(Path(assets_file).read_text(encoding="utf-8"))
            if isinstance(raw, list):
                valid_assets = {str(item) for item in raw}
        except Exception:
            valid_assets = None

    if existing_notes and Path(existing_notes).is_file() and Path(existing_notes).stat().st_size > 0:
        m_line = _parse_log_file(
            Path(existing_notes),
            green_map,
            collected,
            valid_assets=valid_assets,
        )
        if m_line:
            microg_line = m_line

    logs = sorted(Path(logs_dir).rglob("build*.md")) if Path(logs_dir).exists() else []
    for log in logs:
        m_line = _parse_log_file(log, green_map, collected, valid_assets=None)
        if m_line:
            microg_line = m_line

    if not green_map and not collected:
        return

    if green_map:
        print("\n".join(green_map.values()), end="\n\n")

    if microg_line:
        print(microg_line, end="\n\n")

    if unique := list(dict.fromkeys(collected)):
        print("\n\n".join(unique))


def main() -> None:
    _require_ci("logs.py")
    match sys.argv[1:]:
        case ["combine-logs", *args]:
            logs_dir = Path(args[0]) if args else Path("logs")
            existing_notes = Path(args[1]) if len(args) > 1 and Path(args[1]).is_file() else None
            assets_file = Path(args[2]) if len(args) > 2 and Path(args[2]).is_file() else None
            combine_logs(logs_dir=logs_dir, existing_notes=existing_notes, assets_file=assets_file)
        case _:
            abort("Usage: logs.py combine-logs [dir] [existing_notes] [assets_file]")


if __name__ == "__main__":
    main()