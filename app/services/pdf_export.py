from __future__ import annotations

from jinja2 import Environment, FileSystemLoader


def _jinja_env() -> Environment:
    return Environment(loader=FileSystemLoader("templates"), autoescape=True)


def empfehlung_pdf(items: list[dict]) -> bytes:
    """
    items: list of {"schueler": ..., "klasse": ..., "leistung": ..., "bloecke": ...}
    Gibt PDF-Bytes zurück (eine Seite pro Schüler).
    """
    import weasyprint

    html = _jinja_env().get_template("pdf_empfehlung.html").render(items=items)
    return weasyprint.HTML(string=html, base_url=".").write_pdf()
