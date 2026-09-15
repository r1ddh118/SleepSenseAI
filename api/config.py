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

    # PySpark data directories
    data_raw_path: Path = REPO_ROOT / "data" / "raw"
    data_processed_path: Path = REPO_ROOT / "data" / "processed"
    data_synthetic_path: Path = REPO_ROOT / "data" / "synthetic"
    data_parquet_path: Path = REPO_ROOT / "data" / "parquet"
    reports_path: Path = REPO_ROOT / "reports" / "generated"

    # MQTT / Hardware — optional, only used when paho-mqtt is installed
    # (see requirements-hardware.txt). Leave empty to disable.
    mqtt_broker_host: str = ""
    mqtt_broker_port: int = 8883
    mqtt_username: str = ""
    mqtt_password: str = ""

    edge_device: str = "desktop"

    @field_validator(
        "src_path", "datasets_path", "artifacts_path", "participant_csv",
        "data_raw_path", "data_processed_path", "data_synthetic_path",
        "data_parquet_path", "reports_path",
        mode="before",
    )
    @classmethod
    def _coerce_path(cls, v):
        return Path(v) if v is not None and not isinstance(v, Path) else v


settings = Settings()
