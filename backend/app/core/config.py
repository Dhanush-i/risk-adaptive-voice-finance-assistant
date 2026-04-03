"""
Configuration Loader
=====================
Loads config from architecture/config.yaml and .env file.
Provides a singleton AppConfig instance for the entire application.
"""

import os
import yaml
from dotenv import load_dotenv
from typing import Dict, Any, Optional
from functools import lru_cache


# Load .env file
load_dotenv()


class AppConfig:
    """Application configuration loaded from YAML + environment variables."""

    def __init__(self, config_path: str = "architecture/config.yaml"):
        # Load YAML config
        with open(config_path, "r") as f:
            self._config = yaml.safe_load(f)

        # Override Razorpay keys from environment
        self._config["razorpay"]["key_id"] = os.getenv(
            "RAZORPAY_KEY_ID", self._config["razorpay"]["key_id"]
        )
        self._config["razorpay"]["key_secret"] = os.getenv(
            "RAZORPAY_KEY_SECRET", self._config["razorpay"]["key_secret"]
        )

        # Override database URL from environment
        db_url = os.getenv("DATABASE_URL")
        if db_url:
            self._config["database"]["url"] = db_url

    # --- Project ---
    @property
    def project_name(self) -> str:
        return self._config["project"]["name"]

    @property
    def seed(self) -> int:
        return self._config["project"]["seed"]

    # --- STT ---
    @property
    def stt(self) -> Dict[str, Any]:
        return self._config["stt"]

    # --- Speaker Verification ---
    @property
    def speaker_verification(self) -> Dict[str, Any]:
        return self._config["speaker_verification"]

    # --- Intent Classification ---
    @property
    def intent_classification(self) -> Dict[str, Any]:
        return self._config["intent_classification"]

    # --- Fraud Detection ---
    @property
    def fraud_detection(self) -> Dict[str, Any]:
        return self._config["fraud_detection"]

    # --- Auth ---
    @property
    def auth(self) -> Dict[str, Any]:
        return self._config["auth"]

    # --- Razorpay ---
    @property
    def razorpay(self) -> Dict[str, Any]:
        return self._config["razorpay"]

    @property
    def razorpay_key_id(self) -> str:
        return self._config["razorpay"]["key_id"]

    @property
    def razorpay_key_secret(self) -> str:
        return self._config["razorpay"]["key_secret"]

    @property
    def razorpay_currency(self) -> str:
        return self._config["razorpay"]["currency"]

    @property
    def razorpay_max_amount_paise(self) -> int:
        return self._config["razorpay"]["max_amount_paise"]

    # --- Database ---
    @property
    def database_url(self) -> str:
        return self._config["database"]["url"]

    # --- API ---
    @property
    def api(self) -> Dict[str, Any]:
        return self._config["api"]

    @property
    def cors_origins(self) -> list:
        return self._config["api"]["cors_origins"]

    # --- Storage ---
    @property
    def storage(self) -> Dict[str, Any]:
        return self._config["storage"]

    # --- Raw access ---
    @property
    def raw(self) -> Dict[str, Any]:
        return self._config


@lru_cache()
def get_config() -> AppConfig:
    """Get the singleton config instance."""
    return AppConfig()
