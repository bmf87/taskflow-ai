import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv("taskflow-ai.env"))

OROUTER_SRV_URL = os.getenv("OROUTER_SRV_URL", "https://bfavro73-oroutersrv.hf.space")
OROUTER_CLIENT_ID = os.getenv("OROUTER_CLIENT_ID")
OROUTER_CLIENT_SECRET = os.getenv("OROUTER_CLIENT_SECRET")
APP_ADMIN_SECRET = os.getenv("APP_ADMIN_SECRET")

DEFAULT_FREE_MODEL = "openrouter/free"

# Image paths
APP_LOGO_PATH = "ui/images/tfai_logo.png"
APP_ICON_PATH = "ui/images/tfai_ico.png"

IMAGE_LKP = ({
    "logo": APP_LOGO_PATH,
    "icon": APP_ICON_PATH,
})