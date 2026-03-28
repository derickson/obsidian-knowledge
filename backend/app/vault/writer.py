from pathlib import Path

import frontmatter

from app.config import settings


def vault_path() -> Path:
    return Path(settings.vault_path)


def write_note(path: str, content: str, metadata: dict | None = None) -> Path:
    """Write a markdown note to the vault with optional frontmatter metadata."""
    full_path = vault_path() / path
    full_path.parent.mkdir(parents=True, exist_ok=True)

    post = frontmatter.Post(content, **(metadata or {}))
    full_path.write_text(frontmatter.dumps(post), encoding="utf-8")
    return full_path


def delete_note(path: str) -> None:
    """Delete a note from the vault."""
    full_path = vault_path() / path
    if full_path.is_file():
        full_path.unlink()
