import hashlib
import re
from pathlib import Path

import frontmatter

from app.config import settings

WIKILINK_PATTERN = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")


def vault_path(override: str | None = None) -> Path:
    return Path(override) if override else Path(settings.vault_path)


def list_notes(folder: str | None = None, vault: str | None = None) -> list[Path]:
    """List all markdown files in the vault, optionally filtered by folder."""
    base = vault_path(vault)
    if folder:
        base = base / folder
    return sorted(base.rglob("*.md"))


def read_note(path: str, vault: str | None = None) -> dict:
    """Read a note and return parsed content, frontmatter, and metadata."""
    full_path = vault_path(vault) / path
    if not full_path.is_file():
        raise FileNotFoundError(f"Note not found: {path}")

    post = frontmatter.load(full_path)
    content = post.content
    metadata = dict(post.metadata)
    wikilinks = extract_wikilinks(content)

    return {
        "path": path,
        "title": metadata.get("title", full_path.stem),
        "content": content,
        "metadata": metadata,
        "tags": metadata.get("tags", []),
        "wikilinks": wikilinks,
        "content_hash": content_hash(content),
        "last_modified": full_path.stat().st_mtime,
    }


def scan_structure(
    vault: str | None = None, max_depth: int = 2, files_per_folder: int = 10,
) -> dict:
    """Walk vault directory and return folder tree with sample filenames."""
    base = vault_path(vault)

    def _scan(directory: Path, depth: int) -> dict:
        folders = []
        md_files = []
        try:
            entries = sorted(directory.iterdir(), key=lambda p: p.name)
        except PermissionError:
            entries = []
        for entry in entries:
            if entry.name.startswith("."):
                continue
            if entry.is_dir() and depth < max_depth:
                folders.append(_scan(entry, depth + 1))
            elif entry.is_file() and entry.suffix == ".md":
                md_files.append(entry.name)
        return {
            "name": directory.name if directory != base else "root",
            "folders": folders,
            "files": md_files[:files_per_folder],
            "file_count": len(md_files),
        }

    return _scan(base, 0)


def extract_wikilinks(content: str) -> list[str]:
    """Extract [[wikilink]] targets from markdown content."""
    return WIKILINK_PATTERN.findall(content)


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()[:16]
