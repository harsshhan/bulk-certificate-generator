from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str
    test_database_url: str | None = None
    
    model_config = SettingsConfigDict(env_file=".env")
    
settings = Settings()

