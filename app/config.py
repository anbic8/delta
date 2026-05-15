from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    postgres_db: str
    postgres_user: str
    postgres_password: str
    postgres_host: str = "db"
    postgres_port: int = 5432

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # LLM-Integration
    llm_backend: str = "ollama"          # "ollama" | "claude"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    anthropic_api_key: str = ""

    empfehlung_schwelle_schwach: float = 60.0
    empfehlung_schwelle_sehr_schwach: float = 40.0
    empfehlung_max_pro_kapitel: int = 2

    model_config = {"env_file": ".env"}


settings = Settings()
