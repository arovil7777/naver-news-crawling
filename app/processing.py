from app.database import MongoDBConnector


def save_articles_to_db(data, collection_name="crawling_contents"):
    # 크롤링된 기사를 MongoDB에 저장
    db = MongoDBConnector()
    collection = db.get_collection(collection_name)

    for item in data:
        # 중복 방지 (기사 url)
        if not collection.find_one({"url": item["url"]}):
            collection.insert_one(item)

    db.close_connection()
    print(f"{len(data)}개의 데이터 저장 완료")
