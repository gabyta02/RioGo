import os

from geonode.settings import *

SESSION_COOKIE_NAME = os.getenv("GEONODE_SESSION_COOKIE_NAME", "geonode_sessionid")
CSRF_COOKIE_NAME = os.getenv("GEONODE_CSRF_COOKIE_NAME", "geonode_csrftoken")

SESSION_COOKIE_PATH = "/"
CSRF_COOKIE_PATH = "/"
SESSION_COOKIE_DOMAIN = None
CSRF_COOKIE_DOMAIN = None

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
CSRF_TRUSTED_ORIGINS = [
    "https://riobambatour.org",
    "https://www.riobambatour.org",
]
