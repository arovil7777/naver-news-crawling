from app.crawling import (
    setup_driver,
    crawl_all_categories,
    parallel_crawl_article_content,
)
from app.processing import save_articles_to_db, save_articles_to_csv
from app.config import logger


def main():
    logger.info("크롤링을 시작합니다.")
    driver = setup_driver()

    article_list_url = "https://news.naver.com/"
    try:
        # 1. 카테고리 별로 기사 목록 크롤링
        articles = crawl_all_categories(driver, article_list_url)
        print("\n")
        logger.info(f"수집된 기사 총 개수: {len(articles)}")

        # 2. 각 기사의 본문 데이터 크롤링
        articles_with_content = parallel_crawl_article_content(articles)

        # 3. 크롤링 완료 후 데이터 병합
        for article, article_with_content in zip(articles, articles_with_content):
            # 본문, 작성자, 날짜 등 기존 article에 병합
            article.update(article_with_content)

        if articles:
            logger.info(f"크롤링 완료. 총 {len(articles)}개의 기사 수집")

            # 데이터 저장 (MongoDB 또는 CSV)
            save_articles_to_csv(articles)
            # save_articles_to_db(articles)
        else:
            logger.debug("크롤링 결과가 없습니다.")

        logger.info("작업이 완료되었습니다.")
    except Exception as e:
        logger.critical(f"예기치 못한 에러 발생: {e}")
    finally:
        driver.quit()
        logger.info("WebDriver 종료.")


if __name__ == "__main__":
    main()
