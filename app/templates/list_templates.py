# 기사 목록 페이지 템플릿 정의
LIST_TEMPLATES = [
    {
        "section": "section",
        "news_list_selector": "newsct_wrapper",
        "category1_selector": "li.Nlist_item.is_active > a > span",
        "category2_selector": "li.ct_snb_nav_item.is_selected > a",
        "load_more_selector": "section_more",
        "rank_selector": "",
        "article_selector": "sa_text",
        "title_selector": "sa_text_strong",
        "summary_selector": "sa_text_lede",
        "url_selector": "a",
        "publisher_selector": ".sa_text_press",
    },
    {
        "section": "ranking",
        "news_list_selector": "rankingnews_box_wrap",
        "category1_selector": "li.on > a > span.tx",
        "category2_selector": "li.on > a > span.tx",
        "load_more_selector": "button_rankingnews_more",
        "rank_selector": "list_ranking_num",
        "article_selector": "rankingnews_box",
        "title_selector": "list_title",
        "summary_selector": "",
        "url_selector": "a",
        "publisher_selector": ".rankingnews_name",
    },
]
