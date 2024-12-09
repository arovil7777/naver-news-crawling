from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from multiprocessing import Pool, cpu_count
from app.config import logger
from datetime import datetime
from tqdm import tqdm


def setup_driver():
    # Selenium WebDriver 설정
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disabled-dev-shm-usage")
    chrome_options.add_argument(
        "--headless"
    )  # 헤드리스 모드 (브라우저가 뜨지 않고 실행)
    chrome_options.add_argument("--disable-gpu")

    driver = webdriver.Chrome(options=chrome_options)
    return driver


def crawl_article_content_with_driver(article):
    # 독립적인 WebDriver를 사용해 기사 본문 크롤링
    url = article["url"]
    driver = setup_driver()
    article_data = {"url": url}

    try:
        driver.get(url)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "newsct_wrapper"))
        )

        content_element = driver.find_element(By.CLASS_NAME, "newsct_wrapper")
        content = content_element.find_element(By.TAG_NAME, "article").text
        writer = "작성자 정보 없음"

        for class_name in ["media_and_head_jounalist_name", "byline_p"]:
            elements = content_element.find_elements(By.CLASS_NAME, class_name)
            if elements:
                writer = elements[0].text
                break

        published_at = content_element.find_element(
            By.CLASS_NAME, "_ARTICLE_DATE_TIME"
        ).get_attribute("data-date-time")
        updated_at_element = content_element.find_elements(
            By.CLASS_NAME, "_ARTICLE_MODIFY_DATE_TIME"
        )

        article_data.update(
            {
                "article_id": driver.execute_script("return article.articleId"),
                "content": content,
                "writer": writer,
                "published_at": datetime.strptime(published_at, "%Y-%m-%d %H:%M:%S"),
                "updated_at": (
                    datetime.strptime(
                        updated_at_element[0].get_attribute("data-modify-date-time"),
                        "%Y-%m-%d %H:%M:%S",
                    )
                    if updated_at_element
                    else None
                ),
            }
        )
    except Exception as e:
        logger.error(f"기사 본문 수집 중 에러 발생 {url}: {e}")
    finally:
        driver.quit()

    return article_data


def parallel_crawl_article_content(articles):
    # 멀티프로세싱으로 기사 본문 크롤링
    logger.info(f"총 {len(articles)}개의 기사 본문 크롤링 시작.")
    results = []

    cpuCount = cpu_count() - 2
    logger.info(f"멀티 프로세싱 CPU 코어 개수: {cpuCount} / {cpu_count()}\n")
    with Pool(processes=cpuCount) as pool:
        for result in tqdm(
            pool.imap_unordered(crawl_article_content_with_driver, articles),
            total=len(articles),
            desc="기사 본문 크롤링 진행",
            unit="기사",
        ):
            results.append(result)
    logger.info("\n기사 본문 크롤링 완료")
    return results


def collect_category_urls(driver, base_url):
    # 상위 카테고리 탐색
    driver.get(base_url)
    categories = driver.find_elements(By.CSS_SELECTOR, "li.Nlist_item > a")

    category_urls = []
    for idx, category in enumerate(categories):
        try:
            # 정치 ~ 랭킹 카테고리만 조회
            if idx == 0 or idx > 1:
                continue

            # 상위 카테고리 정보 수집
            url = category.get_attribute("href")
            name = category.text

            category_urls.append({"name": name, "url": url})
        except Exception as e:
            logger.error(f"카테고리 수집 에러: {e}")

    logger.info(f"{len(category_urls)}개 카테고리 수집")
    return category_urls


def collect_sub_category_urls(driver, category):
    sub_category_urls = []

    try:
        # 상위 카테고리 페이지로 이동
        driver.get(category["url"])

        # 하위 카테고리 탐색
        sub_categories = driver.find_elements(By.CSS_SELECTOR, "li.ct_snb_nav_item > a")

        for sub_category in sub_categories:
            sub_url = (
                sub_category.get_attribute("href")
                + f"?date={datetime.now().strftime('%Y%m%d')}"
            )
            sub_name = sub_category.get_attribute("textContent")

            sub_category_urls.append({"name": sub_name, "url": sub_url})
    except Exception as e:
        logger.error(f"하위 카테고리 수집 에러 {category['name']}: {e}")

    return sub_category_urls


def crawl_category_articles(category):
    driver = setup_driver()
    logger.info(f"크롤링 시작: {category['name']}\n")
    sub_categories = collect_sub_category_urls(driver, category)

    all_articles = []
    for sub_category in tqdm(
        sub_categories,
        desc=f"{category['name']} 하위 카테고리 크롤링",
        unit="하위 카테고리",
    ):
        articles = crawl_articles(driver, sub_category["url"])
        all_articles.extend(articles)

    driver.quit()  # 작업 완료 후 driver 종료
    return all_articles


def crawl_all_categories(driver, base_url):
    # 상위 카테고리 수집
    categories = collect_category_urls(driver, base_url)

    all_articles = []
    cpuCount = cpu_count() - 2
    with Pool(processes=cpuCount) as pool:
        results = pool.starmap(
            crawl_category_articles, [(category,) for category in categories]
        )

    # 각 카테고리에서 수집한 기사 병합
    for result in tqdm(results, desc="모든 카테고리 크롤링", unit="카테고리"):
        all_articles.extend(result)

    return all_articles


def crawl_articles(driver, url):
    # 뉴스 기사 목록 크롤링
    driver.get(url)

    articles = []
    try:
        # 뉴스 더보기 버튼 클릭 로직
        while True:
            try:
                # 뉴스 더보기 버튼 찾기
                load_more_button = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "section_more"))
                )

                # 뉴스 더보기 버튼 클릭
                load_more_button.click()

                # 로드된 컨텐츠 대기
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CLASS_NAME, "newsct_wrapper"))
                )

                logger.debug("'뉴스 더보기' 버튼 클릭")
            except Exception as e:
                break

        # 로딩 대기
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "newsct_wrapper"))
        )

        # 카테고리 정보 추출
        category1 = driver.find_element(
            By.CSS_SELECTOR, "li.Nlist_item.is_active > a > span"
        ).text
        category2 = driver.find_element(
            By.CSS_SELECTOR, "li.ct_snb_nav_item.is_selected > a"
        ).get_attribute("textContent")

        # 기사 요소 찾기
        articles_elements = driver.find_elements(By.CSS_SELECTOR, ".sa_text")
        site = driver.title.replace(" ", "").split(":")[1]

        for idx, element in enumerate(articles_elements, start=1):
            try:
                articles.append(
                    {
                        "site": site,
                        "title": element.find_element(By.TAG_NAME, "strong").text,
                        "summary": element.find_element(
                            By.CLASS_NAME, "sa_text_lede"
                        ).get_attribute("textContent"),
                        "url": element.find_element(By.TAG_NAME, "a").get_attribute(
                            "href"
                        ),
                        "publisher": element.find_element(
                            By.CSS_SELECTOR, ".sa_text_press"
                        ).text,
                        "category1": category1,
                        "category2": category2,
                        "scraped_at": datetime.now(),
                    }
                )
            except Exception as e:
                logger.error(f"{category1} 기사 수집 중 에러 발생 {idx}: {e}")

    except Exception as e:
        logger.error(f"크롤링 중 에러 발생: {e}")

    return articles
