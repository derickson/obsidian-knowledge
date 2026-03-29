import asyncio
import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import anthropic
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.config import settings
from app.search.client import recent_notes, search_notes, semantic_search
from app.search.indexer import delete_from_index, index_note, reindex_all
from app.sync import run_ob_sync
from app.vault.reader import list_notes, read_note
from app.vault.writer import delete_note, write_note

logger = logging.getLogger(__name__)

router = APIRouter()

SYSTEM_INSTRUCTIONS = """You are a personal knowledge base assistant for Dave Erickson.
The user is Dave Erickson. When the user says "my", "I", or "me", they mean Dave Erickson.

You are connected to Dave's Obsidian vault.
Notes are markdown files with YAML frontmatter for metadata and [[wikilinks]] for cross-referencing.

## Vault organization

- **Root level**: Primary entries on people, concepts, or tools (e.g., `Dave Erickson.md`, `Elasticsearch.md`)
- **Meetings/**: Time-driven meeting notes as `Meetings/YYYY-MM-DD-Meeting-Name.md`
- **Observations/**: Journal entries, thoughts, and general observations as `Observations/YYYY-MM-DD-Topic.md`
- **Content/**: Notes on consumed content (videos, articles, books) as `Content/Title.md`
- **Inbox/**: Staging area for unsorted or auto-ingested notes
- **TestData/**: Reserved for automated tests — do not use

## Daily notes

- Daily notes live in `Observations/` with the naming pattern `YYYY-MM-DD-Daily.md` (e.g., `Observations/2026-03-28-Daily.md`).
- They use the tags `daily` and `observation` in frontmatter.
- A daily note captures the day's plans, reflections, and links to other vault entries (meetings, content, people).
- When the user asks about "today", "yesterday", or a specific date without specifying a note, check the corresponding daily note first.

## Behavior

- Use `semantic` search for natural language questions (hybrid BM25 + vector search).
- Use `search` for exact keyword matching.
- Use `read` to get the full content of a specific note after finding it via search.
- When answering questions, search first, then read relevant notes for full context.
- Follow [[wikilinks]] in notes to find related information when the initial answer is incomplete.
- Use `[[wikilinks]]` when creating or editing notes to link related concepts.
- When creating notes, search first to avoid duplicates. Prefer linking over repeating information.
- Add relevant tags in metadata when creating notes.
"""

TOOLS = [
    {
        "name": "search",
        "description": "Full-text BM25 search across all notes. Returns path, title, and content preview.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "size": {"type": "integer", "description": "Max results (default 10)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "semantic",
        "description": "Hybrid semantic search (BM25 + vector). Best for natural language questions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Natural language query"},
                "size": {"type": "integer", "description": "Max results (default 10)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "read",
        "description": "Read the full content of a specific note by path.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Note path (e.g., 'Dave Erickson.md')"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "list_all_notes",
        "description": "List all note paths in the vault, optionally filtered by folder.",
        "input_schema": {
            "type": "object",
            "properties": {
                "folder": {"type": "string", "description": "Folder to list (optional)"},
            },
        },
    },
    {
        "name": "create",
        "description": "Create or update a note. Content should be markdown. Metadata becomes YAML frontmatter.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Note path (e.g., 'Meetings/2026-03-28-Standup.md')"},
                "content": {"type": "string", "description": "Markdown content"},
                "metadata": {
                    "type": "object",
                    "description": "Frontmatter metadata (tags, source, etc.)",
                },
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "delete",
        "description": "Delete a single note from the knowledge base.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Note path to delete"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "reindex",
        "description": "Reindex all vault notes into Elasticsearch. Use sparingly.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
]


def _truncate_search_results(results: list[dict]) -> list[dict]:
    """Truncate content in search results to keep context manageable."""
    truncated = []
    for r in results:
        entry = {"path": r.get("path"), "title": r.get("title"), "tags": r.get("tags", [])}
        content = r.get("content", "")
        entry["content_preview"] = content[:500] + "..." if len(content) > 500 else content
        truncated.append(entry)
    return truncated


