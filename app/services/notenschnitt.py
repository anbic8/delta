from typing import Callable
from sqlalchemy.orm import Session

NoteQuelle = Callable[[int, Session], list[tuple[float, float]]]


def berechne_gewichteten_schnitt(noten: list[tuple[float, float]]) -> float | None:
    if not noten:
        return None
    gesamt = sum(g for _, g in noten)
    return round(sum(n * g for n, g in noten) / gesamt, 2) if gesamt else None


def _muendliche_noten(schueler_id: int, db: Session) -> list[tuple[float, float]]:
    from app.models.muendliche_note import MuendlicheNote
    rows = (
        db.query(MuendlicheNote)
        .filter(MuendlicheNote.schueler_id == schueler_id, MuendlicheNote.geloescht_am.is_(None))
        .all()
    )
    return [(r.note, r.gewichtung) for r in rows]


def _schriftliche_noten_fuer_art(schueler_id: int, art, db: Session) -> list[tuple[float, float]]:
    from app.models.schueler import Schueler
    from app.models.schriftliche_leistung import SchriftlicheLeistung
    from app.services.notenberechnung import note_fuer_schriftliche_leistung

    schueler = db.get(Schueler, schueler_id)
    if not schueler:
        return []
    leistungen = (
        db.query(SchriftlicheLeistung)
        .filter(SchriftlicheLeistung.klasse_id == schueler.klasse_id, SchriftlicheLeistung.art == art)
        .all()
    )
    result = []
    for leistung in leistungen:
        note = note_fuer_schriftliche_leistung(schueler_id, leistung.id, db)
        if note is not None:
            result.append((note, leistung.gewichtung))
    return result


def _schriftliche_kleine_ln(schueler_id: int, db: Session) -> list[tuple[float, float]]:
    from app.models.schriftliche_leistung import LeistungArt
    return _schriftliche_noten_fuer_art(schueler_id, LeistungArt.kleiner_ln, db)


def _schriftliche_grosse_ln(schueler_id: int, db: Session) -> list[tuple[float, float]]:
    from app.models.schriftliche_leistung import LeistungArt
    return _schriftliche_noten_fuer_art(schueler_id, LeistungArt.schulaufgabe, db)


# Phase 4: schriftliche kleine LN als zweite Quelle eingehängt
_KLEINE_LN_QUELLEN: list[NoteQuelle] = [_muendliche_noten, _schriftliche_kleine_ln]


def schnitt_kleine_ln(schueler_id: int, db: Session) -> float | None:
    noten: list[tuple[float, float]] = []
    for quelle in _KLEINE_LN_QUELLEN:
        noten.extend(quelle(schueler_id, db))
    return berechne_gewichteten_schnitt(noten)


def schnitt_grosse_ln(schueler_id: int, db: Session) -> float | None:
    return berechne_gewichteten_schnitt(_schriftliche_grosse_ln(schueler_id, db))


def gesamtschnitt(schueler_id: int, db: Session) -> float | None:
    kl = schnitt_kleine_ln(schueler_id, db)
    gr = schnitt_grosse_ln(schueler_id, db)
    if kl is None or gr is None:
        return None
    return round((2 * gr + kl) / 3, 2)
