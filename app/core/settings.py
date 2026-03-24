from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8")
    DATABASE_URL: str = "postgresql+psycopg2://recall:recall@localhost:5432/recall"
    OPENAI_API_KEY: str = ""
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    ANSWER_MODEL: str = "gpt-4.1-mini"


settings = Settings()
