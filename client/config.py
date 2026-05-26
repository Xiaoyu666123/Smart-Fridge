from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/fridge_db"

    VISION_API_KEY: str = ""
    VISION_API_URL: str = ""
    VISION_MODEL: str = "qwen-vl-plus"
    LLM_API_KEY: str = ""
    LLM_API_URL: str = ""
    LLM_MODEL: str = "qwen-plus"
    DEFAULT_CITY: str = "北京"

    JWT_SECRET: str = "smart-fridge-jwt-secret-key-change-in-prod"
    JWT_EXPIRE_HOURS: int = 168

    class Config:
        env_file = ".env"


settings = Settings()
