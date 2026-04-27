"""Constants for the YoDeck integration."""

DOMAIN = "yodeck"
DEFAULT_NAME = "YoDeck"

# API
API_BASE_URL = "https://app.yodeck.com/api/v2"
DEFAULT_SCAN_INTERVAL = 3600  # seconds (60 minutes)
MIN_SCAN_INTERVAL = 300  # seconds (5 minutes - minimum to respect rate limits)

# Config
CONF_SCREEN_ID = "screen_id"
CONF_SCAN_INTERVAL = "scan_interval"
