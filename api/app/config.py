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
    post_call_jobs_enabled: bool = True
    messaging_timeout_seconds: float = 10.0

    llm_api_key: str = ""
    llm_model: str = "gpt-4.1-mini"
    llm_base_url: str = ""
    llm_timeout_seconds: float = 30.0
    call_analysis_max_tokens: int = 800
    call_transcript_max_chars: int = 12000

    stt_cost_per_minute: float = 0.0
    llm_input_cost_per_1m_tokens: float = 0.0
    llm_output_cost_per_1m_tokens: float = 0.0
    tts_cost_per_1m_characters: float = 0.0
    telephony_cost_per_minute: float = 0.0
    cost_currency: str = "INR"

    s3_endpoint_url: str = ""
    s3_region: str = "ap-south-1"
    s3_bucket: str = ""
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_public_base_url: str = ""
    s3_force_path_style: bool = False
    s3_timeout_seconds: float = 30.0
    recording_prefix: str = "recordings"
    recording_max_bytes: int = 50 * 1024 * 1024

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
