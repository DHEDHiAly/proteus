from pydantic_settings import BaseSettings
from typing import List
import yaml
import os


class Settings(BaseSettings):
    APP_NAME: str = "Proteus"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    DATABASE_URL: str = "postgresql+asyncpg://proteus:proteus@localhost:5432/proteus"
    REDIS_URL: str = "redis://localhost:6379/0"

    SECRET_KEY: str = "proteus-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    FERNET_KEY: str = ""

    MCMCU_CONFIG_PATH: str = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "data", "mcmc_params.yaml"
    )
    TARGETS_DIR: str = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "data", "targets"
    )
    KNOWN_BINDERS_DIR: str = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "data", "known_binders"
    )
    ESM_CACHE_DIR: str = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "data", "models", "esm2_embeddings_cache"
    )
    SCORER_MODEL_PATH: str = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "data", "models", "scorer_weights.pt"
    )

    DATA_RETENTION_DAYS: int = 365
    MAX_CONCURRENT_RUNS: int = 50
    RUN_TIMEOUT_MINUTES: int = 120

    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()


def load_mcmc_config() -> dict:
    with open(settings.MCMCU_CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)
