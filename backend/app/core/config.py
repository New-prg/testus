from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Driving Analytics MVP"
    api_prefix: str = "/api"
    database_url: str = Field(default="postgresql+psycopg2://postgres:postgres@postgres:5432/driving_analytics", alias="DATABASE_URL")
    jwt_secret: str = Field(default="change_me", alias="JWT_SECRET")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=1440, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    pilot_gps_base_url: str = Field(default="https://pilot-gps.com", alias="PILOT_GPS_BASE_URL")
    pilot_gps_node: int = Field(default=1, alias="PILOT_GPS_NODE")
    pilot_gps_username: str | None = Field(default=None, alias="PILOT_GPS_USERNAME")
    pilot_gps_password: str | None = Field(default=None, alias="PILOT_GPS_PASSWORD")
    use_demo_data: bool = Field(default=True, alias="USE_DEMO_DATA")
    demo_dataset_path: str | None = Field(default=None, alias="DEMO_DATASET_PATH")
    demo_sensor_profile_path: str | None = Field(default=None, alias="DEMO_SENSOR_PROFILE_PATH")
    demo_dataset_row_limit: int = Field(default=500_000, alias="DEMO_DATASET_ROW_LIMIT")


@lru_cache
def get_settings() -> Settings:
    return Settings()
