from typing import ClassVar

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Qingshang"
    deepseek_api_key: str | None = None

    llm_model: str = "deepseek-chat"
    llm_temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    llm_timeout_seconds: float = Field(default=30.0, gt=0)

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
