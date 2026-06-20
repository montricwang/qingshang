"""定义应用配置。"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import ClassVar


class Settings(BaseSettings):
    """从 .env 读取的应用配置。"""

    # --- 基础配置 ---
    app_name: str

    # --- 大模型配置 ---
    llm_api_key: str
    llm_base_url: str
    llm_model: str
    llm_temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    llm_timeout_seconds: float = Field(default=30.0, gt=0)

    # --- 数据库配置 ---
    database_url: str

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# BaseSettings 会在实例化时读取环境变量；格式错误会阻止应用启动。
settings = Settings()  # pyright: ignore[reportCallIssue]
