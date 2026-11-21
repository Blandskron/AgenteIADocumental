#!/usr/bin/env python3
"""Validate relative Markdown links in root docs and docs/ without external deps."""

from __future__ import annotations

import re
import sys
from pathlib import Path

LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
INLINE_CODE_RE = re.compile(r"`[^`]*`")
EXTERNAL_PREFIXES = ("http://", "https://", "mailto:", "#")


def check_repo(root: Path) -> list[tuple[str, int, str, str]]:
    files = sorted(list(root.glob("*.md")) + list((root / "docs").rglob("*.md")))
    broken: list[tuple[str, int, str, str]] = []
    for md_file in files:
        in_fence = False
        for line_no, line in enumerate(md_file.read_text(encoding="utf-8").splitlines(), start=1):
            if line.strip().startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            cleaned = INLINE_CODE_RE.sub("", line)
            for label, target in LINK_RE.findall(cleaned):
                target = target.strip()
                if not target or target.startswith(EXTERNAL_PREFIXES):
                    continue
                path_part = target.split("#", 1)[0].strip()
                if not path_part:
                    continue
                resolved = (md_file.parent / path_part).resolve()
                if not resolved.exists():
                    broken.append((str(md_file.relative_to(root)), line_no, label, target))
    return broken


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    broken = check_repo(root)
    if broken:
        for file_path, line_no, label, target in broken:
            print(f"BROKEN LINK: {file_path}:{line_no} [{label}]({target})", file=sys.stderr)
        return 1
    print("OK: all relative Markdown links in root and docs/ resolved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
