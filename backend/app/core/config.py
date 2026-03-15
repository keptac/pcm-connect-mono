from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = Field(
        "PCM System",
        validation_alias=AliasChoices("APP_NAME", "app_name"),
    )
    secret_key: str = Field(
        "change-me",
        validation_alias=AliasChoices("SECRET_KEY", "secret_key"),
    )
    access_token_expire_minutes: int = Field(
        30,
        validation_alias=AliasChoices(
            "ACCESS_TOKEN_EXPIRE_MINUTES",
            "ACCESS_TOKEN_EXP_MINUTES",
            "access_token_exp_minutes",
        ),
    )
    refresh_token_expire_days: int = Field(
        7,
        validation_alias=AliasChoices(
            "REFRESH_TOKEN_EXPIRE_DAYS",
            "refresh_token_expire_days",
        ),
    )
    database_url: str = Field(
        "postgresql+psycopg2://pcm_user:pcm_pass@db:5432/pcm_db",
        validation_alias=AliasChoices("DATABASE_URL", "DB_URL", "db_url"),
    )
    upload_dir: str = Field(
        "/data/uploads",
        validation_alias=AliasChoices("UPLOAD_DIR", "upload_dir"),
    )
    allowed_upload_extensions: str = Field(
        "csv,xlsx,jpg,jpeg,png,pdf,doc,docx",
        validation_alias=AliasChoices(
            "ALLOWED_UPLOAD_EXTENSIONS",
            "allowed_upload_extensions",
        ),
    )
    max_upload_mb: int = Field(
        10,
        validation_alias=AliasChoices("MAX_UPLOAD_MB", "max_upload_mb"),
    )
    admin_email: str = Field(
        "admin@pcm.local",
        validation_alias=AliasChoices("ADMIN_EMAIL", "admin_email"),
    )
    admin_password: str = Field(
        "admin123",
        validation_alias=AliasChoices("ADMIN_PASSWORD", "admin_password"),
    )
    service_recovery_email: str = Field(
        "adam@pcm.service",
        validation_alias=AliasChoices("SERVICE_RECOVERY_EMAIL", "service_recovery_email"),
    )
    service_recovery_password: str = Field(
        "change-me-service-password",
        validation_alias=AliasChoices("SERVICE_RECOVERY_PASSWORD", "service_recovery_password"),
    )
    cors_origins: str = Field(
        "http://localhost:5173",
        validation_alias=AliasChoices("CORS_ORIGINS", "cors_origins"),
    )


settings = Settings()
