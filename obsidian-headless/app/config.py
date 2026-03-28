from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    vault_path: str = "/app/vaults/AgentKnowledge"
    # Path ob sync uses — matches the host path in ob's config when running in Docker
    vault_sync_path: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
