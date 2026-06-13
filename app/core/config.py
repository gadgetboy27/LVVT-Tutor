import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = os.environ.get("DATABASE_URL", "")
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "your-secret-key-change-in-production")
    ALGORITHM: str = "HS256"
    # Long-lived token so users stay signed in across sessions (default 7 days).
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", str(60 * 24 * 7)))
    
    # LLM provider: "auto" tries Anthropic (Claude Fable 5) first, then OpenAI.
    LLM_PROVIDER: str = os.environ.get("LLM_PROVIDER", "auto")

    # Anthropic (Claude Fable 5) — primary text AI
    ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL: str = os.environ.get("ANTHROPIC_MODEL", "claude-fable-5")

    # OpenAI — fallback for text AI, and audio (text-to-speech has no Anthropic equivalent)
    OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY") or os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY", "")
    OPENAI_BASE_URL: str = os.environ.get("OPENAI_BASE_URL") or os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL", "")
    OPENAI_MODEL: str = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    LVVTA_BASE_URL: str = "https://www.lvvta.org.nz"
    CHROMA_PERSIST_DIR: str = "./chroma_db"
    
    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
