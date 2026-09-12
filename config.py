"""
config.py — Loads all settings from environment variables / .env file.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "us-east-1"
    s3_bucket: str = ""

    anthropic_api_key: str = ""
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-20b"
    openweather_api_key: str = ""
    google_maps_api_key: str = ""

    google_credentials_json: str = ""
    calendar_id: str = ""
    calendar_timezone: str = "America/New_York"

    home_location: str = ""
    work_location: str = ""
    school_location: str = ""
    briefing_days_ahead: int = 7

    agent_tone: str = "warm and practical"
    daily_routine: str = ""
    briefing_title: str = "Weekly Family Briefing"

    email_sender: str = ""
    email_recipient: str = ""
    gmail_app_password: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
