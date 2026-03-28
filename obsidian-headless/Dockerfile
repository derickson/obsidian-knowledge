FROM python:3.12-slim

WORKDIR /app

# Install Node.js (for ob CLI) and npm
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install obsidian-headless CLI
RUN npm install -g obsidian-headless

# Install Python dependencies
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY obsidian-headless/pyproject.toml .
RUN uv sync --no-dev

COPY obsidian-headless/app/ app/

EXPOSE 8100
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8100"]
