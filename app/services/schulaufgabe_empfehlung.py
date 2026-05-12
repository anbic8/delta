from __future__ import annotations
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.models.aufgabe import AfbNiveau


@dataclass
class BuchaufgabeMatch:
    buchaufgabe_id: int
    buch: str
    kapitel: str
    unterkapitel: str
    aufgabennummer: str
    beschreibung: str | None
    afb_niveau: str
    wichtigkeit: int
    match_grund: str


@dataclass
class AufgabeBlock:
    la_nr: str                  # Aufgabennummer im Test (z.B. "1a")
    titel: str
    max_punkte: float
    erreicht: float | None      # None = nicht eingetragen
    prozent: float | None
    voll: bool                  # 100 % erreicht → keine Empfehlung
    empfehlungen: list[BuchaufgabeMatch] = field(default_factory=list)


def _ziel_afb(prozent: float | None, aufgabe_afb: AfbNiveau) -> list[AfbNiveau]:
    if prozent is None or prozent < 40:
        return [AfbNiveau.AFB_I]
    if prozent < 70:
        return [AfbNiveau.AFB_I, AfbNiveau.AFB_II]
    # 70-99 %: gleiches Niveau üben
    reihenfolge = [AfbNiveau.AFB_I, AfbNiveau.AFB_II, AfbNiveau.AFB_III]
    idx = reihenfolge.index(aufgabe_afb) if aufgabe_afb in reihenfolge else 2
    return reihenfolge[: idx + 1]


def _suche(db, kapitel, unterkapitel, k_ids, ziel_afb, gesehen, limit):
    from app.models.buchaufgabe import Buchaufgabe, BuchaufgabeKompetenz

    def q(kap=None, uk=None, komps=None, afb=None):
        query = db.query(Buchaufgabe)
        if kap:
            query = query.filter(Buchaufgabe.kapitel == kap)
        if uk:
            query = query.filter(Buchaufgabe.unterkapitel == uk)
        if komps:
            query = (query
                     .join(BuchaufgabeKompetenz)
                     .filter(BuchaufgabeKompetenz.kompetenz_id.in_(komps))
                     .distinct())
        if afb:
            query = query.filter(Buchaufgabe.afb_niveau.in_(afb))
        if gesehen:
            query = query.filter(~Buchaufgabe.id.in_(gesehen))
        return query.order_by(Buchaufgabe.wichtigkeit.desc()).all()

    _AFB_LABEL = {"AFB_I": "AFB I", "AFB_II": "AFB II", "AFB_III": "AFB III"}

    stufen = []
    if kapitel and unterkapitel:
        stufen += [
            (q(kapitel, unterkapitel, k_ids, ziel_afb),
             f"Kapitel + Unterkapitel + Kompetenz + AFB" if k_ids else "Kapitel + Unterkapitel + AFB"),
            (q(kapitel, unterkapitel, k_ids),
             "Kapitel + Unterkapitel + Kompetenz") if k_ids else ([], ""),
            (q(kapitel, unterkapitel),
             "Kapitel + Unterkapitel"),
        ]
    if k_ids:
        stufen += [
            (q(komps=k_ids, afb=ziel_afb), "Kompetenz + AFB"),
            (q(komps=k_ids), "Kompetenz"),
        ]

    treffer: list[BuchaufgabeMatch] = []
    for candidates, grund in stufen:
        if not grund:
            continue
        for ba in candidates:
            if ba.id in gesehen or len(treffer) >= limit:
                break
            gesehen.add(ba.id)
            treffer.append(BuchaufgabeMatch(
                buchaufgabe_id=ba.id,
                buch=ba.buch,
                kapitel=ba.kapitel,
                unterkapitel=ba.unterkapitel,
                aufgabennummer=ba.aufgabennummer,
                beschreibung=ba.beschreibung,
                afb_niveau=ba.afb_niveau.value if hasattr(ba.afb_niveau, "value") else str(ba.afb_niveau),
                wichtigkeit=ba.wichtigkeit,
                match_grund=grund,
            ))
        if len(treffer) >= limit:
            break

    return treffer


def empfehlungen_fuer_schulaufgabe(
    schueler_id: int,
    leistung_id: int,
    db: Session,
    max_pro_aufgabe: int = 2,
) -> tuple[object, object, list[AufgabeBlock]]:
    from app.models.schueler import Schueler
    from app.models.schriftliche_leistung import SchriftlicheLeistung, LeistungAufgabe
    from app.models.schueler_ergebnis import SchuelerErgebnis
    from app.models.aufgabe import AufgabeKompetenz

    schueler = db.get(Schueler, schueler_id)
    leistung = db.get(SchriftlicheLeistung, leistung_id)

    las = sorted(leistung.leistung_aufgaben, key=lambda la: la.reihenfolge)
    gesehen_global: set[int] = set()
    bloecke: list[AufgabeBlock] = []

    for la in las:
        a = la.aufgabe
        ergebnis = db.query(SchuelerErgebnis).filter(
            SchuelerErgebnis.schueler_id == schueler_id,
            SchuelerErgebnis.leistung_aufgabe_id == la.id,
        ).first()

        erreicht = ergebnis.erreichte_punkte if ergebnis else None
        prozent = round(erreicht / a.max_punkte * 100, 1) if erreicht is not None else None
        voll = erreicht is not None and erreicht >= a.max_punkte

        block = AufgabeBlock(
            la_nr=la.aufgabennummer,
            titel=a.titel,
            max_punkte=a.max_punkte,
            erreicht=erreicht,
            prozent=prozent,
            voll=voll,
        )

        if not voll:
            k_ids = [ak.kompetenz_id for ak in
                     db.query(AufgabeKompetenz).filter(AufgabeKompetenz.aufgabe_id == a.id).all()]
            ziel = _ziel_afb(prozent, a.afb_niveau)
            block.empfehlungen = _suche(
                db, a.kapitel, a.unterkapitel, k_ids, ziel,
                gesehen_global, max_pro_aufgabe,
            )

        bloecke.append(block)

    return schueler, leistung, bloecke
