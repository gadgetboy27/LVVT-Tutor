import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = os.environ.get("DATABASE_URL", "")
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "your-secret-key-change-in-production")
    ALGORITHM: str = "HS256"
    # Long-lived token so users stay signed in across sessions (default 7 days).
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", str(60 * 24 * 7)))
    
    # LLM provider: "auto" tries Anthropic (Claude Fable 5) first, then OpenAI.
    # Optional cheaper/faster Anthropic model just for building study guides (selection + short
    # restatement; every quote is machine-verified). Empty = use ANTHROPIC_MODEL.
    STUDY_GUIDE_MODEL: str = os.environ.get("STUDY_GUIDE_MODEL", "")
    LLM_PROVIDER: str = os.environ.get("LLM_PROVIDER", "auto")

    # Anthropic (Claude Fable 5) — primary text AI
    ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")
    # Default to Opus 4.8 (broadly available); set ANTHROPIC_MODEL=claude-fable-5
    # in the environment if your account has Fable access.
    ANTHROPIC_MODEL: str = os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-8")

    # OpenAI — fallback for text AI, and audio (text-to-speech has no Anthropic equivalent)
    OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY") or os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY", "")
    OPENAI_BASE_URL: str = os.environ.get("OPENAI_BASE_URL") or os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL", "")
    OPENAI_MODEL: str = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    # Keep indexed LVVTA PDFs current: on startup and then every N hours, re-check
    # each source PDF and re-index any that changed upstream.
    PDF_REFRESH_ENABLED: bool = os.environ.get("PDF_REFRESH_ENABLED", "true").lower() in ("1", "true", "yes")
    PDF_REFRESH_INTERVAL_HOURS: float = float(os.environ.get("PDF_REFRESH_INTERVAL_HOURS", "24"))

    LVVTA_BASE_URL: str = "https://www.lvvta.org.nz"
    CHROMA_PERSIST_DIR: str = "./chroma_db"
    # Where downloaded source PDFs are cached. On a host with a persistent volume, point
    # this (and CHROMA_PERSIST_DIR) at it so redeploys keep them.
    # Chroma downloads an ~80 MB embedding model to ~/.cache/chroma on first use. Set this to
    # a persistent path (e.g. a volume) to symlink that cache there so redeploys skip the download.
    MODEL_CACHE_DIR: str = os.environ.get("MODEL_CACHE_DIR", "")
    PDF_CACHE_DIR: str = os.environ.get("PDF_CACHE_DIR", "pdf_cache")
    
    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
