from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.notes import router as notes_router
from app.api.admin import router as admin_router
from app.mcp.tools import mcp
from app.search.client import _es_client, get_es_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    if _es_client is not None:
        _es_client.close()


app = FastAPI(title="Obsidian Knowledge", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(notes_router, prefix="/api/notes", tags=["notes"])
app.include_router(admin_router, prefix="/api/admin", tags=["admin"])

# Mount MCP server at /mcp
app.mount("/mcp", mcp.http_app())
