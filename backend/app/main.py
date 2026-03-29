from contextlib import asynccontextmanager

from elasticapm.contrib.starlette import ElasticAPM, make_apm_client
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.notes import router as notes_router
from app.api.admin import router as admin_router
from app.api.chat import router as chat_router
from app.api.vaults import router as vaults_router
from app.config import settings
from app.mcp.tools import mcp
from app.search.client import _es_client, get_es_client

prefix = settings.api_prefix

mcp_app = mcp.http_app(path="/")


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with mcp_app.lifespan(app):
        yield
    if _es_client is not None:
        _es_client.close()


app = FastAPI(title="Obsidian Knowledge", version="0.1.0", lifespan=lifespan)

apm_client = make_apm_client({"SERVICE_NAME": "obsidian-knowledge-backend"})
app.add_middleware(ElasticAPM, client=apm_client)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(notes_router, prefix=f"{prefix}/api/notes", tags=["notes"])
app.include_router(admin_router, prefix=f"{prefix}/api/admin", tags=["admin"])
app.include_router(chat_router, prefix=f"{prefix}/api/chat", tags=["chat"])
app.include_router(vaults_router, prefix=f"{prefix}/api/vaults", tags=["vaults"])

# Mount MCP server
app.mount(f"{prefix}/mcp", mcp_app)
