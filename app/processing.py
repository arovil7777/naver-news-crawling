import os
from app.utils.db_handler import MongoDBConnector
from app.utils.csv_handler import save_to_csv, load_from_csv
from app.utils.hdfs_handler import HDFSConnector
# from app.utils.hbase_handler import HBaseConnector
from app.config import Config, logger
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
        logger.info(f"로컬에 CSV 파일 저장 완료: {file_path}")
        return file_path
    except Exception as e:
        logger.error(f"CSV 저장 중 오류 발생: {e}")
        return None


def load_articles_to_csv(file_path):
    # CSV 파일에서 기사 데이터 로드
    try:
        return load_from_csv(file_path)
    except Exception as e:
        logger.error(f"CSV 로드 중 오류 발생: {e}")
        return []


def send_csv_to_hdfs(local_file_path):
    # CSV 데이터를 HDFS로 전송
    if not local_file_path:
        logger.error("유효하지 않은 파일 경로입니다.")
        return

    try:
        hdfs = HDFSConnector()

        hdfs_dir = Config.HDFS_DIR
        hdfs_file_path = os.path.join(hdfs_dir, os.path.basename(local_file_path))
        hdfs.upload_file(local_file_path, hdfs_file_path)
        logger.info(f"HDFS에 파일 업로드 완료: {hdfs_file_path}")
    except Exception as e:
        logger.error(f"HDFS 전송 중 오류 발생: {e}")


"""
# def send_csv_to_hbase(file_path, table_name):
#     # CSV 데이터를 HBase로 전송
#     try:
#         # CSV 데이터 로드
#         data = load_from_csv(file_path)
#         if not data:
#             logger.error("CSV 파일이 비어 있습니다.")
#             return

#         # HBase 연결
#         hbase = HBaseConnector()
#         table = hbase.get_table(table_name)

#         # 데이터 삽입
#         for idx, row in enumerate(data):
#             try:
#                 # 각 행을 HBase에 삽입
#                 row_key = row.get("url", f"row-{idx}")
#                 table.put(row_key, {f"info: {k}": str(v) for k, v in row.items()})
#             except Exception as e:
#                 logger.error(f"HBase에 데이터 삽입 실패 (row={row}): {e}")

#         logger.info(
#             f"{len(data)}개의 행을 HBase 테이블 '{table_name}'에 성공적으로 저장했습니다."
#         )
#     except Exception as e:
#         logger.error(f"HBase로 전송 중 에러 발생: {e}")
#     finally:
#         hbase.close_connection()
"""
