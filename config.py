import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN: str = os.environ["TELEGRAM_BOT_TOKEN"]
OPENROUTER_API_KEY: str = os.environ["OPENROUTER_API_KEY"]
OPENROUTER_MODEL: str = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini")
YTDLP_COOKIES_FILE: Optional[str] = os.environ.get("YTDLP_COOKIES_FILE")
