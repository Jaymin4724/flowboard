from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import EmailStr


class Settings(BaseSettings):
    # Pydantic automatically reads these from environment variables
    # or the specified .env file
    DB_URL: str
    TEST_DB_URL: str

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    SECRET_ACCESS_KEY: str
    SECRET_REFRESH_KEY: str
    ALGORITHM: str = "HS256"

    REDIS_HOST: str
    REDIS_PORT: int = 6379
    REDIS_URL: str
    MAIL_USERNAME: EmailStr
    MAIL_PASSWORD: str
    MAIL_FROM: str
    MAIL_PORT: int = 587
    MAIL_SERVER: str

    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str
    AWS_REGION: str
    AWS_S3_BUCKET: str
    TESTING: bool = True
    EMAIL_SERVICE_ACTIVE: bool = True
    # Configuration to link the .env file
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
