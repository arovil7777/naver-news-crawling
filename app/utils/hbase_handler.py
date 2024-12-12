import happybase
from app.config import Config, logger


class HBaseConnector:
    def __init__(self, host=Config.HBASE_HOST, port=Config.HBASE_PORT):
        # HBase 연결 설정
        try:
            self.connection = happybase.Connection(host=host, port=port)
            self.connection.open()
            logger.info(f"HBase 연결 성공: {host}:{port}")
        except Exception as e:
            logger.critical(f"HBase 연결 실패: {e}")
            raise

    def get_table(self, table_name):
        # HBase 테이블 객체 반환
        return self.connection.table(table_name)

    def close_connection(self):
        # HBase 연결 종료
        self.connection.close()
        logger.info("HBase 연결 종료")
