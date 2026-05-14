from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass, field
from sqlalchemy.orm import Session


AFB_LABEL = {"AFB_I": "Reproduzieren", "AFB_II": "Anwenden", "AFB_III": "Verallgemeinern"}


@dataclass
class PlanEintrag:
    ba_id: int
    kapitel: str
    unterkapitel: str
    aufgabennummer: str
    beschreibung: str | None
    afb_label: str          # "Reproduzieren" / "Anwenden" / "Verallgemeinern"
    wichtigkeit: int
    sa_flag: bool           # ★  Deckt SA-Kompetenz ab
    pers_flag: bool         # ⚠  Trifft persönliche Schwäche
    ergaenzt: bool = False  # Wurde nachträglich zur Lückendeckung hinzugefügt


@dataclass
class PlanUK:
    unterkapitel: str
    eintraege: list[PlanEintrag] = field(default_factory=list)


@dataclass
class PlanKapitel:
    kapitel: str
    uks: list[PlanUK] = field(default_factory=list)


@dataclass
class PlanSchueler:
    schueler_id: int
    name: str
    kapitel: list[PlanKapitel] = field(default_factory=list)


def alle_buchkapitel(db: Session) -> list[str]:
    from app.models.buchaufgabe import Buchaufgabe
    return sorted(set(r[0] for r in db.query(Buchaufgabe.kapitel).distinct().all()))


