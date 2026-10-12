from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str
    test_database_url: str | None = None
    
    redis_url: str = "redis://localhost:6379/0"
    certificate_processing_timeout_seconds: int = 600
    
    model_config = SettingsConfigDict(env_file=".env",extra="ignore")
    
settings = Settings()

