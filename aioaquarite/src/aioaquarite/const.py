"""Constants for the aioaquarite library."""

API_KEY = "AIzaSyBLaxiyZ2nS1KgRBqWe-NY4EG7OzG5fKpE"
IDENTITY_TOOLKIT_BASE = "https://identitytoolkit.googleapis.com/v1/accounts"
SECURETOKEN_URL = "https://securetoken.googleapis.com/v1/token"
API_REFERRER = "https://hayward-europe.web.app/"
HAYWARD_REST_API = "https://europe-west1-hayward-europe.cloudfunctions.net/"

FIRESTORE_PROJECT = "hayward-europe"

# Token refresh buffer (seconds before expiry to trigger refresh)
TOKEN_REFRESH_BUFFER = 300  # 5 minutes
