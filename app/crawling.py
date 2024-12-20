from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime


def setup_driver(driver_path):
    # Selenium WebDriver 설정
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disabled-dev-shm-usage")
    chrome_options.add_argument("--headless")  # 헤드리스 모드 (브라우저가 뜨지 않고 실행)
    chrome_options.add_argument("--disable-gpu")

    driver = webdriver.Chrome(driver_path, options=chrome_options)
    return driver


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
            print(f"Error collecting category: {e}")

    return category_urls


def collect_sub_category_urls(driver, category):
    sub_category_urls = []

    try:
        # 상위 카테고리 페이지로 이동
        driver.get(category["url"])

        # 하위 카테고리 탐색
        sub_categories = driver.find_elements(By.CSS_SELECTOR, "li.ct_snb_nav_item > a")

        for sub_category in sub_categories:
            sub_url = (sub_category.get_attribute("href") + f"?date={datetime.now().strftime('%Y%m%d')}")
            sub_name = sub_category.get_attribute("textContent")

            sub_category_urls.append({"name": sub_name, "url": sub_url})
    except Exception as e:
        print(f"Error collecting sub categories for {category['name']}: {e}")

    return sub_category_urls


def crawl_all_categories(driver, base_url):
    # 상위 카테고리 수집
    print("상위 카테고리 수집 시작...")
    categories = collect_category_urls(driver, base_url)

    all_categories = []
    print("하위 카테고리 수집 중...")
    for category in categories:
        # "랭킹" 카테고리의 경우 하위 카테고리가 존재하지 않음
        if "ranking" in category["url"]:
            all_categories.append(category)
            continue

        # 하위 카테고리 수집
        sub_categories = collect_sub_category_urls(driver, category)

        for sub_category in sub_categories:
            articles = crawl_articles(driver, sub_category["url"])

        # 상위 카테고리와 하위 카테고리 병합
        # category["sub_categories"] = sub_categories
        # all_categories.append(category)

    # return all_categories
    return articles


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
            except Exception as e:
                break

        # 로딩 대기
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "newsct_wrapper"))
        )

        # 카테고리 정보 추출
        category1 = driver.find_element(By.CSS_SELECTOR, "li.Nlist_item.is_active > a > span").text
        category2 = driver.find_element(By.CSS_SELECTOR, "li.ct_snb_nav_item.is_selected > a").get_attribute("textContent")

        # 기사 요소 찾기
        articles_elements = driver.find_elements(By.CSS_SELECTOR, ".sa_text")
        site = driver.title.replace(" ", "").split(":")[1]

        for idx, element in enumerate(articles_elements, start=1):
            try:
                title = element.find_element(By.TAG_NAME, "strong").text
                summary = element.find_element(By.CLASS_NAME, "sa_text_lede").get_attribute("textContent")
                url = element.find_element(By.TAG_NAME, "a").get_attribute("href")
                publisher = element.find_element(By.CSS_SELECTOR, ".sa_text_press").text

                articles.append(
                    {
                        "site": site,
                        "title": title,
                        "summary": summary,
                        "url": url,
                        "publisher": publisher,
                        "category1": category1,
                        "category2": category2,
                        "scraped_at": datetime.now(),
                    }
                )
            except Exception as e:
                print(f"Error while processing articles {idx}: {e}")

    except Exception as e:
        print(f"Error during crawling: {e}")

    return articles


def crawl_article_content(driver, url):
    # 기사 본문 크롤링
    article_data = {}
    try:
        driver.get(url)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "newsct_wrapper"))
        )

        # 뉴스 기사 ID
        article_id = driver.execute_script("return article.articleId")
        content_element = driver.find_element(By.CLASS_NAME, "newsct_wrapper")

        content = content_element.find_element(By.TAG_NAME, "article").text
        writer = "작성자 정보 없음"
        for class_name in ["media_end_head_journalist_name", "byline_p"]:
            elements = content_element.find_elements(By.CLASS_NAME, class_name)
            if elements:
                writer = elements[0].text
                break

        published_at = content_element.find_element(By.CLASS_NAME, "_ARTICLE_DATE_TIME").get_attribute("data-date-time")
        updated_at_element = content_element.find_elements(By.CLASS_NAME, "_ARTICLE_MODIFY_DATE_TIME")

        article_data["article_id"] = article_id
        article_data["content"] = content
        article_data["writer"] = writer
        article_data["published_at"] = datetime.strptime(published_at, "%Y-%m-%d %H:%M:%S")
        if updated_at_element:
            updated_at = updated_at_element[0].get_attribute("data-modify-date-time")
            article_data["updated_at"] = datetime.strptime(updated_at, "%Y-%m-%d %H:%M:%S")
        else:
            article_data["updated_at"] = None

    except Exception as e:
        print(f"Error while processing article content at {url}: {e}")

    return article_data
