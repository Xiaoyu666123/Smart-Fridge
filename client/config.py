from pydantic import model_validator
from pydantic_settings import BaseSettings


DEFAULT_ADMIN_JWT_SECRET = "smart-fridge-admin-jwt-secret-change-in-prod"
DEFAULT_USER_JWT_SECRET = "smart-fridge-user-jwt-secret-change-in-prod"


class Settings(BaseSettings):
    APP_ENV: str = "development"
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/fridge_db"

    # 唯一端侧设备 ID。所有上报接口里 device_id 缺省时取这个值。
    DEVICE_ID: str = "luckfox"

    VISION_API_KEY: str = ""
    VISION_API_URL: str = ""
    VISION_MODEL: str = "qwen-vl-plus"
    VISION_PROVIDER: str = "dashscope"
    LLM_API_KEY: str = ""
    LLM_API_URL: str = ""
    LLM_MODEL: str = "qwen-plus"
    LLM_PROVIDER: str = "dashscope"
    DEFAULT_CITY: str = "北京"

    # 管理员与普通用户使用独立的 JWT 密钥与过期时间
    ADMIN_JWT_SECRET: str = "smart-fridge-admin-jwt-secret-change-in-prod"
    USER_JWT_SECRET: str = "smart-fridge-user-jwt-secret-change-in-prod"
    ADMIN_JWT_EXPIRE_HOURS: int = 24
    USER_JWT_EXPIRE_HOURS: int = 168
    ADMIN_INITIAL_PASSWORD: str = ""

    # Comma-separated list. Empty means dev defaults only.
    CORS_ORIGINS: str = ""
    MAX_IMAGE_BYTES: int = 5 * 1024 * 1024
    MAX_BASE64_IMAGE_CHARS: int = 7 * 1024 * 1024

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() in {"prod", "production", "staging"}

    def cors_origin_list(self) -> list[str]:
        return [x.strip() for x in self.CORS_ORIGINS.split(",") if x.strip()]

    @model_validator(mode="after")
    def validate_security_settings(self):
        if self.is_production:
            if self.ADMIN_JWT_SECRET == DEFAULT_ADMIN_JWT_SECRET:
                raise ValueError("ADMIN_JWT_SECRET must be set to a strong random value in production")
            if self.USER_JWT_SECRET == DEFAULT_USER_JWT_SECRET:
                raise ValueError("USER_JWT_SECRET must be set to a strong random value in production")
            if not self.cors_origin_list():
                raise ValueError("CORS_ORIGINS must be configured in production")
        return self

    class Config:
        env_file = ".env"


settings = Settings()
