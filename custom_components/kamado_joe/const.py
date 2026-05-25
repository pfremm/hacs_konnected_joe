DOMAIN = "kamado_joe"
DEFAULT_SCAN_INTERVAL = 30  # seconds

API_BASE_URL = "https://cas.kamadojoe.com"
API_LOGIN_PATH = "/api/v1/auth/login"
API_DEVICE_SHADOW_PATH = "/api/v1/paired-device/{device_id}/shadows/current"

# OAuth client credentials embedded in the Kamado Joe iOS app.
# These identify the app to the API; they are NOT end-user credentials.
CLIENT_ID = "0oag310cbuWhqCUx30h7"
CLIENT_SECRET = "sL7Wxyya8C4RDjLyAPvFxUQtvDWKpIjm5-mv31Vr"

# Config entry keys
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_DEVICE_ID = "device_id"
CONF_THING_NAME = "thing_name"
CONF_SCAN_INTERVAL = "scan_interval"
