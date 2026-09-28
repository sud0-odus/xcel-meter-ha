from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", ".pytest_cache", ".venv", "venv", "delivery", "__pycache__"}
LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")


def markdown_files() -> list[Path]:
    return sorted(
        path
        for path in ROOT.rglob("*.md")
        if not any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts)
    )


def github_slug(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text).strip().lower()
    text = re.sub(r"[`*_~]", "", text)
    text = re.sub(r"[^\w\- ]", "", text, flags=re.UNICODE)
    text = re.sub(r"\s", "-", text)
    return text.strip("-")


def headings_for(path: Path) -> set[str]:
    headings: set[str] = set()
    counts: dict[str, int] = {}
    fence: str | None = None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        fence_match = FENCE_RE.match(raw_line)
        if fence_match:
            marker = fence_match.group(1)[0]
            if fence is None:
                fence = marker
            elif marker == fence:
                fence = None
            continue
        if fence is not None:
            continue

        match = HEADING_RE.match(raw_line)
        if not match:
            continue
        base = github_slug(match.group(2))
        if not base:
            continue
        duplicate = counts.get(base, 0)
        counts[base] = duplicate + 1
        headings.add(base if duplicate == 0 else f"{base}-{duplicate}")

    return headings


def split_destination(raw: str) -> str:
    value = raw.strip()
    if value.startswith("<") and ">" in value:
        return value[1 : value.index(">")]
    # Markdown titles are optional after whitespace; project-local links do not use spaces.
    return value.split(maxsplit=1)[0]


def is_external(destination: str) -> bool:
    parsed = urlsplit(destination)
    return bool(parsed.scheme or parsed.netloc) or destination.startswith("//")


def check_markdown(path: Path, heading_cache: dict[Path, set[str]]) -> list[str]:
    errors: list[str] = []
    fence: str | None = None
    fence_line = 0

    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        fence_match = FENCE_RE.match(raw_line)
        if fence_match:
            marker = fence_match.group(1)[0]
            if fence is None:
                fence = marker
                fence_line = line_number
            elif marker == fence:
                fence = None
                fence_line = 0
            continue
        if fence is not None:
            continue

        for match in LINK_RE.finditer(raw_line):
            destination = split_destination(match.group(1))
            if not destination or is_external(destination):
                continue

            parsed = urlsplit(destination)
            fragment = unquote(parsed.fragment)
            local_path = unquote(parsed.path)

            if local_path.startswith("/"):
                # Treat repository-relative absolute-looking paths as non-file website paths.
                continue

            target = path if not local_path else (path.parent / local_path).resolve()
            try:
                target.relative_to(ROOT)
            except ValueError:
                errors.append(
                    f"{path.relative_to(ROOT)}:{line_number}: local link escapes repository: {destination}"
                )
                continue

            if not target.exists():
                errors.append(
                    f"{path.relative_to(ROOT)}:{line_number}: missing local link target: {destination}"
                )
                continue

            if fragment and target.is_file() and target.suffix.lower() == ".md":
                headings = heading_cache.setdefault(target, headings_for(target))
                if fragment.lower() not in headings:
                    errors.append(
                        f"{path.relative_to(ROOT)}:{line_number}: missing Markdown anchor "
                        f"#{fragment} in {target.relative_to(ROOT)}"
                    )

    if fence is not None:
        errors.append(
            f"{path.relative_to(ROOT)}:{fence_line}: unclosed fenced code block ({fence * 3})"
        )

    return errors


def main() -> int:
    files = markdown_files()
    heading_cache: dict[Path, set[str]] = {}
    errors: list[str] = []
    for path in files:
        errors.extend(check_markdown(path, heading_cache))

    if errors:
        print("Documentation validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"Documentation validation PASS: {len(files)} Markdown files checked.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