async def execute_tool(name: str, tool_input: dict, vault_id: str | None = None) -> str:
    """Execute a tool and return the result as a JSON string."""
    try:
        match name:
            case "search":
                result = await asyncio.to_thread(
                    search_notes, tool_input["query"], tool_input.get("size", 10),
                    vault_id=vault_id,
                )
                result = _truncate_search_results(result)
            case "semantic":
                result = await asyncio.to_thread(
                    semantic_search, tool_input["query"], tool_input.get("size", 10),
                    vault_id=vault_id,
                )
                result = _truncate_search_results(result)
            case "read":
                result = await asyncio.to_thread(
                    read_note, tool_input["path"], vault_id=vault_id
                )
            case "list_all_notes":
                result = await asyncio.to_thread(
                    list_notes, tool_input.get("folder"), vault_id=vault_id
                )
            case "create":
                await asyncio.to_thread(
                    write_note, tool_input["path"], tool_input["content"],
                    tool_input.get("metadata"), vault_id=vault_id,
                )
                note = await asyncio.to_thread(
                    read_note, tool_input["path"], vault_id=vault_id
                )
                await asyncio.to_thread(index_note, note, vault_id=vault_id)
                await run_ob_sync(vault_id=vault_id)
                result = {"status": "created", "path": tool_input["path"]}
            case "delete":
                await asyncio.to_thread(
                    delete_note, tool_input["path"], vault_id=vault_id
                )
                await asyncio.to_thread(
                    delete_from_index, tool_input["path"], vault_id=vault_id
                )
                await run_ob_sync(vault_id=vault_id)
                result = {"status": "deleted", "path": tool_input["path"]}
            case "reindex":
                result = await asyncio.to_thread(reindex_all, vault_id=vault_id)
            case _:
                result = {"error": f"Unknown tool: {name}"}
    except Exception as e:
        logger.error("Tool %s failed: %s", name, e)
        result = {"error": str(e)}

    return json.dumps(result, default=str)


def build_system_prompt(
    focused_note_path: str | None,
    tz_name: str = "America/New_York",
    vault_id: str | None = None,
) -> str:
    """Build system prompt, optionally including focused note content."""
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("America/New_York")
    now = datetime.now(tz).strftime("%A, %Y-%m-%d %H:%M %Z")
    prompt = f"Current date and time: {now}\n\n" + SYSTEM_INSTRUCTIONS
    if vault_id:
        prompt += f"\nYou are currently working in the **{vault_id}** vault.\n"
    if focused_note_path:
        try:
            note = read_note(focused_note_path, vault_id=vault_id)
            prompt += f"""
## Currently focused note

The user has this note open in the UI:
- **Path**: {note['path']}
- **Title**: {note['title']}
- **Tags**: {', '.join(note.get('tags', []))}
- **Wikilinks**: {', '.join(note.get('wikilinks', []))}

**Full content:**
{note['content']}
"""
        except Exception:
            pass
    return prompt


class ChatRequest(BaseModel):
    messages: list[dict]
    model: str = "claude-haiku-4-5-20251001"
    focused_note_path: str | None = None
    timezone: str = "America/New_York"
    vault: str | None = None


@router.post("/")
async def chat(request: ChatRequest):
    """Streaming chat with Claude, with tool access to the knowledge base."""
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def event_stream():
        messages = request.messages
        system_prompt = build_system_prompt(
            request.focused_note_path, request.timezone, vault_id=request.vault
        )

        while True:
            collected_content = []

            async with client.messages.stream(
                model=request.model,
                max_tokens=8192,
                system=system_prompt,
                messages=messages,
                tools=TOOLS,
            ) as stream:
                async for event in stream:
                    if event.type == "content_block_start":
                        block = event.content_block
                        if block.type == "tool_use":
                            yield f"data: {json.dumps({'type': 'tool_use_start', 'name': block.name, 'id': block.id})}\n\n"
                    elif event.type == "content_block_delta":
                        delta = event.delta
                        if hasattr(delta, "text"):
                            yield f"data: {json.dumps({'type': 'text', 'content': delta.text})}\n\n"

                final_message = await stream.get_final_message()
                collected_content = final_message.content

            if final_message.stop_reason == "tool_use":
                messages.append({"role": "assistant", "content": collected_content})

                tool_results = []
                for block in collected_content:
                    if block.type == "tool_use":
                        result = await execute_tool(block.name, block.input, vault_id=request.vault)
                        yield f"data: {json.dumps({'type': 'tool_result', 'name': block.name, 'id': block.id})}\n\n"
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        })

                messages.append({"role": "user", "content": tool_results})
            else:
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                break

    return StreamingResponse(event_stream(), media_type="text/event-stream")
