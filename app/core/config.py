"""集中定义应用配置，并从环境变量或 .env 文件自动读取值。"""

from pydantic import Field  # 为配置值附加默认值和数值范围等校验规则。
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置的数据结构。

    实例化时，BaseSettings 会自动查找与字段名对应的环境变量，例如
    ``LLM_API_KEY`` 会写入 ``llm_api_key``。环境变量优先于类中默认值。
    """
    app_name: str = "Qingshang"

    llm_api_key: str | None = None
    llm_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-chat"
    llm_temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    llm_timeout_seconds: float = Field(default=30.0, gt=0)

    # 告诉 pydantic-settings 还要读取项目根目录的 .env；不认识的键直接忽略。
    model_config: SettingsConfigDict = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/qingshang"
    )


# 模块首次导入时创建全局配置对象。其他模块导入 settings 后共享同一份配置。
# 若环境变量格式错误，程序会在启动导入阶段直接报错，而不是运行到中途才发现。
settings = Settings()
