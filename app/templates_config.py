import re
from markupsafe import Markup, escape
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")


def punkte_marker(text) -> Markup:
    """Ersetzt [1P], [2P], [0.5P] etc. durch einen roten Haken-Badge.
    Gibt Markup zurück, damit autoescape in Jinja2-Umgebungen nicht erneut escaped."""
    if not text:
        return Markup("")
    # Escape HTML entities in the input first, then insert safe span HTML
    safe_text = str(escape(str(text)))
    result = re.sub(
        r"\[(\d+(?:[,.]?\d+)?P)\]",
        r'<span style="color:#c1121f;font-weight:bold;font-size:.85em;'
        r'background:#fde8e8;padding:.1em .35em;border-radius:.25em;'
        r'white-space:nowrap;">&#10003; \1</span>',
        safe_text,
    )
    return Markup(result)


templates.env.filters["punkte_marker"] = punkte_marker
