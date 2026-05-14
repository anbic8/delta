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
    afb_label: str
    wichtigkeit: int
    sa_flag: bool
    pers_flag: bool
    ergaenzt: bool = False
    teste_dich: bool = False


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
    return sorted({r[0] for r in db.query(Buchaufgabe.kapitel).distinct().all()})


def alle_uk_paare(db: Session) -> list[tuple[str, str]]:
    """Sortierte Liste aller (kapitel, unterkapitel)-Paare aus dem Buchaufgaben-Katalog."""
    from app.models.buchaufgabe import Buchaufgabe
    rows = db.query(Buchaufgabe.kapitel, Buchaufgabe.unterkapitel).distinct().all()
    return sorted({(r[0] or "", r[1] or "") for r in rows})


def _afb_str(value) -> str:
    key = getattr(value, "value", None) or str(value)
    if "." in key:
        key = key.rsplit(".", 1)[-1]
    return key


def _score(ba, sa_profil: dict, schwach: set) -> tuple:
    """Gibt (total, sa_flag, pers_flag) zurück."""
    ks = {bak.kompetenz.kuerzel for bak in ba.kompetenzen}
    sa_s = sum(sa_profil.get(k, 0.0) for k in ks) * 25
    pers_s = len(ks & schwach) * 15
    total = float(ba.wichtigkeit) * 3 + sa_s + pers_s + (2.0 if ba.minimalfahrplan else 0.0)
    sa_f = any(sa_profil.get(k, 0.0) >= 0.05 for k in ks)
    pers_f = bool(ks & schwach)
    return total, sa_f, pers_f


def _ist_teste_dich(ba) -> bool:
    uk = (ba.unterkapitel or "").lower()
    return "teste" in uk or "selbsttest" in uk


def _mk_eintrag(ba, sa_flag: bool, pers_flag: bool, ergaenzt: bool = False, teste_dich: bool = False) -> PlanEintrag:
    afb_key = _afb_str(ba.afb_niveau)
    return PlanEintrag(
        ba_id=ba.id,
        kapitel=ba.kapitel or "",
        unterkapitel=ba.unterkapitel or "",
        aufgabennummer=ba.aufgabennummer,
        beschreibung=ba.beschreibung,
        afb_label=AFB_LABEL.get(afb_key, afb_key),
        wichtigkeit=ba.wichtigkeit,
        sa_flag=sa_flag,
        pers_flag=pers_flag,
        ergaenzt=ergaenzt,
        teste_dich=teste_dich,
    )


def _kompetenz_profil(las: list) -> dict[str, float]:
    """SA-Kompetenz-Profil aus einer Teilmenge von LeistungAufgaben."""
    punkte: dict[str, float] = {}
    for la in las:
        for ak in la.aufgabe.kompetenzen:
            k = ak.kompetenz.kuerzel
            punkte[k] = punkte.get(k, 0.0) + la.aufgabe.max_punkte * ak.gewichtung
    gesamt = sum(punkte.values()) or 1.0
    return {k: round(v / gesamt, 3) for k, v in punkte.items()}


