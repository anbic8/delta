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
    teste_dich: bool = False


@dataclass
class PlanUK:
    unterkapitel: str
    teste_dich_block: list[PlanEintrag] = field(default_factory=list)
    aufgaben_block: list[PlanEintrag] = field(default_factory=list)


@dataclass
class PlanKapitel:
    kapitel: str
    uks: list[PlanUK] = field(default_factory=list)


@dataclass
class PlanSchueler:
    schueler_id: int
    name: str
    kapitel: list[PlanKapitel] = field(default_factory=list)


# ── Klassifikatoren ───────────────────────────────────────────


def _ist_teste_dich_uk(ba) -> bool:
    """UK-Name enthält 'teste' oder 'selbsttest' → ganzes UK ausschließen."""
    uk = (ba.unterkapitel or "").lower()
    return "teste" in uk or "selbsttest" in uk


def _ist_teste_dich_beschreibung(ba) -> bool:
    """Beschreibung verweist auf Teste-dich-Aufgabe."""
    desc = (ba.beschreibung or "").lower()
    return desc.startswith("teste") or "teste dich" in desc


def _ist_grundwissen(ba) -> bool:
    return (ba.beschreibung or "").lower().startswith("grundwissen")


def _ist_ausgeschlossen(ba) -> bool:
    """Weder Teste-dich noch Grundwissen im regulären Block verwenden."""
    return _ist_teste_dich_beschreibung(ba) or _ist_grundwissen(ba)


# ── Hilfsfunktionen ───────────────────────────────────────────


def alle_uk_paare(db: Session) -> list[tuple[str, str]]:
    """Sortierte (kapitel, unterkapitel)-Paare — ohne Teste-dich-UKs."""
    from app.models.buchaufgabe import Buchaufgabe
    rows = db.query(Buchaufgabe.kapitel, Buchaufgabe.unterkapitel).distinct().all()
    return sorted(
        {(r[0] or "", r[1] or "") for r in rows
         if not ("teste" in (r[1] or "").lower() or "selbsttest" in (r[1] or "").lower())}
    )


def sa_scope_indices(leistung_id: int, db: Session, uk_paare: list[tuple]) -> tuple[int, int]:
    from app.models.schriftliche_leistung import SchriftlicheLeistung
    leistung = db.get(SchriftlicheLeistung, leistung_id)
    if not leistung or not uk_paare:
        return 0, len(uk_paare) - 1
    pair_idx = {p: i for i, p in enumerate(uk_paare)}
    sa_pairs = {
        (la.aufgabe.kapitel or "", la.aufgabe.unterkapitel or "")
        for la in leistung.leistung_aufgaben if la.aufgabe.kapitel
    }
    indices = [pair_idx[p] for p in sa_pairs if p in pair_idx]
    if not indices:
        return 0, len(uk_paare) - 1
    return min(indices), max(indices)


def _afb_str(value) -> str:
    key = getattr(value, "value", None) or str(value)
    if "." in key:
        key = key.rsplit(".", 1)[-1]
    return key


def _score(ba, sa_profil: dict, schwach: set) -> tuple[float, bool, bool]:
    ks = {bak.kompetenz.kuerzel for bak in ba.kompetenzen}
    sa_s = sum(sa_profil.get(k, 0.0) for k in ks) * 25
    pers_s = len(ks & schwach) * 15
    total = float(ba.wichtigkeit) * 3 + sa_s + pers_s + (2.0 if ba.minimalfahrplan else 0.0)
    sa_f = any(sa_profil.get(k, 0.0) >= 0.05 for k in ks)
    pers_f = bool(ks & schwach)
    return total, sa_f, pers_f


def _mk(ba, sa_flag: bool, pers_flag: bool, teste_dich: bool = False) -> PlanEintrag:
    afb_key = _afb_str(ba.afb_niveau)
    return PlanEintrag(
        ba_id=ba.id, kapitel=ba.kapitel or "", unterkapitel=ba.unterkapitel or "",
        aufgabennummer=ba.aufgabennummer, beschreibung=ba.beschreibung,
        afb_label=AFB_LABEL.get(afb_key, afb_key),
        wichtigkeit=ba.wichtigkeit, sa_flag=sa_flag, pers_flag=pers_flag,
        teste_dich=teste_dich,
    )


def _kompetenz_profil(las: list) -> dict[str, float]:
    punkte: dict[str, float] = {}
    for la in las:
        for ak in la.aufgabe.kompetenzen:
            k = ak.kompetenz.kuerzel
            punkte[k] = punkte.get(k, 0.0) + la.aufgabe.max_punkte * ak.gewichtung
    gesamt = sum(punkte.values()) or 1.0
    return {k: round(v / gesamt, 3) for k, v in punkte.items()}