def berechne_lernplan(
    leistung_id: int,
    db: Session,
    kapitel_von: str = "",
    kapitel_bis: str = "",
    min_pro_uk: int = 2,
) -> tuple:
    """
    Gibt zurück: (leistung, sa_profil, schueler_liste, alle_kapitel)
    """
    from app.models.schriftliche_leistung import SchriftlicheLeistung
    from app.models.buchaufgabe import Buchaufgabe
    from app.models.schueler import Schueler
    from app.models.kompetenz import Kompetenz
    from app.services.kompetenzprofil import berechne_profil

    leistung = db.get(SchriftlicheLeistung, leistung_id)
    las = sorted(leistung.leistung_aufgaben, key=lambda x: x.reihenfolge)

    # ── SA-Profil ──────────────────────────────────────────────
    # Globales Profil (Fallback) + Profil pro (kapitel, uk) + pro kapitel
    def _kompetenz_punkte(las_subset) -> dict[str, float]:
        punkte: dict[str, float] = {}
        for la in las_subset:
            for ak in la.aufgabe.kompetenzen:
                k = ak.kompetenz.kuerzel
                punkte[k] = punkte.get(k, 0.0) + la.aufgabe.max_punkte * ak.gewichtung
        return punkte

    def _to_profil(punkte: dict[str, float]) -> dict[str, float]:
        gesamt = sum(punkte.values()) or 1.0
        return {k: round(v / gesamt, 3) for k, v in punkte.items()}

    sa_komp_punkte_global = _kompetenz_punkte(las)
    sa_profil = _to_profil(sa_komp_punkte_global)  # für Anzeige + Fallback

    # Index: (kapitel, uk) → profil, kapitel → profil
    _sa_by_uk: dict[tuple[str, str], dict[str, float]] = {}
    _sa_by_kap: dict[str, dict[str, float]] = {}
    from collections import defaultdict as _dd
    _by_uk: dict[tuple[str, str], list] = _dd(list)
    _by_kap: dict[str, list] = _dd(list)
    for la in las:
        kap = la.aufgabe.kapitel or ""
        uk = la.aufgabe.unterkapitel or ""
        _by_uk[(kap, uk)].append(la)
        _by_kap[kap].append(la)
    for key, subset in _by_uk.items():
        _sa_by_uk[key] = _to_profil(_kompetenz_punkte(subset))
    for key, subset in _by_kap.items():
        _sa_by_kap[key] = _to_profil(_kompetenz_punkte(subset))

    def sa_profil_fuer(kap: str, uk: str) -> dict[str, float]:
        """UK-spezifisches SA-Profil, Fallback: Kapitel, dann global."""
        return _sa_by_uk.get((kap, uk)) or _sa_by_kap.get(kap) or sa_profil

    sa_la_komps: dict[int, set[str]] = {}
    for la in las:
        sa_la_komps[la.id] = {ak.kompetenz.kuerzel for ak in la.aufgabe.kompetenzen}

    # ── Kapitel-Scope ─────────────────────────────────────────
    alle_kap = alle_buchkapitel(db)
    if kapitel_von and kapitel_bis and kapitel_von in alle_kap and kapitel_bis in alle_kap:
        i_von = alle_kap.index(kapitel_von)
        i_bis = alle_kap.index(kapitel_bis)
        scope = alle_kap[min(i_von, i_bis): max(i_von, i_bis) + 1]
    else:
        scope = alle_kap  # Fallback: alle

    # ── Buchaufgaben laden + gruppieren ───────────────────────
    kandidaten: list[Buchaufgabe] = (
        db.query(Buchaufgabe)
        .filter(Buchaufgabe.kapitel.in_(scope))
        .all()
    )
    ba_by_id: dict[int, Buchaufgabe] = {ba.id: ba for ba in kandidaten}

    # Gruppierung: kapitel → uk → [ba]
    gruppen: dict[str, dict[str, list[Buchaufgabe]]] = defaultdict(lambda: defaultdict(list))
    for ba in kandidaten:
        gruppen[ba.kapitel][ba.unterkapitel or ""].append(ba)

    # ── Kompetenz-Map ─────────────────────────────────────────
    k_id_to_kuerzel = {k.id: k.kuerzel for k in db.query(Kompetenz).all()}

    # ── Pro Schüler ───────────────────────────────────────────
    schueler_qs = (
        db.query(Schueler)
        .filter(Schueler.klasse_id == leistung.klasse_id, Schueler.geloescht_am.is_(None))
        .order_by(Schueler.nachname, Schueler.vorname)
        .all()
    )

    result: list[PlanSchueler] = []

    for s in schueler_qs:
        profil = berechne_profil(s.id, db)  # k_id → score
        profil_k = {k_id_to_kuerzel[k_id]: sc for k_id, sc in profil.items() if k_id in k_id_to_kuerzel}
        schwach: set[str] = {k for k, sc in profil_k.items() if sc < 60}

        plan_ba_ids: set[int] = set()           # bereits im Plan
        plan_eintraege: list[PlanEintrag] = []  # alle Einträge, für Lücken-Check

        kapitel_plan: list[PlanKapitel] = []

        for kap in sorted(gruppen.keys()):
            plan_kap = PlanKapitel(kapitel=kap)

            for uk in sorted(gruppen[kap].keys()):
                bas = gruppen[kap][uk]

                # UK-spezifisches SA-Profil für dieses Unterkapitel
                uk_sa_profil = sa_profil_fuer(kap, uk)

                # Scoring: SA-Match + Persönlich-Match + Wichtigkeit
                def score_ba(ba: Buchaufgabe, _sp=uk_sa_profil) -> tuple[float, float, float, bool, bool]:
                    ks = {bak.kompetenz.kuerzel for bak in ba.kompetenzen}
                    sa_s = sum(_sp.get(k, 0.0) for k in ks) * 25
                    pers_s = len(ks & schwach) * 15
                    total = ba.wichtigkeit * 3 + sa_s + pers_s + (2 if ba.minimalfahrplan else 0)
                    sa_f = any(_sp.get(k, 0.0) >= 0.05 for k in ks)
                    pers_f = bool(ks & schwach)
                    return total, sa_s, pers_s, sa_f, pers_f

                scored = sorted([(score_ba(ba), ba) for ba in bas], key=lambda x: -x[0][0])

                uk_eintraege: list[PlanEintrag] = []

                def _eintrag(ba: Buchaufgabe, sa_f: bool, pers_f: bool, erg: bool = False) -> PlanEintrag:
                    return PlanEintrag(
                        ba_id=ba.id, kapitel=ba.kapitel, unterkapitel=ba.unterkapitel or "",
                        aufgabennummer=ba.aufgabennummer, beschreibung=ba.beschreibung,
                        afb_label=AFB_LABEL.get(str(ba.afb_niveau), str(ba.afb_niveau)),
                        wichtigkeit=ba.wichtigkeit, sa_flag=sa_f, pers_flag=pers_f, ergaenzt=erg,
                    )

                # 1. Beste SA-Aufgabe
                sa_best = next(((sc, ba) for (sc, ba) in scored if sc[3]), None) or (scored[0] if scored else None)
                if sa_best:
                    (_, _, _, sa_f, pers_f), ba = sa_best
                    e = _eintrag(ba, sa_flag=True, pers_flag=pers_f)
                    uk_eintraege.append(e)
                    plan_ba_ids.add(ba.id)
                    plan_eintraege.append(e)

                # 2. Beste persönliche Aufgabe (andere als SA-Pick wenn möglich)
                sa_id = sa_best[1].id if sa_best else None
                pers_best = next(
                    ((sc, ba) for (sc, ba) in scored if sc[4] and ba.id != sa_id), None
                ) or next(
                    ((sc, ba) for (sc, ba) in scored if ba.id != sa_id), None
                )

                if pers_best:
                    (_, _, _, sa_f, pers_f), ba = pers_best
                    if ba.id in plan_ba_ids:
                        # Gleiche Aufgabe → Flags ergänzen
                        for e in uk_eintraege:
                            if e.ba_id == ba.id:
                                e.pers_flag = True
                    else:
                        e = _eintrag(ba, sa_flag=sa_f, pers_flag=True)
                        uk_eintraege.append(e)
                        plan_ba_ids.add(ba.id)
                        plan_eintraege.append(e)
                elif sa_best:
                    # Nur eine Aufgabe im UK → beide Flags setzen
                    uk_eintraege[0].pers_flag = True

                if uk_eintraege:
                    plan_kap.uks.append(PlanUK(unterkapitel=uk, eintraege=uk_eintraege))

            if plan_kap.uks:
                kapitel_plan.append(plan_kap)

        # ── Lücken-Check: je SA-Aufgabe mind. 2 Buchaufgaben im Plan ──
        for la in las:
            la_komps = sa_la_komps[la.id]
            if not la_komps:
                continue

            # Wie viele Plan-Einträge decken diese Kompetenzen ab?
            abdeckung = sum(
                1 for e in plan_eintraege
                if la_komps & {bak.kompetenz.kuerzel for bak in ba_by_id[e.ba_id].kompetenzen}
            )

            if abdeckung >= 2:
                continue

            # Zusatzaufgaben suchen
            extras = sorted(
                [ba for ba in kandidaten
                 if ba.id not in plan_ba_ids
                 and la_komps & {bak.kompetenz.kuerzel for bak in ba.kompetenzen}],
                key=lambda ba: -ba.wichtigkeit,
            )
            for ba in extras[: max(0, 2 - abdeckung)]:
                e = _eintrag(ba, sa_flag=True, pers_flag=False, erg=True)
                plan_ba_ids.add(ba.id)
                plan_eintraege.append(e)
                # In den richtigen Kapitel/UK-Slot einhängen
                kap_slot = next((pk for pk in kapitel_plan if pk.kapitel == ba.kapitel), None)
                if not kap_slot:
                    kap_slot = PlanKapitel(kapitel=ba.kapitel)
                    kapitel_plan.append(kap_slot)
                    kapitel_plan.sort(key=lambda pk: pk.kapitel)
                uk_slot = next((u for u in kap_slot.uks if u.unterkapitel == (ba.unterkapitel or "")), None)
                if not uk_slot:
                    uk_slot = PlanUK(unterkapitel=ba.unterkapitel or "")
                    kap_slot.uks.append(uk_slot)
                    kap_slot.uks.sort(key=lambda u: u.unterkapitel)
                uk_slot.eintraege.append(e)

        result.append(PlanSchueler(schueler_id=s.id, name=f"{s.nachname}, {s.vorname}", kapitel=kapitel_plan))

    return leistung, sa_profil, result, alle_kap
