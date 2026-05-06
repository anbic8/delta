from sqlalchemy.orm import Session


def berechne_profil(schueler_id: int, db: Session) -> dict[int, float]:
    """Gibt {kompetenz_id: prozent} für alle Kompetenzen mit Daten zurück."""
    from app.models.schueler_ergebnis import SchuelerErgebnis

    ergebnisse = (
        db.query(SchuelerErgebnis)
        .filter(
            SchuelerErgebnis.schueler_id == schueler_id,
            SchuelerErgebnis.leistung_aufgabe_id.isnot(None),
        ).all()
    )

    scores: dict[int, list[tuple[float, float]]] = {}
    for ergebnis in ergebnisse:
        la = ergebnis.leistung_aufgabe
        aufgabe = la.aufgabe
        if aufgabe.max_punkte <= 0 or ergebnis.erreichte_punkte is None:
            continue
        anteil = ergebnis.erreichte_punkte / aufgabe.max_punkte
        for ak in aufgabe.kompetenzen:
            scores.setdefault(ak.kompetenz_id, []).append((anteil, ak.gewichtung))

    return {
        k_id: round(sum(s * w for s, w in vals) / sum(w for _, w in vals) * 100, 1)
        for k_id, vals in scores.items()
    }


def metadaten(schueler_id: int, db: Session) -> dict[str, int]:
    from app.models.schueler import Schueler
    from app.models.schriftliche_leistung import SchriftlicheLeistung, LeistungAufgabe
    from app.models.schueler_ergebnis import SchuelerErgebnis

    schueler = db.get(Schueler, schueler_id)
    if not schueler:
        return {"leistungen_mit_daten": 0, "leistungen_gesamt": 0}

    gesamt = (
        db.query(SchriftlicheLeistung)
        .filter(SchriftlicheLeistung.klasse_id == schueler.klasse_id, SchriftlicheLeistung.detailliert.is_(True))
        .count()
    )
    mit_daten = (
        db.query(SchriftlicheLeistung)
        .join(LeistungAufgabe, SchriftlicheLeistung.id == LeistungAufgabe.leistung_id)
        .join(SchuelerErgebnis, SchuelerErgebnis.leistung_aufgabe_id == LeistungAufgabe.id)
        .filter(SchuelerErgebnis.schueler_id == schueler_id)
        .distinct()
        .count()
    )
    return {"leistungen_mit_daten": mit_daten, "leistungen_gesamt": gesamt}
