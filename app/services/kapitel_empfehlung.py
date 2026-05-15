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
            .filter(
                Buchaufgabe.kapitel == kapitel,
                Buchaufgabe.unterkapitel == uk,
                Buchaufgabe.im_unterricht.is_(False),
            )
            .all()
        )

        ergebnis[uk] = _pick_aufgaben(kandidaten, schwach_k_ids, ziel, anzahl)

    return ergebnis, komps, afb_profil, ziel


def schueler_afb_profil(schueler_id: int, db: Session) -> dict[AfbNiveau, float]:
    """Persönlicher AFB-Score eines Schülers aus allen seinen Testergebnissen."""
    from app.models.schueler_ergebnis import SchuelerErgebnis

    ergebnisse = (
        db.query(SchuelerErgebnis)
        .filter(
            SchuelerErgebnis.schueler_id == schueler_id,
            SchuelerErgebnis.leistung_aufgabe_id.isnot(None),
            SchuelerErgebnis.erreichte_punkte.isnot(None),
        ).all()
    )
    sammel: dict[AfbNiveau, list[float]] = defaultdict(list)
    for e in ergebnisse:
        la = e.leistung_aufgabe
        if la and la.aufgabe.max_punkte > 0:
            sammel[la.aufgabe.afb_niveau].append(
                e.erreichte_punkte / la.aufgabe.max_punkte * 100
            )
    return {afb: round(sum(v) / len(v), 1) for afb, v in sammel.items()}


def _score_ba(ba, schwach_k_ids, ziel) -> float:
    ba_k_ids = {bak.kompetenz_id for bak in ba.kompetenzen}
    return (
        ba.wichtigkeit * 10
        + len(ba_k_ids & schwach_k_ids) * 6
        + (1 if ba.afb_niveau in ziel else 0) * 3
        + (1 if ba.minimalfahrplan else 0)
    )


def _pick_aufgaben(kandidaten, schwach_k_ids, ziel, anzahl) -> list:
    """
    Wählt Aufgaben aus kandidaten:
    - Mindestens eine pro einzigartiger Beschreibung (beste nach Score)
    - Danach auffüllen bis anzahl erreicht
    """
    scored = sorted(
        [((_score_ba(ba, schwach_k_ids, ziel)), ba.id, ba) for ba in kandidaten],
        key=lambda x: -x[0],
    )

    # Beste Aufgabe pro Beschreibung
    beste_pro_beschr: dict[str, tuple] = {}
    rest: list[tuple] = []
    for sc, ba_id, ba in scored:
        key = (ba.beschreibung or "").strip()
        if key not in beste_pro_beschr:
            beste_pro_beschr[key] = (sc, ba_id, ba)
        else:
            rest.append((sc, ba_id, ba))

    result = [ba for _, _, ba in sorted(beste_pro_beschr.values(), key=lambda x: -x[0])]
    gewählt_ids = {ba.id for ba in result}

    # Auffüllen bis anzahl, wenn noch Platz
    for _, _, ba in rest:
        if len(result) >= anzahl:
            break
        if ba.id not in gewählt_ids:
            result.append(ba)
            gewählt_ids.add(ba.id)

    return result


def _score_kandidaten(kandidaten, schwach_k_ids, ziel, anzahl):
    return _pick_aufgaben(kandidaten, schwach_k_ids, ziel, anzahl)


