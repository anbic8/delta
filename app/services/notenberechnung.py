from sqlalchemy.orm import Session

ABITURSCHLUESSEL = [(85, 1), (70, 2), (55, 3), (40, 4), (20, 5)]


def punkte_zu_note(erreicht: float, max_punkte: float) -> int:
    if max_punkte <= 0:
        return 6
    prozent = erreicht / max_punkte * 100
    for grenze, note in ABITURSCHLUESSEL:
        if prozent >= grenze:
            return note
    return 6


def ist_grenzfall(erreicht: float, max_punkte: float) -> bool:
    aktuelle_note = punkte_zu_note(erreicht, max_punkte)
    if aktuelle_note == 1:
        return False
    naechste_note = aktuelle_note - 1
    for grenze, note in ABITURSCHLUESSEL:
        if note == naechste_note:
            schwelle = grenze / 100 * max_punkte
            return 0 < schwelle - erreicht <= 0.5
    return False


def note_fuer_schriftliche_leistung(schueler_id: int, leistung_id: int, db: Session) -> float | None:
    from app.models.schriftliche_leistung import SchriftlicheLeistung
    from app.models.schueler_ergebnis import SchuelerErgebnis

    leistung = db.get(SchriftlicheLeistung, leistung_id)
    if leistung is None:
        return None

    if leistung.detailliert:
        la_ids = [la.id for la in leistung.leistung_aufgaben]
        if not la_ids:
            return None
        ergebnisse = (
            db.query(SchuelerErgebnis)
            .filter(
                SchuelerErgebnis.schueler_id == schueler_id,
                SchuelerErgebnis.leistung_aufgabe_id.in_(la_ids),
            ).all()
        )
        if not ergebnisse:
            return None
        summe = sum(e.erreichte_punkte for e in ergebnisse if e.erreichte_punkte is not None)
        max_p = sum(la.aufgabe.max_punkte for la in leistung.leistung_aufgaben)
        return float(punkte_zu_note(summe, max_p))
    else:
        ergebnis = (
            db.query(SchuelerErgebnis)
            .filter(
                SchuelerErgebnis.schueler_id == schueler_id,
                SchuelerErgebnis.schriftliche_leistung_id == leistung_id,
            ).first()
        )
        return ergebnis.pauschalnote if ergebnis else None
