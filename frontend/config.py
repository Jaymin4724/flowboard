from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parent / ".env"


class AppSettings(BaseSettings):
    API_BASE_URL: str = "http://localhost:8000"
    REQUEST_TIMEOUT: float = 10.0

    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")


settings = AppSettings()
