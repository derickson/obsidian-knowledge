from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Elasticsearch
    es_cloud_id: str = ""
    es_api_key: str = ""
    es_index: str = "obsidian-knowledge"
    es_inference_id: str = "jina-v3-small"

    # Anthropic
    anthropic_api_key: str = ""

    # Vault
    vault_path: str = "/app/vaults/AgentKnowledge"

    model_config = {"env_file": ".env"}


settings = Settings()
