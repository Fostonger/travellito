import os
from typing import Optional, List
from functools import lru_cache


class Settings:
    """Application settings following Single Responsibility Principle"""
    
    # Database
    DB_DSN: str = os.getenv("DB_DSN", "")
    DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "5"))
    DB_ECHO: bool = os.getenv("DB_ECHO", "false").lower() == "true"
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_SECONDS: int = int(os.getenv("JWT_ACCESS_TTL", "900"))  # 15 minutes
    REFRESH_TOKEN_EXPIRE_SECONDS: int = int(os.getenv("JWT_REFRESH_TTL", str(60 * 60 * 24 * 30)))  # 30 days
    
    # CORS
    CORS_ALLOW_ORIGINS: List[str] = []
    CORS_ALLOW_CREDENTIALS: bool = True
    
    # Storage
    S3_ENDPOINT: str = os.getenv("S3_ENDPOINT", "")
    S3_ACCESS_KEY: str = os.getenv("S3_ACCESS_KEY", "")
    S3_SECRET_KEY: str = os.getenv("S3_SECRET_KEY", "")
    S3_BUCKET: str = os.getenv("S3_BUCKET", "travellito")
    S3_REGION: str = os.getenv("S3_REGION", "us-east-1")
    S3_SECURE: bool = os.getenv("S3_SECURE", "false").lower() == "true"
    
    # Telegram Bot
    BOT_ALIAS: str = os.getenv("BOT_ALIAS", "TravellitoBot")
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    WEBAPP_URL: str = os.getenv("WEBAPP_URL", "")
    
    # Rate Limiting
    RATE_LIMIT_DEFAULT: str = "100/minute"
    
    # Business Rules
    DEFAULT_MAX_COMMISSION: float = 10.0
    DEFAULT_FREE_CANCELLATION_HOURS: int = 24
    
    # Yandex Metrica
    METRIKA_COUNTER: str = os.getenv("METRIKA_COUNTER", "")
    METRIKA_MP_TOKEN: str = os.getenv("METRIKA_MP_TOKEN", "")
    
    def __init__(self):
        self._validate()
        self._parse_cors_origins()
    
    def _validate(self):
        """Validate required settings"""
        if not self.SECRET_KEY:
            raise ValueError("SECRET_KEY environment variable must be set")
        if not self.DB_DSN:
            raise ValueError("DB_DSN environment variable must be set")
    
    def _parse_cors_origins(self):
        """Parse CORS origins from environment"""
        raw_origins = os.getenv("CORS_ALLOW_ORIGINS") or os.getenv("WEBAPP_URL", "*")
        
        if raw_origins.strip() == "*":
            self.CORS_ALLOW_ORIGINS = ["*"]
            self.CORS_ALLOW_CREDENTIALS = False  # Security: wildcard forbids credentials
        else:
            self.CORS_ALLOW_ORIGINS = [o.strip() for o in raw_origins.split(",") if o.strip()]
            self.CORS_ALLOW_CREDENTIALS = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings() 