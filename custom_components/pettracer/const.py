"""Constants for PetTracer integration."""

DOMAIN = "pettracer"

# API URLs
API_URL = "https://portal.pettracer.com/api"
WEBSOCKET_URL = "https://pt.pettracer.com/sc"

# API Endpoints
ENDPOINT_LOGIN = "/user/login"
ENDPOINT_USER_INFO = "/user/info"
ENDPOINT_CC_LIST = "/user/details"  # Gets list of command centers (trackers)
ENDPOINT_CC_FIFO = "/cc/{cc_id}/fifo"

# STOMP Destinations
STOMP_QUEUE_MESSAGES = "/user/queue/messages"
STOMP_QUEUE_PORTAL = "/user/queue/portal"
STOMP_SUBSCRIBE = "/app/subscribe"
STOMP_UNSUBSCRIBE = "/app/unsubscribe"

# Config keys
CONF_EMAIL = "email"
CONF_PASSWORD = "password"

# Signal strength thresholds
SIGNAL_LEVEL_EXCELLENT = 70  # > 70%
SIGNAL_LEVEL_GOOD = 50       # > 50%
SIGNAL_LEVEL_FAIR = 30       # > 30%
SIGNAL_LEVEL_POOR = 5        # > 5%

# Update interval for polling fallback (seconds)
UPDATE_INTERVAL = 60
