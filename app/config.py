import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./media_lab.db")
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    media_root: str = os.getenv("MEDIA_ROOT", "/data/media")
    douyin_cli_path: str = os.getenv("DOUYIN_CLI_PATH", "douyin")
    douyin_cli_profile: str = os.getenv("DOUYIN_CLI_PROFILE", "")
    douyin_cookie_file: str = os.getenv("DOUYIN_COOKIE_FILE", "")
    enable_transcription: bool = os.getenv("ENABLE_TRANSCRIPTION", "0") == "1"
    whisper_model: str = os.getenv("WHISPER_MODEL", "small")


settings = Settings()