def berechne_lernplan(
    leistung_id: int,
    db: Session,
    von_idx: int = 0,
    bis_idx: int = -1,
) -> tuple:
    from app.models.schriftliche_leistung import SchriftlicheLeistung
    from app.models.buchaufgabe import Buchaufgabe
    from app.models.schueler import Schueler
    from app.models.kompetenz import Kompetenz
    from app.services.kompetenzprofil import berechne_profil

    leistung = db.get(SchriftlicheLeistung, leistung_id)
    if not leistung:
        return None, {}, [], []

    las = sorted(leistung.leistung_aufgaben, key=lambda x: x.reihenfolge)

    # ── Globales SA-Profil ────────────────────────────────────
    sa_profil_global = _kompetenz_profil(las)

    # ── UK/Kapitel-spezifische SA-Profile ─────────────────────
    by_uk: dict[tuple, list] = defaultdict(list)
    by_kap: dict[str, list] = defaultdict(list)
    for la in las:
        kap = la.aufgabe.kapitel or ""
        uk = la.aufgabe.unterkapitel or ""
        by_uk[(kap, uk)].append(la)
        by_kap[kap].append(la)

    sa_uk: dict[tuple, dict] = {k: _kompetenz_profil(v) for k, v in by_uk.items()}
    sa_kap: dict[str, dict] = {k: _kompetenz_profil(v) for k, v in by_kap.items()}

    def profil_fuer(kap: str, uk: str) -> dict:
        return sa_uk.get((kap, uk)) or sa_kap.get(kap) or sa_profil_global

    # ── SA-Kompetenz-Index für Lücken-Check ───────────────────
    sa_la_komps: dict[int, set] = {
        la.id: {ak.kompetenz.kuerzel for ak in la.aufgabe.kompetenzen}
        for la in las
    }

    # ── UK-Scope (Index-basiert) ──────────────────────────────
    uk_paare = alle_uk_paare(db)
    if not uk_paare:
        scope_set: set[tuple[str, str]] = set()
    else:
        i0 = max(0, von_idx)
        i1 = len(uk_paare) - 1 if bis_idx < 0 else min(bis_idx, len(uk_paare) - 1)
        scope_set = set(uk_paare[i0: i1 + 1])

    # ── Buchaufgaben laden ────────────────────────────────────
    alle_ba = db.query(Buchaufgabe).all()

    # Teste-dich von regulären Aufgaben trennen
    teste_dich_alle = [ba for ba in alle_ba if _ist_teste_dich(ba)]
    regulaere_alle  = [ba for ba in alle_ba if not _ist_teste_dich(ba)]

    # Reguläre: nur innerhalb des Scopes
    kandidaten = [
        ba for ba in regulaere_alle
        if not scope_set or (ba.kapitel or "", ba.unterkapitel or "") in scope_set
    ]

    # Teste-dich: pro Kapitel (ohne Scope-Filter, deckt ganzes Kapitel ab)
    teste_dich_per_kap: dict[str, list] = defaultdict(list)
    for ba in teste_dich_alle:
        # Nur Kapitel die im Scope vorkommen
        kap_in_scope = {kap for kap, _ in scope_set} if scope_set else None
        if kap_in_scope is None or (ba.kapitel or "") in kap_in_scope:
            teste_dich_per_kap[ba.kapitel or ""].append(ba)

    ba_by_id = {ba.id: ba for ba in kandidaten}

    gruppen: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for ba in kandidaten:
        gruppen[ba.kapitel or ""][ba.unterkapitel or ""].append(ba)

    # ── Kompetenz-Map (id → kuerzel) ─────────────────────────
    k_map = {k.id: k.kuerzel for k in db.query(Kompetenz).all()}

    # ── Schüler ───────────────────────────────────────────────
    schueler_qs = (
        db.query(Schueler)
        .filter(Schueler.klasse_id == leistung.klasse_id, Schueler.geloescht_am.is_(None))
        .order_by(Schueler.nachname, Schueler.vorname)
        .all()
    )

    result: list[PlanSchueler] = []

    for s in schueler_qs:
        profil_raw = berechne_profil(s.id, db)
        profil_k = {k_map[k_id]: sc for k_id, sc in profil_raw.items() if k_id in k_map}
        schwach = {k for k, sc in profil_k.items() if sc < 60}

        plan_ids: set[int] = set()
        plan_eintraege: list[PlanEintrag] = []

        kapitel_plan: list[PlanKapitel] = []

        for kap in sorted(gruppen.keys()):
            plan_kap = PlanKapitel(kapitel=kap)

            for uk in sorted(gruppen[kap].keys()):
                bas = gruppen[kap][uk]
                if not bas:
                    continue

                uk_profil = profil_fuer(kap, uk)

                # Alle Buchaufgaben dieses UK scored
                scored = sorted(
                    [(_score(ba, uk_profil, schwach), ba) for ba in bas],
                    key=lambda x: -x[0][0],
                )

                uk_eintraege: list[PlanEintrag] = []

                # 0. Beste Teste-dich-Aufgabe dieses Kapitels (kein plan_ids-Check)
                td_pool = teste_dich_per_kap.get(kap, [])
                if td_pool:
                    td_scored = sorted(
                        [(_score(ba, uk_profil, schwach), ba) for ba in td_pool],
                        key=lambda x: -x[0][0],
                    )
                    sc_tuple, ba = td_scored[0]
                    _, sa_f, pers_f = sc_tuple
                    e = _mk_eintrag(ba, sa_flag=sa_f, pers_flag=pers_f, teste_dich=True)
                    uk_eintraege.append(e)
                    # kein plan_ids.add — gleiche Teste-dich darf in mehreren UKs erscheinen

                # 1. Beste SA-Aufgabe (nur reguläre, d.h. aus scored)
                sa_candidate = next((x for x in scored if x[0][1]), None) or (scored[0] if scored else None)
                if sa_candidate:
                    sc_tuple, ba = sa_candidate
                    _, sa_f, pers_f = sc_tuple
                    e = _mk_eintrag(ba, sa_flag=True, pers_flag=pers_f)
                    uk_eintraege.append(e)
                    plan_ids.add(ba.id)
                    plan_eintraege.append(e)

                # 2. Beste persönliche Aufgabe (andere reguläre wenn möglich)
                sa_id = sa_candidate[1].id if sa_candidate else -1
                pers_candidate = (
                    next((x for x in scored if x[0][2] and x[1].id != sa_id), None)
                    or next((x for x in scored if x[1].id != sa_id), None)
                )
                if pers_candidate:
                    sc_tuple, ba = pers_candidate
                    _, sa_f, pers_f = sc_tuple
                    if ba.id in plan_ids:
                        for e in uk_eintraege:
                            if e.ba_id == ba.id:
                                e.pers_flag = True
                    else:
                        e = _mk_eintrag(ba, sa_flag=sa_f, pers_flag=True)
                        uk_eintraege.append(e)
                        plan_ids.add(ba.id)
                        plan_eintraege.append(e)
                elif len(uk_eintraege) > 1:
                    # Erste reguläre Aufgabe erhält pers_flag
                    next((e for e in uk_eintraege if not e.teste_dich), uk_eintraege[-1]).pers_flag = True

                if uk_eintraege:
                    plan_kap.uks.append(PlanUK(unterkapitel=uk, eintraege=uk_eintraege))

            if plan_kap.uks:
                kapitel_plan.append(plan_kap)

        # ── Lücken-Check: je SA-Aufgabe mind. 2 Buchaufgaben ──
        for la in las:
            la_komps = sa_la_komps.get(la.id, set())
            if not la_komps:
                continue
            abdeckung = sum(
                1 for e in plan_eintraege
                if e.ba_id in ba_by_id
                and la_komps & {bak.kompetenz.kuerzel for bak in ba_by_id[e.ba_id].kompetenzen}
            )
            if abdeckung >= 2:
                continue
            extras = sorted(
                [ba for ba in kandidaten
                 if ba.id not in plan_ids
                 and la_komps & {bak.kompetenz.kuerzel for bak in ba.kompetenzen}],
                key=lambda ba: -ba.wichtigkeit,
            )
            for ba in extras[: max(0, 2 - abdeckung)]:
                e = _mk_eintrag(ba, sa_flag=True, pers_flag=False, ergaenzt=True)
                plan_ids.add(ba.id)
                plan_eintraege.append(e)
                kap_slot = next((pk for pk in kapitel_plan if pk.kapitel == (ba.kapitel or "")), None)
                if not kap_slot:
                    kap_slot = PlanKapitel(kapitel=ba.kapitel or "")
                    kapitel_plan.append(kap_slot)
                    kapitel_plan.sort(key=lambda pk: pk.kapitel)
                uk_slot = next((u for u in kap_slot.uks if u.unterkapitel == (ba.unterkapitel or "")), None)
                if not uk_slot:
                    uk_slot = PlanUK(unterkapitel=ba.unterkapitel or "")
                    kap_slot.uks.append(uk_slot)
                    kap_slot.uks.sort(key=lambda u: u.unterkapitel)
                uk_slot.eintraege.append(e)

        result.append(PlanSchueler(
            schueler_id=s.id,
            name=f"{s.nachname}, {s.vorname}",
            kapitel=kapitel_plan,
        ))

    return leistung, sa_profil_global, result, uk_paare
