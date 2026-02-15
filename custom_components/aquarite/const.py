"""Shared constants for the Aquarite integration."""

DOMAIN = "aquarite"
BRAND = "Hayward"
MODEL = "Aquarite"

PATH_PREFIX = "main."
PATH_HASCD = f"{PATH_PREFIX}hasCD"
PATH_HASCL = f"{PATH_PREFIX}hasCL"
PATH_HASPH = f"{PATH_PREFIX}hasPH"
PATH_HASRX = f"{PATH_PREFIX}hasRX"
PATH_HASUV = f"{PATH_PREFIX}hasUV"
PATH_HASHIDRO = f"{PATH_PREFIX}hasHidro"

API_KEY = "AIzaSyBLaxiyZ2nS1KgRBqWe-NY4EG7OzG5fKpE"
IDENTITY_TOOLKIT_BASE = "https://identitytoolkit.googleapis.com/v1/accounts"
SECURETOKEN_URL = "https://securetoken.googleapis.com/v1/token"
API_REFERRER = "https://hayward-europe.web.app/"
HAYWARD_REST_API = "https://europe-west1-hayward-europe.cloudfunctions.net/"

# Time intervals (seconds)
HEALTH_CHECK_INTERVAL = 300  # 5 minutes
POLL_INTERVAL = 60           # 1 minute reconciliation poll