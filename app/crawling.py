from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import parmap
import re
import traceback
from multiprocessing import Pool, cpu_count
from app.templates.template_select import get_content_template, get_list_template
from app.config import logger
from datetime import datetime
from tqdm import tqdm


# 템플릿 캐시를 위한 전역 변수
template_cache = {}


def setup_driver():
    # Selenium WebDriver 설정
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disabled-dev-shm-usage")
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")

    return webdriver.Chrome(options=chrome_options)


def parse_date(date_str):
    # 문자열로 된 날짜를 datetime으로 변환
    if not date_str:
        return None

    formats = ["%Y.%m.%d. %p %I:%M", "%Y-%m-%d %H:%M:%S"]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    # logger.error(f"지원하지 않는 날짜 형식: {date_str}")
    raise Exception(f"지원하지 않는 날짜 형식: {date_str}")
    # return None


def get_template_with_cache(cache_key, fetch_function, *args):
    # 캐시를 활용한 템플릿 조회
    if cache_key in template_cache:
        return template_cache[cache_key]

    template = fetch_function(*args)
    if template:
        template_cache[cache_key] = template
    return template


def crawl_article_content_with_driver(article):
    # 기사 본문 크롤링
    url = article["url"]
    article_data = {"url": url}
    driver = setup_driver()

    try:
        driver.get(url)
        content_url = driver.current_url

        # 기사 본문 템플릿 호출
        # template = get_content_template(content_url)
        template = get_template_with_cache(
            content_url, get_content_template, content_url
        )
        if not template:
            logger.error(f"템플릿을 찾을 수 없습니다: {url}")
            return article_data

        if template["article_id_selector"]:
            article_id = driver.execute_script(template["article_id_selector"])
        else:
            match = re.search(r"/article(?:/\d+)?/(\d+)", content_url)
            if match:
                article_id = match.group(1)
            else:
                article_id = None
                deleted_msg = driver.find_element(
                    By.CLASS_NAME, "erms_h"
                ).get_attribute("textContent")
                raise Exception(f"{deleted_msg}")

        content_element = WebDriverWait(driver, 3).until(
            EC.presence_of_element_located(
                (By.CLASS_NAME, template["content_selector"])
            )
        )
        content = content_element.find_element(By.TAG_NAME, "article").text

        writer = next(
            (
                driver.find_element(By.CLASS_NAME, sel).text
                for sel in template["writer_selector"]
                if driver.find_elements(By.CLASS_NAME, sel)
            ),
            "작성자 정보 없음",
        )

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
        logger.error(f"에러 스택 트레이스: {traceback.format_exc()}")
    finally:
        driver.quit()

    return article_data


# def parallel_crawl_article_content(articles):
#     # 멀티프로세싱으로 기사 본문 크롤링
#     logger.info(f"총 {len(articles)}개의 기사 본문 크롤링 시작.")

#     # CPU 사용량 조정
#     num_workers = min(len(articles), cpu_count() * 2)  # CPU 코어 수의 2배로 설정
#     logger.info(f"기사 본문 크롤링 워커 수: {num_workers}")

#     results = parmap.map(
#         crawl_article_content_with_driver,
#         articles,
#         pm_pbar=True,
#         pm_processes=num_workers,
#     )
#     logger.info("기사 본문 크롤링 완료")
#     return results


def parallel_crawl_article_content(articles):
    # 멀티 프로세싱으로 기사 본문 크롤링
    logger.info(f"총 {len(articles)}개의 기사 본문 크롤링 시작.")

    # CPU 사용량 조정 (CPU 코어 수의 2배 또는 기사 수 중 최소값)
    num_workers = min(len(articles), cpu_count() * 2)
    logger.info(f"기사 본문 크롤링 워커 수: {num_workers}")

    results = []
    try:
        # 멀티 프로세싱 Pool 생성
        with Pool(processes=num_workers) as pool:
            results = list(
                tqdm(
                    pool.imap_unordered(crawl_article_content_with_driver, articles),
                    total=len(articles),
                    desc="기사 본문 크롤링 진행 중",
                    colour="green",
                )
            )
    except Exception as e:
        logger.error(f"멀티 프로세싱 중 에러 발생: {e}")
    finally:
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

            if name == "랭킹":
                url = url + f"?date={datetime.now().strftime('%Y%m%d')}"

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

        if "ranking" in category["url"]:
            sub_category_urls.append({"name": "랭킹", "url": category["url"]})

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
        colour="green",
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
    for result in tqdm(
        results, desc="모든 카테고리 크롤링", unit="카테고리", colour="green"
    ):
        all_articles.extend(result)

    return all_articles


def crawl_articles(driver, url):
    # 뉴스 기사 목록 크롤링
    driver.get(url)

    articles = []
    try:
        # 기사 목록 템플릿 호출
        # template = get_list_template(url)
        template = get_template_with_cache(url, get_list_template, url)

        # 로딩 대기
        WebDriverWait(driver, 2).until(
            EC.presence_of_element_located(
                (By.CLASS_NAME, template["news_list_selector"])
            )
        )

        # 카테고리 정보 추출
        category1 = driver.find_element(
            By.CSS_SELECTOR, template["category1_selector"]
        ).get_attribute("textContent")
        category2 = (
            driver.find_element(
                By.CSS_SELECTOR, template["category2_selector"]
            ).get_attribute("textContent")
            if template["category2_selector"]
            else None
        )

        # 뉴스 더보기 버튼 클릭 로직
        while True:
            try:
                # 뉴스 더보기 버튼 찾기
                load_more_button = WebDriverWait(driver, 3).until(
                    EC.presence_of_element_located(
                        (By.CLASS_NAME, template["load_more_selector"])
                    )
                )

                # 뉴스 더보기 버튼 클릭
                load_more_button.click()

                # 로드된 컨텐츠 대기
                WebDriverWait(driver, 2).until(
                    EC.presence_of_element_located(
                        (By.CLASS_NAME, template["news_list_selector"])
                    )
                )

                logger.debug("'뉴스 더보기' 버튼 클릭")
            except Exception as e:
                break

        # 기사 요소 찾기
        articles_elements = driver.find_elements(
            By.CLASS_NAME, template["article_selector"]
        )
        site = driver.title.replace(" ", "").split(":")[1]

        for idx, element in enumerate(articles_elements, start=1):
            try:
                articles.append(
                    {
                        "site": site,
                        "title": element.find_element(
                            By.CLASS_NAME, template["title_selector"]
                        ).text,
                        "summary": (
                            element.find_element(
                                By.CLASS_NAME, template["summary_selector"]
                            ).get_attribute("textContent")
                            if template["summary_selector"]
                            else None
                        ),
                        "url": element.find_element(
                            By.TAG_NAME, template["url_selector"]
                        ).get_attribute("href"),
                        "publisher": element.find_element(
                            By.CSS_SELECTOR, template["publisher_selector"]
                        ).get_attribute("textContent"),
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
