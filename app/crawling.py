from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import parmap
import re
import traceback
from multiprocessing import Pool, cpu_count
from app.templates.template_select import get_template
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


def parse_date(date_str):
    if not date_str:
        return

    formats = ["%Y.%m.%d. %p %I:%M", "%Y-%m-%d %H:%M:%S"]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"지원하지 않는 날짜 형식: {date_str}")


def crawl_article_content_with_driver(article):
    # 독립적인 WebDriver를 사용해 기사 본문 크롤링
    url = article["url"]
    driver = setup_driver()
    article_data = {"url": url}

    try:
        driver.get(url)
        content_url = driver.current_url
        template = get_template(content_url)

        if not template:
            logger.error(f"템플릿을 찾을 수 없습니다: {url}")
            return article_data

        article_id = driver.execute_script(template["article_id_selector"])
        if not article_id:
            match = re.search(r"/article(?:/\d+)?/(\d+)", content_url)
            if match:
                article_id = match.group(1)

        content_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (By.CLASS_NAME, template["content_selector"])
            )
        )
        content = content_element.find_element(By.TAG_NAME, "article").get_attribute(
            "textContent"
        )

        writer = "작성자 정보 없음"
        for writer_selector in template["writer_selector"]:
            writer_elements = driver.find_elements(By.CLASS_NAME, writer_selector)
            if writer_elements:
                writer = writer_elements[0].text
                break

        date_elements = driver.find_elements(By.CLASS_NAME, template["date_selector"])
        for date in date_elements:
            date_element = (
                date.find_elements(By.TAG_NAME, "span")
                if template["site"] == "n.news.naver.com"
                else date.find_elements(By.TAG_NAME, "em")
            )
            published_at = (
                date_element[0]
                .get_attribute(template["date_attribute"])
                .replace("오전", "AM")
                .replace("오후", "PM")
            )
            updated_at = (
                date_element[1]
                .get_attribute(template["updated_attribute"])
                .replace("오전", "AM")
                .replace("오후", "PM")
                if len(date_element) > 1
                else None
            )

        article_data.update(
            {
                "article_id": article_id,
                "content": content,
                "writer": writer,
                "published_at": parse_date(published_at),
                "updated_at": parse_date(updated_at),
            }
        )
    except Exception as e:
        logger.error(f"기사 본문 수집 중 에러 발생 {url}: {e}")
        logger.debug(f"전체 에러 스택 트레이스: {traceback.format_exc()}")
    finally:
        driver.quit()

    return article_data


def parallel_crawl_article_content(articles):
    # 멀티프로세싱으로 기사 본문 크롤링
    logger.info(f"총 {len(articles)}개의 기사 본문 크롤링 시작.")
    results = parmap.map(crawl_article_content_with_driver, articles, pm_pbar=True)
    logger.info("기사 본문 크롤링 완료")
    return results


def collect_category_urls(driver, base_url):
    # 상위 카테고리 탐색
    driver.get(base_url)
    categories = driver.find_elements(By.CSS_SELECTOR, "li.Nlist_item > a")

    category_urls = []
    for idx, category in enumerate(categories):
        try:
            # 정치 ~ 랭킹 카테고리만 조회
            if idx == 0 or idx > 7:
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
    logger.info(f"크롤링 시작: {category['name']}")
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
    cpu_count_adjusted = max(1, cpu_count() - 2)
    logger.info(f"멀티 프로세싱 CPU 코어 개수: {cpu_count_adjusted} / {cpu_count()}")
    with Pool(processes=cpu_count_adjusted) as pool:
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
