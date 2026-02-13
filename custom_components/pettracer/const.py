"""Constants for PetTracer integration."""

DOMAIN = "pettracer"

# API URLs
API_URL = "https://portal.pettracer.com/api"
WEBSOCKET_URL = "wss://pt.pettracer.com"

# API Endpoints
ENDPOINT_LOGIN = "/user/login"
ENDPOINT_USER_INFO = "/user/info" # Apprently not used!
ENDPOINT_CAT_COLLARS = "/map/getccs"
ENDPOINT_CC_LIST = "/user/details"  # Gets list of command centers (trackers)
ENDPOINT_CC_FIFO = "/cc/{cc_id}/fifo" # Apprently not used!
ENDPOINT_CC_INFO = "/map/getccinfo"
ENDPOINT_HOME_STATIONS = "/user/gethomestations"
ENDPOINT_SET_MODE = "/map/setccmode"
ENDPOINT_SET_LED_MODE = "/map/setccled"
ENDPOINT_SET_BUZZER_MODE = "/map/setccbuz"

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


COLLAR_MODES = {
    1: "Fast", #"TM_FAST_1",
    2: "Medium", #"TM_MEDIUM",
    3: "Slow", #"TM_SLOW",
    4: "Ultra Slow", #"TM_ULTRASLOW",
    5: "Test", #"TM_TEST",
    6: "Slow 3", #"TM_SLOW_3",
    7: "Slow 4", #"TM_SLOW_4",
    8: "Fast 2", #"TM_FAST_2",
    10: "Battery Low", #"TM_BATLOW",
    11: "Search mode", #"TM_SEARCH",
    12: "Turned off (need activating)", #"TM_OFF",
    14: "Normal 2", #"TM_NORMAL_2",
    18: "Peil 3", #"TM_PEIL_3",
    19: "Peil 4", #"TM_PEIL_4"
}