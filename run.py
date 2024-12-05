from app.crawling import setup_driver, crawl_articles, crawl_article_content
from app.processing import save_articles_to_db
from app.config import Config
from datetime import datetime


def main():
    print("크롤링을 시작합니다.")

    driver = setup_driver(Config.SELENIUM_DRIVER_PATH)

    article_list_url = (
        f"https://news.naver.com/breakingnews/section/100/264?date={datetime.now().strftime('%Y%m%d')}"  # 네이버 뉴스 (정치)
    )
    try:
        articles = crawl_articles(driver, article_list_url)

        for article in articles:
            content_data = crawl_article_content(driver, article["url"])
            article.update(content_data)

        if article:
            print(f"크롤링 완료. 총 {len(articles)}개의 기사 수집")

            # 데이터 저장
            save_articles_to_db(articles)

        else:
            print("크롤링 결과가 없습니다.")

        print("작업이 완료되었습니다.")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
