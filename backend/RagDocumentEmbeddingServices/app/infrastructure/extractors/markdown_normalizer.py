from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

from app.shared.utils import normalize_text

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", re.DOTALL)
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|([^\]]+))?\]\]")
MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)\s]+\.md(?:#[^)]+)?)\)")
INLINE_TAG_RE = re.compile(r"(?<!\w)#([A-Za-z0-9_/-]{2,64})")


@dataclass(frozen=True)
class NormalizedMarkdown:
    clean_text: str
    frontmatter: dict[str, Any]
    wikilinks: list[str]
    markdown_links: list[str]
    tags: list[str]


def is_ignored_vault_path(path_rel: str) -> bool:
    parts = [part.lower() for part in Path(path_rel).parts]
    return any(part in {".obsidian", ".trash", ".git", "__macosx"} for part in parts)


def _parse_simple_yaml(raw_yaml: str) -> dict[str, Any]:
    """Minimal safe parser for YAML frontmatter (scalars and inline/multiline lists) without external deps."""
    result: dict[str, Any] = {}
    current_key: str | None = None
    for line in raw_yaml.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- ") and current_key is not None:
            existing = result.get(current_key)
            if not isinstance(existing, list):
                existing = []
            existing.append(stripped[2:].strip().strip("\"'"))
            result[current_key] = existing
            continue
        if ":" in stripped:
            key, val = stripped.split(":", 1)
            key = key.strip()
            val = val.strip()
            if not key:
                continue
            if val.startswith("[") and val.endswith("]"):
                inner = val[1:-1].strip()
                items = [item.strip().strip("\"'") for item in inner.split(",") if item.strip()] if inner else []
                result[key] = items
                current_key = key
            elif val == "":
                result[key] = []
                current_key = key
            else:
                result[key] = val.strip("\"'")
                current_key = key
    return result


def normalize_markdown(raw_text: str) -> NormalizedMarkdown:
    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    frontmatter: dict[str, Any] = {}
    match = FRONTMATTER_RE.match(text)
    if match:
        frontmatter = _parse_simple_yaml(match.group(1))
        text = text[match.end() :]

    wikilinks = sorted({m.group(1).strip() for m in WIKILINK_RE.finditer(text) if m.group(1).strip()})
    md_links = sorted({m.group(2).strip() for m in MD_LINK_RE.finditer(text) if m.group(2).strip()})

    fm_tags: set[str] = set()
    raw_fm_tags = frontmatter.get("tags")
    if isinstance(raw_fm_tags, list):
        fm_tags.update(str(t).strip().lstrip("#") for t in raw_fm_tags if str(t).strip())
    elif isinstance(raw_fm_tags, str) and raw_fm_tags.strip():
        fm_tags.add(raw_fm_tags.strip().lstrip("#"))

    body_tags = {m.group(1).strip() for m in INLINE_TAG_RE.finditer(text)}
    tags = sorted(fm_tags | body_tags)

    # Replace [[Target|Alias]] -> Alias and [[Target]] -> Target so embeddings read naturally.
    cleaned_body = WIKILINK_RE.sub(lambda m: (m.group(2) or m.group(1)).strip(), text)
    return NormalizedMarkdown(
        clean_text=normalize_text(cleaned_body),
        frontmatter=frontmatter,
        wikilinks=wikilinks,
        markdown_links=md_links,
        tags=tags,
    )


class MarkdownNormalizerExtractor:
    supported_mime_types = {"text/markdown"}

    def extract(self, file_path: str) -> str:
        path = Path(file_path)
        for encoding in ("utf-8", "latin-1"):
            try:
                raw = path.read_text(encoding=encoding)
                return normalize_markdown(raw).clean_text
            except UnicodeDecodeError:
                continue
        return normalize_markdown(path.read_text(errors="ignore")).clean_text

