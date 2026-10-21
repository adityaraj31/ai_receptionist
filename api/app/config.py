from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    database_url: str
    database_ssl: str | None = None
    secret_key: str = ""
    access_token_minutes: int = 480
    jwt_algorithm: str = "HS256"
    dashboard_url: str = "http://localhost:3000"
    api_title: str = "AI Receptionist API"

    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    embedding_dimensions: int = 384
    fastembed_cache_path: str = ""
    embedding_warmup: bool = True
    faq_max_distance: float = 0.55
    faq_high_confidence_similarity: float = 0.55
    faq_answer_max_chars: int = 320

    redis_url: str = "redis://localhost:6379/0"
    arq_queue_name: str = "post_call"
    reminder_jobs_enabled: bool = True
    messaging_timeout_seconds: float = 10.0

    whatsapp_provider: str = "none"
    whatsapp_api_url: str = "https://graph.facebook.com/v21.0"
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    gupshup_api_url: str = "https://api.gupshup.io/wa/api/v1"
    gupshup_api_key: str = ""
    gupshup_app_name: str = ""
    gupshup_source_number: str = ""

    sms_provider: str = "none"
    exotel_subdomain: str = "api.exotel.com"
    exotel_sid: str = ""
    exotel_api_key: str = ""
    exotel_api_token: str = ""
    exotel_caller_id: str = ""
    plivo_auth_id: str = ""
    plivo_auth_token: str = ""
    plivo_number: str = ""

    model_config = SettingsConfigDict(
        env_file=(ROOT_DIR / ".env", ROOT_DIR / "api" / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        if value.startswith("postgres://"):
            return "postgresql+asyncpg://" + value.removeprefix("postgres://")
        if value.startswith("postgresql://"):
            return "postgresql+asyncpg://" + value.removeprefix("postgresql://")
        return value

    @model_validator(mode="after")
    def extract_database_ssl(self) -> "Settings":
        parts = urlsplit(self.database_url)
        query = dict(parse_qsl(parts.query))
        sslmode = query.pop("sslmode", None)
        if sslmode:
            self.database_ssl = sslmode
            self.database_url = urlunsplit(parts._replace(query=urlencode(query)))
        return self


settings = Settings()
