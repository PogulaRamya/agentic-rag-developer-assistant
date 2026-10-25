from dataclasses import dataclass
import os

@dataclass(frozen=True)
class Settings:
    mode: str = "demo"
    api_key: str = ""
    database_url: str = ""
    anthropic_key: str = ""
    model: str = "claude-sonnet-4-5"
    project: str = ""
    max_bytes: int = 1_000_000_000
    embedding_model: str = "BAAI/bge-small-en-v1.5"

    @classmethod
    def from_env(cls):
        s = cls(mode=os.getenv("APP_MODE", "demo"), api_key=os.getenv("API_KEY", ""),
                database_url=os.getenv("DATABASE_URL", ""), anthropic_key=os.getenv("ANTHROPIC_API_KEY", ""),
                model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5"), project=os.getenv("GCP_PROJECT", ""),
                max_bytes=int(os.getenv("BQ_MAX_BYTES", "1000000000")))
        if s.mode not in ("demo", "production"):
            raise ValueError("APP_MODE must be demo or production")
        if s.mode == "production" and (len(s.api_key) < 24 or not all([s.database_url,s.anthropic_key,s.project])):
            raise ValueError("Production requires API_KEY (24+ chars), DATABASE_URL, ANTHROPIC_API_KEY and GCP_PROJECT")
        if s.max_bytes <= 0:
            raise ValueError("BQ_MAX_BYTES must be positive")
        return s
