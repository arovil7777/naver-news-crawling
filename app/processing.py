import os
from app.utils.db_handler import MongoDBConnector
from app.utils.csv_handler import save_to_csv, load_from_csv
from app.config import logger
from datetime import datetime


def save_articles_to_db(data, collection_name="crawling_contents"):
    # 크롤링된 기사를 MongoDB에 저장
    db = MongoDBConnector()
    collection = db.get_collection(collection_name)

    try:
        for item in data:
            # 중복 방지 (기사 url)
            if not collection.find_one({"url": item["url"]}):
                collection.insert_one(item)

        logger.info(f"{len(data)}개의 데이터 저장 완료")
    except Exception as e:
        logger.error(f"MongoDB 저장 중 오류 발생: {e}")
    finally:
        db.close_connection()


def save_articles_to_csv(data):
    # 크롤링 기사를 CSV 파일로 저장
    data_dir = "data"
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)

    file_path = os.path.join(
        data_dir, f"articles_{datetime.now().strftime('%Y%m%d%H%M%S')}.csv"
    )
    try:
        save_to_csv(data, file_path)
    except Exception as e:
        logger.error(f"CSV 저장 중 오류 발생: {e}")


def load_articles_to_csv(file_path):
    # CSV 파일에서 기사 데이터 로드
    try:
        return load_from_csv(file_path)
    except Exception as e:
        logger.error(f"CSV 로드 중 오류 발생: {e}")
        return []
