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


# Phase 4: weitere Quellen (kleine schriftliche LN) hier einhängen
_KLEINE_LN_QUELLEN: list[NoteQuelle] = [_muendliche_noten]


def schnitt_kleine_ln(schueler_id: int, db: Session) -> float | None:
    noten: list[tuple[float, float]] = []
    for quelle in _KLEINE_LN_QUELLEN:
        noten.extend(quelle(schueler_id, db))
    return berechne_gewichteten_schnitt(noten)


def schnitt_grosse_ln(schueler_id: int, db: Session) -> float | None:
    # Phase 4
    return None


def gesamtschnitt(schueler_id: int, db: Session) -> float | None:
    kl = schnitt_kleine_ln(schueler_id, db)
    gr = schnitt_grosse_ln(schueler_id, db)
    if kl is None or gr is None:
        return None
    return round((2 * gr + kl) / 3, 2)
