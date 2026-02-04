from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8")
    DATABASE_URL: str = "postgresql+psycopg2://recall:recall@localhost:5432/recall"


settings = Settings()
