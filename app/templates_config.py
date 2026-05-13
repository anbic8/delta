import re
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")


def punkte_marker(text: str) -> str:
    """Ersetzt [1P], [2P], [0.5P] etc. durch einen roten Haken-Badge."""
    if not text:
        return text or ""
    return re.sub(
        r"\[(\d+(?:[,.]?\d+)?P)\]",
        r'<span style="color:#c1121f;font-weight:bold;font-size:.85em;'
        r'background:#fde8e8;padding:.1em .35em;border-radius:.25em;'
        r'white-space:nowrap;">✓ \1</span>',
        str(text),
    )


templates.env.filters["punkte_marker"] = punkte_marker