def grundwissen_schwaechen_schueler(schueler_id: int, kapitel: str, db: Session) -> dict:
    """
    Schwache Grundwissen-Einträge eines Schülers (nicht/teilweise gewusst in Abfragen
    oder Fehler in Tests), gefiltert auf das gewählte Kapitel, plus passende Aufgaben.
    """
    from app.models.grundwissen_abfrage import SchuelerGrundwissenAbfrage, AbfrageErgebnis
    from app.models.grundwissen import SchuelerGrundwissenFehler, Grundwissen, AufgabeGrundwissen
    from app.models.buchaufgabe import Buchaufgabe
    from app.models.aufgabe import Aufgabe

    schwach_ids: set[int] = set()

    abfragen = db.query(SchuelerGrundwissenAbfrage).filter(
        SchuelerGrundwissenAbfrage.schueler_id == schueler_id,
        SchuelerGrundwissenAbfrage.ergebnis.in_([
            AbfrageErgebnis.nicht_gewusst.value,
            AbfrageErgebnis.teilweise_gewusst.value,
        ]),
        SchuelerGrundwissenAbfrage.grundwissen_id.isnot(None),
    ).all()
    schwach_ids.update(a.grundwissen_id for a in abfragen)

    fehler = db.query(SchuelerGrundwissenFehler).filter(
        SchuelerGrundwissenFehler.schueler_id == schueler_id,
    ).all()
    schwach_ids.update(f.grundwissen_id for f in fehler)

    if not schwach_ids:
        return {"gw_eintraege": [], "buch_gw": [], "uebung": []}

    gw_eintraege = db.query(Grundwissen).filter(
        Grundwissen.id.in_(schwach_ids),
        Grundwissen.kapitel == kapitel,
    ).order_by(Grundwissen.unterkapitel).all()

    if not gw_eintraege:
        return {"gw_eintraege": [], "buch_gw": [], "uebung": []}

    gw_ids = {g.id for g in gw_eintraege}

    # Buchaufgaben im gleichen Kapitel/UK mit Grundwissen-Beschreibung
    seen_ba: set[int] = set()
    buch_gw = []
    for gw in gw_eintraege:
        for ba in db.query(Buchaufgabe).filter(
            Buchaufgabe.kapitel == kapitel,
            Buchaufgabe.unterkapitel == (gw.unterkapitel or ""),
            Buchaufgabe.beschreibung.ilike("grundwissen%"),
        ).all():
            if ba.id not in seen_ba:
                seen_ba.add(ba.id)
                buch_gw.append(ba)

    # Pool-Aufgaben mit Übung-Tag, die dieses Grundwissen als Vorkenntnis haben
    # oder direkt dieses Grundwissen repräsentieren
    via_vorkenntnis = db.query(Aufgabe).join(
        AufgabeGrundwissen, AufgabeGrundwissen.aufgabe_id == Aufgabe.id
    ).filter(
        AufgabeGrundwissen.grundwissen_id.in_(gw_ids),
        Aufgabe.tags.ilike("%übung%"),
    ).all()

    via_direkt = db.query(Aufgabe).filter(
        Aufgabe.grundwissen_id.in_(gw_ids),
        Aufgabe.tags.ilike("%übung%"),
    ).all()

    seen_a: set[int] = set()
    uebung = []
    for a in via_vorkenntnis + via_direkt:
        if a.id not in seen_a:
            seen_a.add(a.id)
            uebung.append(a)
    uebung.sort(key=lambda a: a.titel)

    return {"gw_eintraege": gw_eintraege, "buch_gw": buch_gw, "uebung": uebung}


def grundwissen_schwaechen_klasse(kl_id: int, kapitel: str, db: Session) -> dict:
    """Aggregiert schwache Grundwissen-Einträge aller Schüler der Klasse."""
    from app.models.schueler import Schueler
    from app.models.grundwissen import Grundwissen, AufgabeGrundwissen
    from app.models.buchaufgabe import Buchaufgabe
    from app.models.aufgabe import Aufgabe

    schueler = db.query(Schueler).filter(
        Schueler.klasse_id == kl_id, Schueler.geloescht_am.is_(None)
    ).all()

    alle_gw_ids: set[int] = set()
    for s in schueler:
        daten = grundwissen_schwaechen_schueler(s.id, kapitel, db)
        alle_gw_ids.update(g.id for g in daten["gw_eintraege"])

    if not alle_gw_ids:
        return {"gw_eintraege": [], "buch_gw": [], "uebung": []}

    gw_eintraege = db.query(Grundwissen).filter(
        Grundwissen.id.in_(alle_gw_ids)
    ).order_by(Grundwissen.unterkapitel).all()

    seen_ba: set[int] = set()
    buch_gw = []
    for gw in gw_eintraege:
        for ba in db.query(Buchaufgabe).filter(
            Buchaufgabe.kapitel == kapitel,
            Buchaufgabe.unterkapitel == (gw.unterkapitel or ""),
            Buchaufgabe.beschreibung.ilike("grundwissen%"),
        ).all():
            if ba.id not in seen_ba:
                seen_ba.add(ba.id)
                buch_gw.append(ba)

    via_vorkenntnis = db.query(Aufgabe).join(
        AufgabeGrundwissen, AufgabeGrundwissen.aufgabe_id == Aufgabe.id
    ).filter(
        AufgabeGrundwissen.grundwissen_id.in_(alle_gw_ids),
        Aufgabe.tags.ilike("%übung%"),
    ).all()

    via_direkt = db.query(Aufgabe).filter(
        Aufgabe.grundwissen_id.in_(alle_gw_ids),
        Aufgabe.tags.ilike("%übung%"),
    ).all()

    seen_a: set[int] = set()
    uebung = []
    for a in via_vorkenntnis + via_direkt:
        if a.id not in seen_a:
            seen_a.add(a.id)
            uebung.append(a)
    uebung.sort(key=lambda a: a.titel)

    return {"gw_eintraege": gw_eintraege, "buch_gw": buch_gw, "uebung": uebung}


