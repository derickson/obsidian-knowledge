from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    vault_path: str = "/app/vaults/AgentKnowledge"

    model_config = {"env_file": ".env"}


settings = Settings()
