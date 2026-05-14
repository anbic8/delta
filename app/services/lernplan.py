from __future__ import annotations
from dataclasses import dataclass, field
from sqlalchemy.orm import Session


@dataclass
class LernplanEmpfehlung:
    ba_id: int
    buch: str
    kapitel: str
    unterkapitel: str
    aufgabennummer: str
    beschreibung: str | None
    afb_niveau: str
    wichtigkeit: int
    sa_flag: bool       # Aufgabe deckt SA-Kompetenz ab (wichtig für alle)
    pers_flag: bool     # Aufgabe trifft persönliche Schwäche des Schülers
    score: float


@dataclass
class LernplanSchueler:
    schueler_id: int
    name: str
    empfehlungen: list[LernplanEmpfehlung] = field(default_factory=list)


def berechne_lernplan(
    leistung_id: int,
    db: Session,
    buch_filter: str = "",
    kapitel_filter: str = "",
    max_pro_schueler: int = 6,
):
    """
    Gibt zurück: (leistung, sa_profil_dict, schueler_liste)
      sa_profil_dict: {kuerzel: anteil_0_bis_1}
      schueler_liste: [LernplanSchueler, ...]
    """
    from app.models.schriftliche_leistung import SchriftlicheLeistung
    from app.models.schueler import Schueler
    from app.models.kompetenz import Kompetenz
    from app.models.buchaufgabe import Buchaufgabe
    from app.services.kompetenzprofil import berechne_profil

    leistung = db.get(SchriftlicheLeistung, leistung_id)
    las = sorted(leistung.leistung_aufgaben, key=lambda x: x.reihenfolge)

    # ── SA-Profil: Kompetenzgewichtung des Tests ──
    sa_komp_punkte: dict[str, float] = {}
    for la in las:
        for ak in la.aufgabe.kompetenzen:
            k = ak.kompetenz.kuerzel
            sa_komp_punkte[k] = sa_komp_punkte.get(k, 0.0) + la.aufgabe.max_punkte * ak.gewichtung

    sa_gesamt = sum(sa_komp_punkte.values()) or 1.0
    sa_profil = {k: round(v / sa_gesamt, 3) for k, v in sa_komp_punkte.items()}

    # ── Buchaufgaben-Kandidaten ──
    q = db.query(Buchaufgabe)
    if buch_filter:
        q = q.filter(Buchaufgabe.buch == buch_filter)
    if kapitel_filter:
        q = q.filter(Buchaufgabe.kapitel == kapitel_filter)
    kandidaten = q.all()

    # ── Kompetenz-Map (id → kuerzel) ──
    k_id_to_kuerzel = {k.id: k.kuerzel for k in db.query(Kompetenz).all()}

    # ── Pro Schüler ──
    schueler_liste = (
        db.query(Schueler)
        .filter(Schueler.klasse_id == leistung.klasse_id, Schueler.geloescht_am.is_(None))
        .order_by(Schueler.nachname, Schueler.vorname)
        .all()
    )

    result: list[LernplanSchueler] = []
    for s in schueler_liste:
        profil = berechne_profil(s.id, db)  # k_id → score (0–100)
        profil_kuerzel = {k_id_to_kuerzel[k_id]: score for k_id, score in profil.items() if k_id in k_id_to_kuerzel}
        schwach = {k for k, score in profil_kuerzel.items() if score < 60}

        scored: list[tuple[float, Buchaufgabe, bool, bool]] = []
        for ba in kandidaten:
            ba_kuerzels = {bak.kompetenz.kuerzel for bak in ba.kompetenzen}

            sa_score = sum(sa_profil.get(k, 0.0) for k in ba_kuerzels) * 25
            pers_score = len(ba_kuerzels & schwach) * 12
            total = ba.wichtigkeit * 3 + sa_score + pers_score + (2 if ba.minimalfahrplan else 0)

            sa_flag = any(sa_profil.get(k, 0.0) >= 0.05 for k in ba_kuerzels)
            pers_flag = bool(ba_kuerzels & schwach)

            if sa_flag or pers_flag:
                scored.append((total, ba, sa_flag, pers_flag))

        scored.sort(key=lambda x: -x[0])
        empf = [
            LernplanEmpfehlung(
                ba_id=ba.id, buch=ba.buch, kapitel=ba.kapitel,
                unterkapitel=ba.unterkapitel or "", aufgabennummer=ba.aufgabennummer,
                beschreibung=ba.beschreibung, afb_niveau=ba.afb_niveau,
                wichtigkeit=ba.wichtigkeit, sa_flag=sa_f, pers_flag=pers_f, score=round(sc, 1),
            )
            for sc, ba, sa_f, pers_f in scored[:max_pro_schueler]
        ]
        result.append(LernplanSchueler(
            schueler_id=s.id,
            name=f"{s.nachname}, {s.vorname}",
            empfehlungen=empf,
        ))

    return leistung, sa_profil, result
