import os
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def load_env_file(filepath: Path):
    """Fallback .env file loader using standard library if dotenv is not installed."""
    if not filepath.exists():
        return
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip("'\"")
                    if key not in os.environ:
                        os.environ[key] = val
    except Exception as e:
        print(f"[Config] Note: Could not load .env directly: {e}")


# Load environment variables
_env_path = Path(__file__).parent / ".env"
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=_env_path)
except ImportError:
    load_env_file(_env_path)


class Config:
    # Kilo AI Gateway Settings
    KILO_API_KEY = os.getenv(
        "KILO_API_KEY",
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJlbnYiOiJwcm9kdWN0aW9uIiwia2lsb1VzZXJJZCI6IjNhYTY0YWJiLTYyOWItNDU4Yy05MDk0LWRmMDA0YmFjZDQ4ZiIsImFwaVRva2VuUGVwcGVyIjoiMTBkMjA2NDQtNDljMy00MDZjLWIxOTktYjE4MTEwYzQ4MjhlIiwidmVyc2lvbiI6MywiaWF0IjoxNzg3MDk1MzMzLCJleHAiOjE5NDQ3NzUzMzN9.PnBR71HRHyp3dBbBDlRKbjNIezhHya8RthHuL4iHExs",
    )
    KILO_API_URL = os.getenv(
        "KILO_API_URL",
        "https://api.kilo.ai/api/gateway/chat/completions",
    )
    KILO_MODEL = os.getenv("KILO_MODEL", "stepfun/step-3.7-flash:free")

    # Novel Scraping Settings
    NOVEL_BASE_URL = os.getenv(
        "NOVEL_BASE_URL", "https://novelfire.net/book/reverend-insanity"
    )
    HTTP_REFERER = os.getenv("HTTP_REFERER", "https://novelfire.net")
    X_TITLE = os.getenv(
        "X_TITLE", "Reverend Insanity Literary Arabic Translator"
    )

    # Runtime and Execution Settings
    REQUEST_DELAY_SECONDS = float(os.getenv("REQUEST_DELAY_SECONDS", "20"))
    MAX_RETRIES = int(os.getenv("MAX_RETRIES", "5"))
    CHUNK_SIZE_PARAGRAPHS = int(os.getenv("CHUNK_SIZE_PARAGRAPHS", "100"))
    TIMEOUT_SECONDS = int(os.getenv("TIMEOUT_SECONDS", "90"))

    # Directory Paths
    BASE_DIR = Path(__file__).parent
    OUTPUT_DIR = BASE_DIR / os.getenv("OUTPUT_DIR", "output")
    RAW_EN_DIR = OUTPUT_DIR / "raw_en"
    TRANSLATED_AR_DIR = OUTPUT_DIR / "translated_ar"
    PROGRESS_FILE = OUTPUT_DIR / "progress.json"

    # Scraping Headers
    SCRAPER_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    # Kilo AI Gateway Headers
    @classmethod
    def get_api_headers(cls) -> dict:
        return {
            "Authorization": f"Bearer {cls.KILO_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": cls.HTTP_REFERER,
            "X-Title": cls.X_TITLE,
        }

    @classmethod
    def init_directories(cls):
        """Ensure all output directories exist."""
        cls.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        cls.RAW_EN_DIR.mkdir(parents=True, exist_ok=True)
        cls.TRANSLATED_AR_DIR.mkdir(parents=True, exist_ok=True)


# Initialize folders automatically on load
Config.init_directories()
