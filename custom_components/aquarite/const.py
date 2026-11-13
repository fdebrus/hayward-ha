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
PATH_HASLED = f"{PATH_PREFIX}hasLED"

# Dispatcher signal fired (suffixed with the entry_id) when a pool appears
# on the account at runtime; payload is the new pool's coordinator.
SIGNAL_NEW_POOL = f"{DOMAIN}_new_pool"

# Time intervals (seconds)
DEFAULT_HEALTH_CHECK_INTERVAL = 300  # 5 minutes
LED_PULSE_DELAY = 1.5  # Delay between off and on when cycling LED color

# Options flow keys
CONF_HEALTH_CHECK_INTERVAL = "health_check_interval"

# Experimental options (aioaquarite 0.14 beta). Each one switches on
# something the first-party web client has been observed to do, so its
# effect can be measured on a real controller; all default to off. See
# PROTOCOL.md in the aioaquarite repository.
CONF_EXPERIMENTAL_FRAGMENT_WRITES = "experimental_fragment_writes"
CONF_EXPERIMENTAL_LED_ENDPOINT = "experimental_led_endpoint"
CONF_EXPERIMENTAL_REQUEST_UPDATES = "experimental_request_updates"

# The web client repeats its update request 10 and 20 minutes after it
# starts listening (three sends in total).
REQUEST_UPDATES_REPEAT_DELAYS = (600, 1200)

# get_pool_stats service fields
ATTR_POOL_ID = "pool_id"
ATTR_TYPE = "type"
ATTR_PERIOD = "period"
DEFAULT_STATS_PERIOD = 30
