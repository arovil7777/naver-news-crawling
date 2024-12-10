from app.templates.templates import TEMPLATES


def get_template(url):
    for template in TEMPLATES:
        if template["site"] in url:
            return template
    return None
