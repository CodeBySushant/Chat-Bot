"""Application settings, loaded from environment / .env."""
from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"          # "json" (prod) or "console" (dev)
    ENVIRONMENT: str = "production"
    # --- Observability ---
    METRICS_ENABLED: bool = True
    OTEL_ENABLED: bool = False
    OTEL_SERVICE_NAME: str = "chatbot-saas-api"
    OTEL_EXPORTER_OTLP_ENDPOINT: str | None = None   # e.g. http://otel-collector:4317
    OTEL_TRACES_SAMPLER_RATIO: float = 0.1
    # --- Dependencies for readiness checks ---
    REDIS_URL: str | None = None
    PROJECT_NAME: str = "Chatbot SaaS API"
    API_V1_PREFIX: str = "/api/v1"

    # Database
    DATABASE_URL: str
    DATABASE_ADMIN_URL: str
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    SQL_ECHO: bool = False

    # JWT / tokens
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ISSUER: str = "chatbot-saas"
    JWT_AUDIENCE: str = "chatbot-saas-api"
    JWT_LEEWAY_SECONDS: int = 10
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    RESET_TOKEN_EXPIRE_HOURS: int = 1
    VERIFY_TOKEN_EXPIRE_HOURS: int = 48

    # Rate limiting (in-process fixed window; swap for Redis in multi-worker prod)
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    RATE_LIMIT_LOGIN_MAX: int = 10
    RATE_LIMIT_REGISTER_MAX: int = 10
    RATE_LIMIT_REFRESH_MAX: int = 30
    RATE_LIMIT_PASSWORD_RESET_MAX: int = 5

    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    # --- Knowledge base / ingestion ---
    STORAGE_DIR: str = "/tmp/kb-storage"
    MAX_UPLOAD_MB: int = 25
    CHUNK_SIZE_CHARS: int = 1000
    CHUNK_OVERLAP_CHARS: int = 150
    INGEST_WORKERS: int = 2

    # Embeddings: "local-hash" (offline, deterministic) or "openai"
    EMBEDDING_PROVIDER: str = "local-hash"
    EMBEDDING_MODEL: str = "local-hash-v1"
    EMBEDDING_DIM: int = 384
    OPENAI_API_KEY: str | None = None
    OPENAI_EMBED_MODEL: str = "text-embedding-3-small"
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"

    # Qdrant: set QDRANT_URL for a server; otherwise embedded local mode at QDRANT_PATH
    QDRANT_URL: str | None = None
    QDRANT_API_KEY: str | None = None
    QDRANT_PATH: str = "/tmp/qdrant-data"
    QDRANT_COLLECTION: str = "kb_chunks"

    # --- Web crawler ---
    CRAWL_WORKERS: int = 1
    CRAWLER_USER_AGENT: str = "ChatbotSaaSBot/1.0 (+https://example.com/bot)"
    CRAWLER_MAX_PAGES: int = 50
    CRAWLER_MAX_DEPTH: int = 3
    CRAWLER_CONCURRENCY: int = 4
    CRAWLER_TIMEOUT_SECONDS: float = 15.0
    CRAWLER_RETRY_MAX: int = 3
    CRAWLER_RETRY_BACKOFF_SECONDS: float = 0.5
    CRAWLER_MAX_BYTES_PER_PAGE: int = 5 * 1024 * 1024
    CRAWLER_RESPECT_ROBOTS: bool = True
    CRAWLER_REQUEST_DELAY_SECONDS: float = 0.0

    # --- Unified AI (LLM) provider layer ---
    AI_PROVIDER: str = "ollama"  # "ollama" | "openai" | (registered future provider)
    AI_REQUEST_TIMEOUT: float = 60.0
    AI_DEFAULT_TEMPERATURE: float = 0.2
    AI_DEFAULT_MAX_TOKENS: int = 1024
    # OpenAI chat (API key/base url reused from the embeddings block above)
    OPENAI_CHAT_MODEL: str = "gpt-4o-mini"
    # Ollama
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.1"

    # --- Retrieval-Augmented Generation ---
    RAG_TOP_K: int = 5
    RAG_MIN_SCORE: float = 0.0
    RAG_MAX_CONTEXT_CHARS: int = 6000
    RAG_HISTORY_TURNS: int = 6
    # --- Billing ---
    AI_COST_PER_1K_TOKENS: float = 0.0005
    JOB_WORKERS: int = 2
    BILLING_PROVIDER: str = "stripe"
    STRIPE_API_KEY: str | None = None
    STRIPE_WEBHOOK_SECRET: str | None = None
    LEMONSQUEEZY_API_KEY: str | None = None
    PADDLE_API_KEY: str | None = None
    RAG_PERSONA: str = "You are a helpful assistant for this company's customers."

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_origins(cls, v):
        if isinstance(v, str) and not v.startswith("["):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @property
    def is_production(self) -> bool:
        return self.ENV.lower() in {"production", "prod"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


def _expand_file_secrets() -> None:
    """Support the ``<VAR>_FILE`` convention used by Docker/Swarm/K8s secrets:
    if ``FOO_FILE`` points at a readable file and ``FOO`` is unset, load the file
    contents into ``FOO``. Keeps secrets out of the process env/image."""
    import os

    for key, path in list(os.environ.items()):
        if not key.endswith("_FILE"):
            continue
        target = key[: -len("_FILE")]
        if os.environ.get(target):
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                os.environ[target] = fh.read().strip()
        except OSError:
            pass


_expand_file_secrets()
settings = get_settings()
