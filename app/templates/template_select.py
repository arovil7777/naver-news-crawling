from app.templates.content_templates import CONTENT_TEMPLATES
from app.templates.list_templates import LIST_TEMPLATES


def get_list_template(url):
    for template in LIST_TEMPLATES:
        if template["section"] in url:
            return template
    return None


def get_content_template(url):
    for template in CONTENT_TEMPLATES:
        if template["site"] in url:
            return template
    return None
