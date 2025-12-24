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
BASE_URL = "https://identitytoolkit.googleapis.com/v1/accounts"
TOKEN_URL = "https://securetoken.googleapis.com/v1/token"
HAYWARD_REST_API = "https://europe-west1-hayward-europe.cloudfunctions.net/"

# Time intervals (seconds)
HEALTH_CHECK_INTERVAL = 300  # Interval for periodic health checks
POLL_INTERVAL = 60  # Interval for polling the Firestore document