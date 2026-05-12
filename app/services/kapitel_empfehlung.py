from __future__ import annotations
from collections import defaultdict

from sqlalchemy.orm import Session

from app.models.aufgabe import AfbNiveau


def klassen_kompetenzprofil(klasse_id: int, db: Session) -> dict[int, float]:
    """Durchschnittlicher Kompetenz-Score aller aktiven Schüler der Klasse."""
    from app.models.schueler import Schueler
    from app.services.kompetenzprofil import berechne_profil

    schueler = (
        db.query(Schueler)
        .filter(Schueler.klasse_id == klasse_id, Schueler.geloescht_am.is_(None))
        .all()
    )
    sammel: dict[int, list[float]] = defaultdict(list)
    for s in schueler:
        for k_id, score in berechne_profil(s.id, db).items():
            sammel[k_id].append(score)
    return {k: round(sum(v) / len(v), 1) for k, v in sammel.items()}


def klassen_afb_profil(klasse_id: int, db: Session) -> dict[AfbNiveau, float]:
    """Durchschnittlicher Prozent-Score pro AFB-Niveau aus allen detaillierten Tests."""
    from app.models.schriftliche_leistung import SchriftlicheLeistung
    from app.models.schueler_ergebnis import SchuelerErgebnis

    leistungen = (
        db.query(SchriftlicheLeistung)
        .filter(SchriftlicheLeistung.klasse_id == klasse_id, SchriftlicheLeistung.detailliert.is_(True))
        .all()
    )
    sammel: dict[AfbNiveau, list[float]] = defaultdict(list)
    for l in leistungen:
        for la in l.leistung_aufgaben:
            if la.aufgabe.max_punkte <= 0:
                continue
            afb = la.aufgabe.afb_niveau
            for e in db.query(SchuelerErgebnis).filter(
                SchuelerErgebnis.leistung_aufgabe_id == la.id,
                SchuelerErgebnis.erreichte_punkte.isnot(None),
            ).all():
                sammel[afb].append(e.erreichte_punkte / la.aufgabe.max_punkte * 100)
    return {afb: round(sum(v) / len(v), 1) for afb, v in sammel.items()}


def ziel_afb(afb_profil: dict) -> list[AfbNiveau]:
    """Ziel-AFB-Niveau basierend auf Klassenperformance."""
    if not afb_profil:
        return [AfbNiveau.AFB_I, AfbNiveau.AFB_II]
    avg = sum(afb_profil.values()) / len(afb_profil)
    if avg < 40:
        return [AfbNiveau.AFB_I]
    if avg < 70:
        return [AfbNiveau.AFB_I, AfbNiveau.AFB_II]
    return [AfbNiveau.AFB_I, AfbNiveau.AFB_II, AfbNiveau.AFB_III]


def empfehlungen_fuer_kapitel(
    klasse_id: int,
    kapitel: str,
    uk_anzahl: dict[str, int],   # {unterkapitel: n}
    db: Session,
    schwelle_schwach: float = 60.0,
) -> tuple[dict, dict, dict, list[AfbNiveau]]:
    """
    Gibt zurück:
      ergebnis    {unterkapitel: [Buchaufgabe, ...]}
      komps       {kompetenz_id: score}
      afb_profil  {AfbNiveau: score}
      ziel        [AfbNiveau, ...]
    """
    from app.models.buchaufgabe import Buchaufgabe, BuchaufgabeKompetenz
    from app.models.kompetenz import Kompetenz

    komps = klassen_kompetenzprofil(klasse_id, db)
    afb_profil = klassen_afb_profil(klasse_id, db)
    ziel = ziel_afb(afb_profil)

    schwach_k_ids = {k_id for k_id, score in komps.items() if score < schwelle_schwach}

    ergebnis: dict[str, list] = {}

    for uk, anzahl in uk_anzahl.items():
        if anzahl <= 0:
            continue

        kandidaten = (
            db.query(Buchaufgabe)
            .filter(Buchaufgabe.kapitel == kapitel, Buchaufgabe.unterkapitel == uk)
            .all()
        )

        scored = []
        for ba in kandidaten:
            ba_k_ids = {bak.kompetenz_id for bak in ba.kompetenzen}
            komp_match = len(ba_k_ids & schwach_k_ids)
            afb_match = 1 if ba.afb_niveau in ziel else 0
            mfp_bonus = 1 if ba.minimalfahrplan else 0
            score = ba.wichtigkeit * 10 + komp_match * 6 + afb_match * 3 + mfp_bonus
            scored.append((score, ba.id, ba))

        scored.sort(key=lambda x: -x[0])
        ergebnis[uk] = [ba for _, _, ba in scored[:anzahl]]

    return ergebnis, komps, afb_profil, ziel
