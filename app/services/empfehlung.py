from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.aufgabe import AfbNiveau
from app.schemas.empfehlung import EmpfehlungRead
from app.services.kompetenzprofil import berechne_profil


_AFB_LABEL = {
    AfbNiveau.AFB_I: "Grundniveau",
    AfbNiveau.AFB_II: "Aufbauniveau",
    AfbNiveau.AFB_III: "Vertiefungsniveau",
}


def _begruendung(score: float, ba, kompetenz, schwelle_sehr_schwach: float) -> str:
    kuerzel = kompetenz.kuerzel if kompetenz else "?"
    stufe = "sehr schwach" if score < schwelle_sehr_schwach else "schwach"
    afb = _AFB_LABEL.get(ba.afb_niveau, str(ba.afb_niveau))
    return (
        f"Kompetenz {kuerzel} ist {stufe} ({score:.0f} %). "
        f"{afb}-Aufgabe zur gezielten Förderung."
    )


def empfehlungen(
    schueler_id: int,
    db: Session,
    anzahl: int = 5,
    profil_override: dict[int, float] | None = None,
) -> list[EmpfehlungRead]:
    from app.config import settings
    from app.models.buchaufgabe import Buchaufgabe, BuchaufgabeKompetenz
    from app.models.kompetenz import Kompetenz

    schwelle_schwach = settings.empfehlung_schwelle_schwach
    schwelle_sehr_schwach = settings.empfehlung_schwelle_sehr_schwach
    max_pro_kapitel = settings.empfehlung_max_pro_kapitel

    profil = profil_override if profil_override is not None else berechne_profil(schueler_id, db)

    schwache = {k_id: score for k_id, score in profil.items() if score < schwelle_schwach}
    if not schwache:
        return []

    sorted_schwach = sorted(schwache.items(), key=lambda x: x[1])

    ergebnisse: list[EmpfehlungRead] = []
    kapitel_zaehler: dict[str, int] = {}
    gesehen_ids: set[int] = set()

    for k_id, score in sorted_schwach:
        if len(ergebnisse) >= anzahl:
            break

        if score < schwelle_sehr_schwach:
            ziel_afb = [AfbNiveau.AFB_I]
        else:
            ziel_afb = [AfbNiveau.AFB_I, AfbNiveau.AFB_II]

        kandidaten = (
            db.query(Buchaufgabe)
            .join(BuchaufgabeKompetenz)
            .filter(
                BuchaufgabeKompetenz.kompetenz_id == k_id,
                Buchaufgabe.afb_niveau.in_(ziel_afb),
            )
            .order_by(Buchaufgabe.wichtigkeit.desc(), Buchaufgabe.id)
            .all()
        )

        k_obj = db.get(Kompetenz, k_id)

        for ba in kandidaten:
            if len(ergebnisse) >= anzahl:
                break
            if ba.id in gesehen_ids:
                continue
            kapitel_key = f"{ba.buch}::{ba.kapitel}"
            if kapitel_zaehler.get(kapitel_key, 0) >= max_pro_kapitel:
                continue

            kapitel_zaehler[kapitel_key] = kapitel_zaehler.get(kapitel_key, 0) + 1
            gesehen_ids.add(ba.id)
            ergebnisse.append(
                EmpfehlungRead(
                    buchaufgabe_id=ba.id,
                    buch=ba.buch,
                    kapitel=ba.kapitel,
                    seite=ba.seite,
                    aufgabennummer=ba.aufgabennummer,
                    beschreibung=ba.beschreibung,
                    afb_niveau=ba.afb_niveau,
                    wichtigkeit=ba.wichtigkeit,
                    kompetenz_kuerzel=k_obj.kuerzel if k_obj else "?",
                    kompetenz_score=score,
                    begruendung=_begruendung(score, ba, k_obj, schwelle_sehr_schwach),
                )
            )

    return ergebnisse
