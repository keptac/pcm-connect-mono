from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    secret_key: str = "change-me"
    access_token_exp_minutes: int = 60 * 24
    db_url: str = "sqlite:///./pcm.db"
    admin_email: str = "admin@pcm.local"
    admin_password: str = "admin123"
    cors_origins: str = "http://localhost:5173"

    class Config:
        env_file = ".env"


settings = Settings()
