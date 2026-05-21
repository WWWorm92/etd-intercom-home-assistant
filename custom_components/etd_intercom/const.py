from __future__ import annotations

DOMAIN = "etd_intercom"
PLATFORMS = ["button", "camera"]

CONF_AUTH_METHOD = "auth_method"
CONF_TOKEN = "token"
CONF_PHONE = "phone"
CONF_CUSTOM_DEVICES = "custom_devices"

AUTH_METHOD_TOKEN = "token"
AUTH_METHOD_SMS = "sms"

BASE_API_URL = "https://citizen.etd-online.ru/api/v1"
DEFAULT_USER_AGENT = "okhttp/4.12.0"

STATIC_URL_PATH = "/etd_intercom"
STATIC_DIR_NAME = "frontend"
CARD_FILENAME = "etd-intercom-card.js"
CARD_VERSION = "0.7.0"