# ── Hauptfunktion ─────────────────────────────────────────────


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

    # ── SA-Profile ────────────────────────────────────────────
    sa_profil_global = _kompetenz_profil(las)
    by_uk: dict[tuple, list] = defaultdict(list)
    by_kap: dict[str, list] = defaultdict(list)
    for la in las:
        kap = la.aufgabe.kapitel or ""
        uk = la.aufgabe.unterkapitel or ""
        by_uk[(kap, uk)].append(la)
        by_kap[kap].append(la)
    sa_uk = {k: _kompetenz_profil(v) for k, v in by_uk.items()}
    sa_kap = {k: _kompetenz_profil(v) for k, v in by_kap.items()}

    def profil_fuer(kap: str, uk: str) -> dict:
        return sa_uk.get((kap, uk)) or sa_kap.get(kap) or sa_profil_global

    # ── UK-Scope ──────────────────────────────────────────────
    uk_paare = alle_uk_paare(db)
    if uk_paare:
        i0 = max(0, von_idx)
        i1 = len(uk_paare) - 1 if bis_idx < 0 else min(bis_idx, len(uk_paare) - 1)
        scope_set = set(uk_paare[i0: i1 + 1])
    else:
        scope_set = set()

    # ── Buchaufgaben laden (nur nicht-Teste-dich-UKs im Scope) ───
    alle_ba = db.query(Buchaufgabe).all()
    scope_ba = [
        ba for ba in alle_ba
        if not _ist_teste_dich_uk(ba)
        and (not scope_set or (ba.kapitel or "", ba.unterkapitel or "") in scope_set)
    ]

    gruppen: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for ba in scope_ba:
        gruppen[ba.kapitel or ""][ba.unterkapitel or ""].append(ba)

    k_map = {k.id: k.kuerzel for k in db.query(Kompetenz).all()}

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
        kapitel_plan: list[PlanKapitel] = []

        for kap in sorted(gruppen.keys()):
            plan_kap = PlanKapitel(kapitel=kap)
            kap_profil = sa_kap.get(kap) or sa_profil_global

            # Kapitel-Pool für Block 3: alle regulären Aufgaben im Kapitel, nach Score sortiert
            kap_pool = [
                ba for uk_bas in gruppen[kap].values()
                for ba in uk_bas
                if not _ist_ausgeschlossen(ba)
            ]
            kap_pool_scored = sorted(
                [(_score(ba, kap_profil, schwach), ba) for ba in kap_pool],
                key=lambda x: -x[0][0],
            )

            for uk in sorted(gruppen[kap].keys()):
                bas_uk = gruppen[kap][uk]
                if not bas_uk:
                    continue

                uk_profil = profil_fuer(kap, uk)
                plan_uk = PlanUK(unterkapitel=uk)

                # ── Block 1: Teste-dich (per Beschreibung) in diesem UK ──
                td_uk = [ba for ba in bas_uk if _ist_teste_dich_beschreibung(ba)]
                td_scored = sorted(
                    [(_score(ba, uk_profil, schwach), ba) for ba in td_uk],
                    key=lambda x: -x[0][0],
                )
                for sc_t, ba in td_scored:
                    if ba.id not in plan_ids:
                        _, sa_f, pers_f = sc_t
                        plan_uk.teste_dich_block.append(_mk(ba, sa_f, pers_f, teste_dich=True))
                        plan_ids.add(ba.id)

                # ── Block 2: Pro Beschreibung (excl. Teste-dich + Grundwissen) ──
                regulaere_uk = [ba for ba in bas_uk if not _ist_ausgeschlossen(ba)]
                scored_uk = sorted(
                    [(_score(ba, uk_profil, schwach), ba) for ba in regulaere_uk],
                    key=lambda x: -x[0][0],
                )
                by_beschr: dict[str, tuple] = {}
                for sc_t, ba in scored_uk:
                    key = (ba.beschreibung or "").strip()
                    if key not in by_beschr:
                        by_beschr[key] = (sc_t, ba)

                for key in sorted(by_beschr.keys()):
                    sc_t, ba = by_beschr[key]
                    if ba.id not in plan_ids:
                        _, sa_f, pers_f = sc_t
                        plan_uk.aufgaben_block.append(_mk(ba, sa_f, pers_f))
                        plan_ids.add(ba.id)

                # ── Block 3: 2 weitere aus dem Kapitel (bester Score) ──
                count = 0
                for sc_t, ba in kap_pool_scored:
                    if count >= 2:
                        break
                    if ba.id not in plan_ids:
                        _, sa_f, pers_f = sc_t
                        plan_uk.aufgaben_block.append(_mk(ba, sa_f, pers_f))
                        plan_ids.add(ba.id)
                        count += 1

                if plan_uk.teste_dich_block or plan_uk.aufgaben_block:
                    plan_kap.uks.append(plan_uk)

            if plan_kap.uks:
                kapitel_plan.append(plan_kap)

        result.append(PlanSchueler(
            schueler_id=s.id,
            name=f"{s.nachname}, {s.vorname}",
            kapitel=kapitel_plan,
        ))

    return leistung, sa_profil_global, result, uk_paare