def grundwissen_vorschlaege(kl_id: int, kapitel: str, db: Session) -> dict:
    """
    Schlägt Grundwissen-Aufgaben vor:
    - Buchaufgaben mit 'Grundwissen'-Beschreibung für dieses Kapitel,
      gefiltert nach Jahrgangsstufe über den Buchnamen
    - Aufgabenpool-Aufgaben mit Tag 'Übung', passend zur Jahrgangsstufe
    """
    from app.models.buchaufgabe import Buchaufgabe
    from app.models.aufgabe import Aufgabe
    from app.models.klasse import Klasse

    kl = db.get(Klasse, kl_id)
    js = kl.jahrgangsstufe

    buch_gw = (
        db.query(Buchaufgabe)
        .filter(
            Buchaufgabe.kapitel == kapitel,
            Buchaufgabe.beschreibung.ilike("grundwissen%"),
            Buchaufgabe.buch.ilike(f"%{js}%"),
        )
        .order_by(Buchaufgabe.unterkapitel, Buchaufgabe.aufgabennummer)
        .all()
    )

    uebung_qs = (
        db.query(Aufgabe)
        .filter(Aufgabe.tags.ilike("%übung%"))
        .order_by(Aufgabe.kapitel, Aufgabe.titel)
        .all()
    )
    # Kapitel-match bevorzugen, sonst alle mit Übung-Tag
    uebung_kap = [a for a in uebung_qs if a.kapitel == kapitel]
    uebung = uebung_kap if uebung_kap else uebung_qs

    return {"buch_gw": buch_gw, "uebung": uebung}


def empfehlungen_pro_schueler(
    klasse_id: int,
    kapitel: str,
    uk_anzahl: dict[str, int],
    db: Session,
    schwelle_schwach: float = 60.0,
) -> list[dict]:
    """
    Individuelle Aufgabenempfehlung pro Schüler.
    Gibt zurück: list von {schueler, uk_ergebnis, komps, afb_profil, ziel}
    """
    from app.models.schueler import Schueler
    from app.models.buchaufgabe import Buchaufgabe
    from app.services.kompetenzprofil import berechne_profil

    schueler_liste = (
        db.query(Schueler)
        .filter(Schueler.klasse_id == klasse_id, Schueler.geloescht_am.is_(None))
        .order_by(Schueler.nachname, Schueler.vorname)
        .all()
    )

    # Buchaufgaben pro UK vorausladen (einmalige DB-Abfragen)
    uk_kandidaten: dict[str, list] = {}
    for uk in uk_anzahl:
        if uk_anzahl[uk] > 0:
            uk_kandidaten[uk] = (
                db.query(Buchaufgabe)
                .filter(
                    Buchaufgabe.kapitel == kapitel,
                    Buchaufgabe.unterkapitel == uk,
                    Buchaufgabe.im_unterricht.is_(False),
                )
                .all()
            )

    results = []
    for s in schueler_liste:
        komps = berechne_profil(s.id, db)
        afb_prof = schueler_afb_profil(s.id, db)
        ziel = ziel_afb(afb_prof)
        schwach_k = {k_id for k_id, score in komps.items() if score < schwelle_schwach}

        uk_ergebnis = {
            uk: _score_kandidaten(uk_kandidaten[uk], schwach_k, ziel, anzahl)
            for uk, anzahl in uk_anzahl.items()
            if anzahl > 0 and uk in uk_kandidaten
        }
        results.append({
            "schueler": s,
            "uk_ergebnis": uk_ergebnis,
            "komps": komps,
            "afb_profil": afb_prof,
            "ziel": ziel,
            "gw_schwaechen": grundwissen_schwaechen_schueler(s.id, kapitel, db),
        })
    return results
