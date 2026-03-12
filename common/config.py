from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # AWS
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_region: str = "us-east-1"
    s3_bucket: str

    # Optional: Google Calendar (needed in Phase 2)
    google_credentials_json: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Single shared instance — import this everywhere
settings = Settings()
