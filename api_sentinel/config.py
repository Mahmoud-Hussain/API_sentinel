from typing import List
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./sentinel.db"
    retention_days: int = 30
    masked_fields: List[str] = ["password", "token", "credit_card", "authorization"]
    selective_persistence: bool = False

    class Config:
        env_file = ".env"
        env_prefix = "SENTINEL_"

settings = Settings()
