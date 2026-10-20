"""Agent configuration — read from env, never print secrets."""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
GITHUB_PUSH_TOKEN = os.environ.get("GITHUB_PUSH_TOKEN", "")
GITHUB_USER = os.environ.get("GITHUB_USER", "qezawat-a")

# Bitunix (trader engine uses these; never printed)
BITUNIX_API_KEY = os.environ.get("BITUNIX_API_KEY", "")
BITUNIX_SECRET_KEY = os.environ.get("BITUNIX_SECRET_KEY", "")
BITUNIX_BASE_URL = os.environ.get("BITUNIX_BASE_URL", "https://fapi.bitunix.com")

# Model gateway
NINEROUTER_URL = os.environ.get("NINEROUTER_URL", "")
NINEROUTER_KEY = os.environ.get("NINEROUTER_KEY", "")

# Runtime toggles
AUTO_APPROVE_ON_EDIT = os.environ.get("DAN_AUTO_APPROVE_ON_EDIT", "0") == "1"
LEARNING = os.environ.get("DAN_LEARNING", "1") == "1"

# Telegram: only respond to this chat id if set (0 = everyone)
ALLOWED_CHAT_ID = os.environ.get("DAN_CHAT_ID", "0")