from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../../.env", "../.env"), env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite:///./atlas.db"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "dev-only-change-me"
    jwt_expire_minutes: int = 720
    demo_mode: bool = True
    cors_origins: str = "http://localhost:3000,http://localhost:3001"
    session_cookie: str = "atlas_session"
    csrf_cookie: str = "atlas_csrf"
    cookie_secure: bool = False  # set COOKIE_SECURE=true behind HTTPS (required in production)
    cookie_samesite: str = "lax"
    api_rate_limit: int = 600     # requests / minute / IP
    log_level: str = "INFO"
    max_replans: int = 2
    max_parallel: int = 4


settings = Settings()
