import os
from dotenv import load_dotenv
from datetime import datetime
import logging

# env 파일 로드
load_dotenv()

# 로그 폴더 경로
log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

log_file = os.path.join(log_dir, f"app_{datetime.now().strftime('%Y%m%d')}.log")


class Config:
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    DATABASE_NAME = os.getenv("DATABASE_NAME", "crawling_db")
    SELENIUM_DRIVER_PATH = os.getenv(
        "SELENIUM_DRIVER_PATH", "/usr/local/bin/chromedriver"
    )


# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(log_file, encoding="utf-8"), logging.StreamHandler()],
)

logger = logging.getLogger(__name__)
