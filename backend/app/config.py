from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Elasticsearch Serverless
    es_url: str = ""
    es_api_key: str = ""
    es_index: str = "obsidian-knowledge"
    es_inference_id: str = "jina-v3-small"

    # Anthropic
    anthropic_api_key: str = ""

    # Obsidian Headless service
    headless_url: str = "http://obsidian-headless:8100"

    # API
    api_prefix: str = "/obsidian-knowledge"

    # MCP authentication
    mcp_api_key: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
