"""Constants for ETD Intercom."""

from __future__ import annotations

DOMAIN = "etd_intercom"

CONF_TOKEN = "token"
CONF_AUTH_METHOD = "auth_method"
CONF_PHONE = "phone"
CONF_INCLUDE_MANUAL_DEVICES = "include_manual_devices"
CONF_CUSTOM_DEVICES = "custom_devices"

AUTH_METHOD_TOKEN = "token"
AUTH_METHOD_SMS = "sms"

API_BASE_URL = "https://citizen.etd-online.ru"
API_LOGIN_URL = f"{API_BASE_URL}/api/v1/call/login"
API_RESEND_SMS_URL = f"{API_BASE_URL}/api/v1/call/resend-sms"
API_SUBMIT_SMS_URL = f"{API_BASE_URL}/api/v1/call/submit"
API_INTERCOM_LIST_URL = f"{API_BASE_URL}/api/v1/intercom/list"
API_PROFILE_ME_URL = f"{API_BASE_URL}/api/v1/profile/me"
API_OPEN_URL = f"{API_BASE_URL}/api/v1/intercom/{{intercom_id}}/open"

PREVIEW_URL_TEMPLATE = "https://cameras-preview-server.etd-online.ru/api/cameras/preview/{intercom_id}.jpg"

# Private/manual list for the current object. It is optional and can be disabled
# during config flow. API devices from /api/v1/intercom/list always have priority.
MANUAL_DEVICES = [
    {"slug": "kalitka_1", "name": "Калитка 1", "id": "000266", "icon": "mdi:gate-open"},
    {"slug": "kalitka_2", "name": "Калитка 2", "id": "000314", "icon": "mdi:gate-open"},
    {"slug": "kalitka_3", "name": "Калитка 3", "id": "000431", "icon": "mdi:gate-open"},
    {"slug": "kalitka_4", "name": "Калитка 4", "id": "000318", "icon": "mdi:gate-open"},
    {"slug": "kalitka_5", "name": "Калитка 5", "id": "000320", "icon": "mdi:gate-open"},
    {"slug": "kalitka_6", "name": "Калитка 6", "id": "001592", "icon": "mdi:gate-open"},
    {"slug": "kalitka_7", "name": "Калитка 7", "id": "001593", "icon": "mdi:gate-open"},
    {"slug": "kalitka_8", "name": "Калитка 8", "id": "001583", "icon": "mdi:gate-open"},
    {"slug": "kalitka_9", "name": "Калитка 9", "id": "001595", "icon": "mdi:gate-open"},
    {"slug": "vorota_1", "name": "Ворота 1", "id": "001586", "icon": "mdi:gate-open"},
    {"slug": "podiezd_1", "name": "Подъезд 1", "id": "000270", "icon": "mdi:door-open"},
    {"slug": "podiezd_2", "name": "Подъезд 2", "id": "000267", "icon": "mdi:door-open"},
    {"slug": "podiezd_3", "name": "Подъезд 3", "id": "000268", "icon": "mdi:door-open"},
    {"slug": "podiezd_4", "name": "Подъезд 4", "id": "000269", "icon": "mdi:door-open"},
    {"slug": "podiezd_5", "name": "Подъезд 5", "id": "000313", "icon": "mdi:door-open"},
    {"slug": "podiezd_6", "name": "Подъезд 6", "id": "000317", "icon": "mdi:door-open"},
    {"slug": "podiezd_7", "name": "Подъезд 7", "id": "000319", "icon": "mdi:door-open"},
    {"slug": "podiezd_8", "name": "Подъезд 8", "id": "000316", "icon": "mdi:door-open"},
    {"slug": "podiezd_9", "name": "Подъезд 9", "id": "001474", "icon": "mdi:door-open"},
    {"slug": "podiezd_10", "name": "Подъезд 10", "id": "001475", "icon": "mdi:door-open"},
    {"slug": "podiezd_11", "name": "Подъезд 11", "id": "001476", "icon": "mdi:door-open"},
    {"slug": "podiezd_12", "name": "Подъезд 12", "id": "001477", "icon": "mdi:door-open"},
    {"slug": "podiezd_13", "name": "Подъезд 13", "id": "001478", "icon": "mdi:door-open"},
]
