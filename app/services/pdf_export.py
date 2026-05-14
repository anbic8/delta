from __future__ import annotations

from jinja2 import Environment, FileSystemLoader


def _jinja_env() -> Environment:
    from app.templates_config import punkte_marker, afb_label  # noqa: F401
    env = Environment(loader=FileSystemLoader("templates"), autoescape=True)
    env.filters["punkte_marker"] = punkte_marker
    env.filters["afb_label"] = afb_label
    return env


def kapitel_empfehlung_pdf(context: dict) -> bytes:
    """PDF für die Klassen-Kapitel-Empfehlung."""
    import weasyprint
    html = _jinja_env().get_template("pdf_kapitel_empfehlung.html").render(**context)
    return weasyprint.HTML(string=html, base_url=".").write_pdf()


def ehz_pdf(context: dict) -> bytes:
    """PDF mit Aufgaben + Erwartungshorizont (EHZ) für eine SchriftlicheLeistung."""
    import weasyprint
    html = _jinja_env().get_template("pdf_ehz.html").render(**context)
    return weasyprint.HTML(string=html, base_url=".").write_pdf()


def empfehlung_pdf(items: list[dict]) -> bytes:
    """
    items: list of {"schueler": ..., "klasse": ..., "leistung": ..., "bloecke": ...}
    Gibt PDF-Bytes zurück (eine Seite pro Schüler).
    """
    import weasyprint

    html = _jinja_env().get_template("pdf_empfehlung.html").render(items=items)
    return weasyprint.HTML(string=html, base_url=".").write_pdf()
