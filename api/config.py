"""Load configuration from environment variables. Import: from config import settings."""

from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = f"sqlite:///{REPO_ROOT}/sleepsense.db"
    redis_url: str = "redis://localhost:6379/0"

    secret_key: str = "CHANGE_ME_IN_PRODUCTION"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    src_path: Path = REPO_ROOT / "src"
    datasets_path: Path = REPO_ROOT / "datasets"
    artifacts_path: Path = REPO_ROOT / "artifacts"
    participant_csv: Path = REPO_ROOT / "datasets" / "participant_info.csv"

    mqtt_broker_host: str = "indigobumble-39b622a1.a02.usw2.aws.hivemq.cloud"
    mqtt_broker_port: int = 8883
    mqtt_username: str = "hivemq.webclient.1776682804651"
    mqtt_password: str = "Up:#KhGRYou7g603Q>l<"

    edge_device: str = "desktop"

    thingspeak_channel_id: str = ""
    thingspeak_read_api_key: str = ""
    thingspeak_poll_seconds: int = 2
    thingspeak_hr_field: str = "field1"
    thingspeak_eda_field: str = "field2"
    thingspeak_temp_field: str = "field3"
    thingspeak_bvp_field: str = "field4"

    @field_validator("src_path", "datasets_path", "artifacts_path", "participant_csv", mode="before")
    @classmethod
    def _coerce_path(cls, v):
        return Path(v) if v is not None and not isinstance(v, Path) else v


settings = Settings()
