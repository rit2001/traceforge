"""Check repository-local Markdown file links and heading anchors offline."""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
IGNORED_PARTS = {".git", ".venv", "build", "dist", "htmlcov", "node_modules"}
LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$", re.MULTILINE)


def markdown_files() -> list[Path]:
    return sorted(
        path
        for path in ROOT.rglob("*.md")
        if not IGNORED_PARTS.intersection(path.relative_to(ROOT).parts)
    )


def heading_anchors(text: str) -> set[str]:
    anchors: set[str] = set()
    seen: Counter[str] = Counter()
    for heading in HEADING.findall(text):
        heading = re.sub(r"[`*_~]", "", heading).strip().lower()
        base = re.sub(r"[^\w\- ]", "", heading, flags=re.UNICODE).replace(" ", "-")
        base = re.sub(r"-+", "-", base)
        suffix = seen[base]
        seen[base] += 1
        anchors.add(base if suffix == 0 else f"{base}-{suffix}")
    return anchors


def main() -> int:
    failures: list[str] = []
    checked = 0
    files = markdown_files()
    anchor_cache: dict[Path, set[str]] = {}
    for source in files:
        text = source.read_text()
        for raw_target in LINK.findall(text):
            target = raw_target.strip()
            if target.startswith("<") and ">" in target:
                target = target[1 : target.index(">")]
            else:
                target = target.split(maxsplit=1)[0]
            if re.match(r"^[a-z][a-z0-9+.-]*:", target, flags=re.IGNORECASE):
                continue
            path_part, separator, anchor = target.partition("#")
            destination = (
                source if not path_part else (source.parent / unquote(path_part)).resolve()
            )
            checked += 1
            if not destination.exists():
                failures.append(f"{source.relative_to(ROOT)}: missing {target}")
                continue
            if separator and anchor and destination.is_file() and destination.suffix == ".md":
                anchors = anchor_cache.setdefault(
                    destination, heading_anchors(destination.read_text())
                )
                if unquote(anchor).lower() not in anchors:
                    failures.append(f"{source.relative_to(ROOT)}: missing anchor {target}")
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print(f"checked {checked} internal links across {len(files)} Markdown files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
