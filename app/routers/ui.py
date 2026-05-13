import csv
import io
import math
import unicodedata
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.aufgabe import AfbNiveau, Aufgabe, AufgabeKompetenz
from app.models.klasse import Klasse, Notensystem
from app.models.kompetenz import Kompetenz
from app.models.muendliche_note import MuendlicheNote
from app.models.schueler import Schueler
from app.models.schueler_ergebnis import SchuelerErgebnis
from app.models.schriftliche_leistung import LeistungAufgabe, LeistungArt, SchriftlicheLeistung
from app.models.schuljahr import Schuljahr
from app.services import notenberechnung, notenschnitt
from app.services import kompetenzprofil as kp_service
from app.services import empfehlung as emp_service
from app.templates_config import templates

router = APIRouter(prefix="/ui", include_in_schema=False)

REDIRECT = lambda url: RedirectResponse(url=url, status_code=303)


def _radar(scores_by_kuerzel: dict, size: int = 220, getestete: set | None = None) -> dict:
    """getestete: set of Kuerzel (z.B. {'K1','K3'}) die tatsächlich bewertet wurden.
    None = alle als getestet betrachten (Rückwärtskompatibilität)."""
    cx = cy = size / 2
    r = size / 2 - 35
    labels = ["K1", "K2", "K3", "K4", "K5", "K6"]
    n = 6
    grid, grid_half, axes, data, label_pos = [], [], [], [], []
    for i, lbl in enumerate(labels):
        a = -math.pi / 2 + 2 * math.pi * i / n
        ox, oy = cx + r * math.cos(a), cy + r * math.sin(a)
        hx, hy = cx + r * 0.5 * math.cos(a), cy + r * 0.5 * math.sin(a)
        grid.append(f"{ox:.1f},{oy:.1f}")
        grid_half.append(f"{hx:.1f},{hy:.1f}")
        axes.append({"x2": f"{ox:.1f}", "y2": f"{oy:.1f}"})
        pct = scores_by_kuerzel.get(lbl, 0) / 100
        dx, dy = cx + r * pct * math.cos(a), cy + r * pct * math.sin(a)
        data.append(f"{dx:.1f},{dy:.1f}")
        la = 1.3
        ist_getestet = (getestete is None) or (lbl in getestete)
        pct_val = scores_by_kuerzel.get(lbl, 0)
        label_pos.append({
            "x": f"{cx + r * la * math.cos(a):.1f}",
            "y": f"{cy + r * la * math.sin(a):.1f}",
            "text": lbl,
            "pct": pct_val,
            "getestet": ist_getestet,
            # Farbklasse: kein_test | kritisch | schwach | ok
            "status": ("kein_test" if not ist_getestet
                       else "kritisch" if pct_val == 0
                       else "schwach" if pct_val < 60
                       else "ok"),
        })
    return {
        "size": size, "cx": cx, "cy": cy,
        "grid": " ".join(grid), "grid_half": " ".join(grid_half),
        "data": " ".join(data), "axes": axes, "labels": label_pos,
    }


_STATUS_FARBE = {
    "kein_test": "#adb5bd",
    "kritisch":  "#6b0000",
    "schwach":   "#c1121f",
    "ok":        "#2d6a4f",
}


# ── Schuljahre ────────────────────────────────────────────────

@router.get("/schuljahre")
def schuljahre_liste(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(request, "schuljahre.html", {
        "schuljahre": db.query(Schuljahr).order_by(Schuljahr.name.desc()).all(),
        "msg": request.query_params.get("msg"),
        "err": request.query_params.get("err"),
    })


@router.post("/schuljahre")
def schuljahr_erstellen(name: str = Form(...), db: Session = Depends(get_db)):
    import re
    if not re.match(r"^\d{4}/\d{2}$", name):
        return REDIRECT("/ui/schuljahre?err=Ungültiges+Format+(z.B.+2025/26)")
    existing = db.query(Schuljahr).filter(Schuljahr.name == name).first()
    if existing:
        return REDIRECT("/ui/schuljahre?err=Schuljahr+existiert+bereits")
    db.add(Schuljahr(name=name))
    db.commit()
    return REDIRECT("/ui/schuljahre?msg=Schuljahr+angelegt")


@router.post("/schuljahre/{sj_id}/loeschen")
def schuljahr_loeschen(sj_id: int, db: Session = Depends(get_db)):
    obj = db.get(Schuljahr, sj_id)
    if obj:
        db.delete(obj)
        db.commit()
    return REDIRECT("/ui/schuljahre?msg=Schuljahr+gelöscht")


# ── Klassen ───────────────────────────────────────────────────

@router.get("/klassen")
def klassen_liste(request: Request, schuljahr_id: int, db: Session = Depends(get_db)):
    sj = db.get(Schuljahr, schuljahr_id)
    klassen = db.query(Klasse).filter(Klasse.schuljahr_id == schuljahr_id).order_by(Klasse.jahrgangsstufe, Klasse.buchstabe).all()
    return templates.TemplateResponse(request, "klassen_liste.html", {
        "schuljahr": sj, "klassen": klassen,
        "msg": request.query_params.get("msg"),
        "err": request.query_params.get("err"),
    })


@router.post("/klassen")
def klasse_erstellen(schuljahr_id: int = Form(...), jahrgangsstufe: int = Form(...), buchstabe: str = Form(...), db: Session = Depends(get_db)):
    if not (5 <= jahrgangsstufe <= 13):
        return REDIRECT(f"/ui/klassen?schuljahr_id={schuljahr_id}&err=Jahrgangsstufe+muss+5-13+sein")
    notensys = Notensystem.sechserskala if jahrgangsstufe <= 11 else Notensystem.punkte
    db.add(Klasse(jahrgangsstufe=jahrgangsstufe, buchstabe=buchstabe.lower(), schuljahr_id=schuljahr_id, notensystem=notensys))
    db.commit()
    return REDIRECT(f"/ui/klassen?schuljahr_id={schuljahr_id}&msg=Klasse+angelegt")


@router.post("/klassen/{kl_id}/loeschen")
def klasse_loeschen(kl_id: int, db: Session = Depends(get_db)):
    kl = db.get(Klasse, kl_id)
    sj_id = kl.schuljahr_id if kl else 0
    if kl:
        db.delete(kl)
        db.commit()
    return REDIRECT(f"/ui/klassen?schuljahr_id={sj_id}&msg=Klasse+gelöscht")


@router.get("/klassen/{kl_id}")
def klasse_detail(kl_id: int, request: Request, db: Session = Depends(get_db)):
    kl = db.get(Klasse, kl_id)
    sj = db.get(Schuljahr, kl.schuljahr_id)
    schueler = db.query(Schueler).filter(Schueler.klasse_id == kl_id).order_by(Schueler.nachname, Schueler.vorname).all()
    leistungen = db.query(SchriftlicheLeistung).filter(SchriftlicheLeistung.klasse_id == kl_id).order_by(SchriftlicheLeistung.datum.desc()).all()
    return templates.TemplateResponse(request, "klasse_detail.html", {
        "klasse": kl, "schuljahr": sj,
        "schueler": schueler, "leistungen": leistungen,
        "msg": request.query_params.get("msg"),
        "err": request.query_params.get("err"),
    })


# ── Schüler ───────────────────────────────────────────────────

@router.post("/schueler")
def schueler_erstellen(klasse_id: int = Form(...), vorname: str = Form(...), nachname: str = Form(...), db: Session = Depends(get_db)):
    db.add(Schueler(vorname=vorname, nachname=nachname, klasse_id=klasse_id))
    db.commit()
    return REDIRECT(f"/ui/klassen/{klasse_id}?msg=Schüler+hinzugefügt")


@router.post("/schueler/{s_id}/loeschen")
def schueler_loeschen(s_id: int, db: Session = Depends(get_db)):
    s = db.get(Schueler, s_id)
    kl_id = s.klasse_id if s else 0
    if s and not s.geloescht_am:
        s.geloescht_am = datetime.utcnow()
        db.commit()
    return REDIRECT(f"/ui/klassen/{kl_id}?msg=Schüler+entfernt")


@router.get("/schueler/{s_id}")
def schueler_dashboard(s_id: int, request: Request, db: Session = Depends(get_db)):
    s = db.get(Schueler, s_id)
    kl = db.get(Klasse, s.klasse_id)
    noten = db.query(MuendlicheNote).filter(MuendlicheNote.schueler_id == s_id, MuendlicheNote.geloescht_am.is_(None)).order_by(MuendlicheNote.datum.desc()).all()

    schnitt_data = type("S", (), {
        "schnitt_kleine_ln": notenschnitt.schnitt_kleine_ln(s_id, db),
        "schnitt_grosse_ln": notenschnitt.schnitt_grosse_ln(s_id, db),
        "gesamtschnitt": notenschnitt.gesamtschnitt(s_id, db),
    })()

    profil_data = kp_service.berechne_profil(s_id, db)
    meta = kp_service.metadaten(s_id, db)
    alle_k = db.query(Kompetenz).order_by(Kompetenz.kuerzel).all()
    scores_by_kuerzel = {}
    profil_scores = []
    getestete_kuerzels = set()
    for k in alle_k:
        pct = profil_data.get(k.id, 0)
        scores_by_kuerzel[k.kuerzel] = pct
        if k.id in profil_data:
            getestete_kuerzels.add(k.kuerzel)
            profil_scores.append(type("Sc", (), {
                "kompetenz_id": k.id, "kuerzel": k.kuerzel,
                "bezeichnung": k.bezeichnung, "prozent": pct,
                "status": ("kritisch" if pct == 0 else "schwach" if pct < 60 else "ok"),
            })())

    profil = type("P", (), {
        "scores": profil_scores,
        "leistungen_mit_daten": meta["leistungen_mit_daten"],
        "leistungen_gesamt": meta["leistungen_gesamt"],
    })()

    return templates.TemplateResponse(request, "schueler_dashboard.html", {
        "schueler": s, "klasse": kl,
        "muendliche_noten": noten, "schnitt": schnitt_data,
        "profil": profil, "radar": _radar(scores_by_kuerzel, getestete=getestete_kuerzels),
        "msg": request.query_params.get("msg"),
    })


@router.get("/schueler/{s_id}/empfehlung")
def schueler_empfehlung(s_id: int, request: Request, anzahl: int = 5, db: Session = Depends(get_db)):
    from app.config import settings
    s = db.get(Schueler, s_id)
    kl = db.get(Klasse, s.klasse_id)
    empfs = emp_service.empfehlungen(s_id, db, anzahl=anzahl)
    profil = kp_service.berechne_profil(s_id, db)
    alle_k = db.query(Kompetenz).order_by(Kompetenz.kuerzel).all()
    scores_by_kuerzel = {k.kuerzel: profil.get(k.id, 0) for k in alle_k}
    getestete_kuerzels = {k.kuerzel for k in alle_k if k.id in profil}
    return templates.TemplateResponse(request, "empfehlung.html", {
        "schueler": s, "klasse": kl,
        "empfehlungen": empfs,
        "anzahl": anzahl,
        "schwelle_schwach": settings.empfehlung_schwelle_schwach,
        "hat_daten": bool(profil),
        "radar": _radar(scores_by_kuerzel, getestete=getestete_kuerzels),
        "profil_vorhanden": bool(profil),
    })


@router.post("/schueler/{s_id}/muendliche-note")
def muendliche_note_erstellen(s_id: int, datum: str = Form(...), note: float = Form(...), gewichtung: float = Form(...), beschreibung: str = Form(""), db: Session = Depends(get_db)):
    s = db.get(Schueler, s_id)
    notensys = s.klasse.notensystem
    if notensys == Notensystem.sechserskala and not (1 <= note <= 6):
        return REDIRECT(f"/ui/schueler/{s_id}?msg=Note+außerhalb+Bereich")
    if notensys == Notensystem.punkte and not (0 <= note <= 15):
        return REDIRECT(f"/ui/schueler/{s_id}?msg=Note+außerhalb+Bereich")
    from datetime import date
    db.add(MuendlicheNote(schueler_id=s_id, datum=date.fromisoformat(datum), note=note, notensystem=notensys, gewichtung=gewichtung, beschreibung=beschreibung or None))
    db.commit()
    return REDIRECT(f"/ui/schueler/{s_id}")


@router.post("/muendliche-noten/{n_id}/loeschen")
def muendliche_note_loeschen(n_id: int, db: Session = Depends(get_db)):
    n = db.get(MuendlicheNote, n_id)
    s_id = n.schueler_id if n else 0
    if n and not n.geloescht_am:
        n.geloescht_am = datetime.utcnow()
        db.commit()
    return REDIRECT(f"/ui/schueler/{s_id}")


# ── Schriftliche Leistungen ───────────────────────────────────

@router.get("/leistung-neu")
def leistung_neu_form(klasse_id: int, request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(request, "leistung_neu.html", {
        "klasse": db.get(Klasse, klasse_id),
    })


@router.post("/schriftliche-leistungen")
def leistung_erstellen(
    klasse_id: int = Form(...), datum: str = Form(...), titel: str = Form(...),
    art: str = Form(...), detailliert: str = Form(""), gewichtung: float = Form(1.0),
    db: Session = Depends(get_db),
):
    from datetime import date
    ist_detailliert = (art == "schulaufgabe") or (detailliert == "true")
    l = SchriftlicheLeistung(
        klasse_id=klasse_id, datum=date.fromisoformat(datum), titel=titel,
        art=LeistungArt(art), detailliert=ist_detailliert, gewichtung=gewichtung,
    )
    db.add(l)
    db.commit()
    db.refresh(l)
    return REDIRECT(f"/ui/schriftliche-leistungen/{l.id}")


@router.get("/schriftliche-leistungen/{lid}")
def leistung_detail(lid: int, request: Request, db: Session = Depends(get_db)):
    l = db.get(SchriftlicheLeistung, lid)
    las = sorted(l.leistung_aufgaben, key=lambda x: x.reihenfolge)
    max_p = sum(la.aufgabe.max_punkte for la in las)
    la_ids = [la.id for la in las]
    has_ergebnisse = bool(la_ids and db.query(SchuelerErgebnis).filter(SchuelerErgebnis.leistung_aufgabe_id.in_(la_ids)).count() > 0) or \
                     bool(db.query(SchuelerErgebnis).filter(SchuelerErgebnis.schriftliche_leistung_id == lid).count() > 0)
    aufgaben_pool = db.query(Aufgabe).order_by(Aufgabe.titel).all()
    return templates.TemplateResponse(request, "leistung_detail.html", {
        "leistung": l, "leistung_aufgaben": las,
        "max_punkte_gesamt": max_p, "has_ergebnisse": has_ergebnisse,
        "aufgaben_pool": aufgaben_pool,
        "msg": request.query_params.get("msg"),
    })


@router.post("/schriftliche-leistungen/{lid}/aufgaben")
def aufgabe_zuordnen(lid: int, aufgabe_id: int = Form(...), aufgabennummer: str = Form(...), reihenfolge: int = Form(1), db: Session = Depends(get_db)):
    db.add(LeistungAufgabe(leistung_id=lid, aufgabe_id=aufgabe_id, aufgabennummer=aufgabennummer, reihenfolge=reihenfolge))
    db.commit()
    return REDIRECT(f"/ui/schriftliche-leistungen/{lid}")


@router.post("/schriftliche-leistungen/{lid}/aufgaben/{la_id}/entfernen")
def aufgabe_entfernen(lid: int, la_id: int, db: Session = Depends(get_db)):
    obj = db.query(LeistungAufgabe).filter(LeistungAufgabe.id == la_id, LeistungAufgabe.leistung_id == lid).first()
    if obj:
        db.delete(obj)
        db.commit()
    return REDIRECT(f"/ui/schriftliche-leistungen/{lid}")


@router.get("/schriftliche-leistungen/{lid}/punkte")
def punkte_matrix_form(lid: int, request: Request, db: Session = Depends(get_db)):
    l = db.get(SchriftlicheLeistung, lid)
    las = sorted(l.leistung_aufgaben, key=lambda x: x.reihenfolge)
    schueler = db.query(Schueler).filter(Schueler.klasse_id == l.klasse_id, Schueler.geloescht_am.is_(None)).order_by(Schueler.nachname, Schueler.vorname).all()
    punkte_map: dict = {}
    noten_map: dict = {}
    max_p = sum(la.aufgabe.max_punkte for la in las)
    for s in schueler:
        punkte_map[s.id] = {}
        for la in las:
            e = db.query(SchuelerErgebnis).filter(SchuelerErgebnis.schueler_id == s.id, SchuelerErgebnis.leistung_aufgabe_id == la.id).first()
            punkte_map[s.id][la.id] = e.erreichte_punkte if e else None
        summe = sum(v for v in punkte_map[s.id].values() if v is not None)
        if all(v is not None for v in punkte_map[s.id].values()) and las:
            noten_map[s.id] = notenberechnung.punkte_zu_note(summe, max_p)
    return templates.TemplateResponse(request, "punkte_matrix.html", {
        "leistung": l, "leistung_aufgaben": las,
        "schueler": schueler, "punkte_map": punkte_map, "noten_map": noten_map,
        "max_punkte_gesamt": max_p, "notensystem": l.klasse.notensystem,
    })


@router.post("/schriftliche-leistungen/{lid}/zelle")
def punkte_zelle_speichern(lid: int, schueler_id: int = Form(...), la_id: int = Form(...), punkte: float = Form(...), db: Session = Depends(get_db)):
    existing = db.query(SchuelerErgebnis).filter(SchuelerErgebnis.schueler_id == schueler_id, SchuelerErgebnis.leistung_aufgabe_id == la_id).first()
    if existing:
        existing.erreichte_punkte = punkte
    else:
        db.add(SchuelerErgebnis(schueler_id=schueler_id, leistung_aufgabe_id=la_id, erreichte_punkte=punkte))
    db.commit()
    return ""  # HTMX hx-swap="none"


@router.get("/schriftliche-leistungen/{lid}/pauschal")
def pauschal_form(lid: int, request: Request, db: Session = Depends(get_db)):
    l = db.get(SchriftlicheLeistung, lid)
    schueler = db.query(Schueler).filter(Schueler.klasse_id == l.klasse_id, Schueler.geloescht_am.is_(None)).order_by(Schueler.nachname, Schueler.vorname).all()
    noten_map = {}
    for s in schueler:
        e = db.query(SchuelerErgebnis).filter(SchuelerErgebnis.schueler_id == s.id, SchuelerErgebnis.schriftliche_leistung_id == lid).first()
        noten_map[s.id] = e.pauschalnote if e else None
    return templates.TemplateResponse(request, "pauschal_form.html", {
        "leistung": l, "schueler": schueler,
        "noten_map": noten_map, "notensystem": l.klasse.notensystem,
    })


@router.post("/schriftliche-leistungen/{lid}/pauschal")
async def pauschal_speichern(lid: int, request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    l = db.get(SchriftlicheLeistung, lid)
    db.query(SchuelerErgebnis).filter(SchuelerErgebnis.schriftliche_leistung_id == lid).delete()
    for key, val in form.items():
        if key.startswith("note_") and val:
            s_id = int(key.split("_")[1])
            db.add(SchuelerErgebnis(schueler_id=s_id, schriftliche_leistung_id=lid, pauschalnote=float(val)))
    db.commit()
    return REDIRECT(f"/ui/klassen/{l.klasse_id}?msg=Noten+gespeichert")


def _auswertung_extra_stats(lid: int, db):
    """Berechnet AFB/Kompetenz-Aufbau und Durchschnittswerte für die Auswertungsseite."""
    from app.models.schriftliche_leistung import LeistungAufgabe
    from app.models.schueler_ergebnis import SchuelerErgebnis
    import sqlalchemy as sa

    las = (
        db.query(LeistungAufgabe)
        .filter(LeistungAufgabe.leistung_id == lid)
        .order_by(LeistungAufgabe.reihenfolge)
        .all()
    )

    aufgaben_avg: dict = {}
    afb_max: dict = {}
    komp_max: dict = {}
    afb_sum: dict = {}   # afb -> [sum_erreicht, sum_max]
    komp_sum: dict = {}  # kuerzel -> [sum_erreicht_w, sum_max_w]

    for la in las:
        afb = la.aufgabe.afb_niveau.value
        mp = la.aufgabe.max_punkte

        # Aufbau: max_punkte per AFB
        afb_max[afb] = round(afb_max.get(afb, 0.0) + mp, 4)

        # Aufbau: max_punkte per Kompetenz (weighted by gewichtung)
        for ak in la.aufgabe.kompetenzen:
            kuerzel = ak.kompetenz.kuerzel
            komp_max[kuerzel] = round(komp_max.get(kuerzel, 0.0) + mp * ak.gewichtung, 4)

        # Ergebnisse dieser Aufgabe
        ergebnisse = (
            db.query(SchuelerErgebnis)
            .filter(
                SchuelerErgebnis.leistung_aufgabe_id == la.id,
                SchuelerErgebnis.erreichte_punkte.isnot(None),
            )
            .all()
        )
        if not ergebnisse:
            continue

        # Aufgaben-Durchschnitt
        aufgaben_avg[la.aufgabennummer] = round(
            sum(e.erreichte_punkte for e in ergebnisse) / len(ergebnisse), 1
        )

        n = len(ergebnisse)
        sum_e = sum(e.erreichte_punkte for e in ergebnisse)

        # AFB-Leistung
        if afb not in afb_sum:
            afb_sum[afb] = [0.0, 0.0]
        afb_sum[afb][0] += sum_e
        afb_sum[afb][1] += mp * n

        # Kompetenz-Leistung (jeder Schüler trägt anteilig bei)
        for ak in la.aufgabe.kompetenzen:
            kuerzel = ak.kompetenz.kuerzel
            if kuerzel not in komp_sum:
                komp_sum[kuerzel] = [0.0, 0.0]
            komp_sum[kuerzel][0] += sum_e * ak.gewichtung
            komp_sum[kuerzel][1] += mp * ak.gewichtung * n

    afb_avg_pct = {
        afb: round(v[0] / v[1] * 100, 1) if v[1] > 0 else 0
        for afb, v in afb_sum.items()
    }
    komp_avg_pct = {
        k: round(v[0] / v[1] * 100, 1) if v[1] > 0 else 0
        for k, v in sorted(komp_sum.items())
    }

    return {
        "aufgaben_avg": aufgaben_avg,
        "afb_max": afb_max,
        "komp_max": dict(sorted(komp_max.items())),
        "afb_avg_pct": afb_avg_pct,
        "komp_avg_pct": komp_avg_pct,
    }


@router.get("/schriftliche-leistungen/{lid}/auswertung")
def auswertung_view(lid: int, request: Request, db: Session = Depends(get_db)):
    from app.routers.schriftliche_leistung import auswertung as api_auswertung
    data = api_auswertung(lid, db)
    extra = _auswertung_extra_stats(lid, db)
    return templates.TemplateResponse(request, "auswertung.html", {"auswertung": data, **extra})


@router.get("/schriftliche-leistungen/{lid}/auswertung.pdf")
def auswertung_pdf(lid: int, db: Session = Depends(get_db)):
    from app.routers.schriftliche_leistung import auswertung as api_auswertung
    from app.services.pdf_export import _jinja_env
    from fastapi.responses import Response
    import weasyprint
    data = api_auswertung(lid, db)
    html = _jinja_env().get_template("pdf_auswertung.html").render(auswertung=data)
    pdf_bytes = weasyprint.HTML(string=html, base_url=".").write_pdf()
    name = f"Notenspiegel_{data.titel}.pdf".replace(" ", "_")
    return Response(pdf_bytes, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/schriftliche-leistungen/{lid}/ehz.pdf")
def ehz_pdf_view(lid: int, db: Session = Depends(get_db)):
    from app.models.schriftliche_leistung import SchriftlicheLeistung, LeistungAufgabe
    from app.services.pdf_export import ehz_pdf
    from fastapi.responses import Response
    leistung = db.get(SchriftlicheLeistung, lid)
    klasse = db.get(Klasse, leistung.klasse_id)
    aufgaben = (
        db.query(LeistungAufgabe)
        .filter(LeistungAufgabe.leistung_id == lid)
        .order_by(LeistungAufgabe.reihenfolge)
        .all()
    )
    max_punkte = sum(la.aufgabe.max_punkte for la in aufgaben)
    pdf_bytes = ehz_pdf({
        "leistung": leistung,
        "klasse": klasse,
        "aufgaben": aufgaben,
        "max_punkte": max_punkte,
    })
    name = f"EHZ_{leistung.titel}.pdf".replace(" ", "_")
    return Response(pdf_bytes, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


# ── Schüler-Verlauf ───────────────────────────────────────────

def _verlauf_eintrag(schueler_id: int, leistung, db):
    from app.models.schueler_ergebnis import SchuelerErgebnis
    from app.services.notenberechnung import punkte_zu_note, ist_grenzfall

    if leistung.detailliert and leistung.leistung_aufgaben:
        las = sorted(leistung.leistung_aufgaben, key=lambda x: x.reihenfolge)
        max_p = sum(la.aufgabe.max_punkte for la in las)
        summe, alle = 0.0, True
        for la in las:
            e = db.query(SchuelerErgebnis).filter(
                SchuelerErgebnis.schueler_id == schueler_id,
                SchuelerErgebnis.leistung_aufgabe_id == la.id,
            ).first()
            if e and e.erreichte_punkte is not None:
                summe += e.erreichte_punkte
            else:
                alle = False
        if alle and max_p > 0:
            return {"leistung": leistung, "summe": summe, "max": max_p,
                    "note": punkte_zu_note(summe, max_p),
                    "prozent": round(summe / max_p * 100, 1),
                    "grenzfall": ist_grenzfall(summe, max_p)}
        return {"leistung": leistung, "summe": None, "max": max_p,
                "note": None, "prozent": None, "grenzfall": False}
    else:
        e = db.query(SchuelerErgebnis).filter(
            SchuelerErgebnis.schueler_id == schueler_id,
            SchuelerErgebnis.schriftliche_leistung_id == leistung.id,
        ).first()
        note = e.pauschalnote if e else None
        return {"leistung": leistung, "summe": None, "max": None,
                "note": note, "prozent": None, "grenzfall": False}


def _trend_svg(eintraege: list) -> dict | None:
    punkte = [(i, e) for i, e in enumerate(eintraege) if e["prozent"] is not None]
    if len(punkte) < 2:
        return None
    w, h, padl, padt = 500, 100, 35, 12
    n = len(eintraege)

    def to_x(i): return padl + i / max(n - 1, 1) * (w - padl - 10)
    def to_y(pct): return padt + (100 - pct) / 100 * (h - padt - 8)

    coords = [(to_x(i), to_y(e["prozent"])) for i, e in punkte]
    polyline = " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)
    return {
        "w": w, "h": h,
        "polyline": polyline,
        "punkte": [
            {"x": f"{x:.1f}", "y": f"{y:.1f}",
             "y_label": f"{y + 12:.1f}",
             "pct": eintraege[i]["prozent"],
             "titel": eintraege[i]["leistung"].titel[:14],
             "art": eintraege[i]["leistung"].art.value
             if hasattr(eintraege[i]["leistung"].art, "value")
             else str(eintraege[i]["leistung"].art)}
            for (i, e), (x, y) in zip(punkte, coords)
        ],
    }


@router.get("/schueler/{s_id}/verlauf")
def schueler_verlauf_view(s_id: int, request: Request, db: Session = Depends(get_db)):
    from app.models.schriftliche_leistung import SchriftlicheLeistung
    s = db.get(Schueler, s_id)
    kl = db.get(Klasse, s.klasse_id)
    leistungen = (
        db.query(SchriftlicheLeistung)
        .filter(SchriftlicheLeistung.klasse_id == kl.id)
        .order_by(SchriftlicheLeistung.datum)
        .all()
    )
    eintraege = [_verlauf_eintrag(s_id, l, db) for l in leistungen]
    schnitt_data = type("S", (), {
        "schnitt_kleine_ln": notenschnitt.schnitt_kleine_ln(s_id, db),
        "schnitt_grosse_ln": notenschnitt.schnitt_grosse_ln(s_id, db),
        "gesamtschnitt": notenschnitt.gesamtschnitt(s_id, db),
    })()
    return templates.TemplateResponse(request, "schueler_verlauf.html", {
        "schueler": s, "klasse": kl,
        "eintraege": eintraege,
        "trend": _trend_svg(eintraege),
        "schnitt": schnitt_data,
    })


# ── Zeugnis ───────────────────────────────────────────────────

def _zeugnis_daten(kl_id: int, db):
    from app.models.schriftliche_leistung import SchriftlicheLeistung
    from app.models.schueler_ergebnis import SchuelerErgebnis
    from app.services.notenberechnung import punkte_zu_note
    from app.models.schuljahr import Schuljahr

    kl = db.get(Klasse, kl_id)
    schuljahr = db.get(Schuljahr, kl.schuljahr_id)
    schueler_liste = (
        db.query(Schueler)
        .filter(Schueler.klasse_id == kl_id, Schueler.geloescht_am.is_(None))
        .order_by(Schueler.nachname, Schueler.vorname)
        .all()
    )
    leistungen = (
        db.query(SchriftlicheLeistung)
        .filter(SchriftlicheLeistung.klasse_id == kl_id)
        .order_by(SchriftlicheLeistung.datum)
        .all()
    )

    zeilen = []
    for s in schueler_liste:
        noten_pro_leistung = {}
        for l in leistungen:
            e = _verlauf_eintrag(s.id, l, db)
            if e["note"] is not None:
                noten_pro_leistung[l.id] = e["note"]
        zeilen.append({
            "schueler": s,
            "schnitt_grosse": notenschnitt.schnitt_grosse_ln(s.id, db),
            "schnitt_kleine": notenschnitt.schnitt_kleine_ln(s.id, db),
            "gesamt": notenschnitt.gesamtschnitt(s.id, db),
            "noten_pro_leistung": noten_pro_leistung,
        })
    return kl, schuljahr, leistungen, zeilen


@router.get("/klassen/{kl_id}/zeugnis")
def zeugnis_view(kl_id: int, request: Request, db: Session = Depends(get_db)):
    kl, schuljahr, leistungen, zeilen = _zeugnis_daten(kl_id, db)
    return templates.TemplateResponse(request, "zeugnis.html", {
        "klasse": kl, "schuljahr": schuljahr,
        "leistungen": leistungen, "zeilen": zeilen,
    })


@router.get("/klassen/{kl_id}/zeugnis.pdf")
def zeugnis_pdf(kl_id: int, db: Session = Depends(get_db)):
    from app.services.pdf_export import _jinja_env
    from fastapi.responses import Response
    import weasyprint
    kl, schuljahr, leistungen, zeilen = _zeugnis_daten(kl_id, db)
    html = _jinja_env().get_template("pdf_zeugnis.html").render(
        klasse=kl, schuljahr=schuljahr.name if schuljahr else "",
        leistungen=leistungen, zeilen=zeilen,
    )
    pdf_bytes = weasyprint.HTML(string=html, base_url=".").write_pdf()
    name = f"Zeugnis_{kl.name}.pdf".replace(" ", "_")
    return Response(pdf_bytes, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/schueler/{s_id}/schulaufgabe/{lid}/empfehlung")
def schulaufgabe_empfehlung_view(s_id: int, lid: int, request: Request, db: Session = Depends(get_db)):
    from app.services.schulaufgabe_empfehlung import empfehlungen_fuer_schulaufgabe
    schueler, leistung, bloecke = empfehlungen_fuer_schulaufgabe(s_id, lid, db)
    profil = kp_service.berechne_profil(s_id, db)
    alle_k = db.query(Kompetenz).order_by(Kompetenz.kuerzel).all()
    scores_by_kuerzel = {k.kuerzel: profil.get(k.id, 0) for k in alle_k}
    getestete_kuerzels = {k.kuerzel for k in alle_k if k.id in profil}
    return templates.TemplateResponse(request, "schulaufgabe_empfehlung.html", {
        "schueler": schueler, "leistung": leistung, "bloecke": bloecke,
        "radar": _radar(scores_by_kuerzel, getestete=getestete_kuerzels),
        "profil_vorhanden": bool(profil),
    })


def _radar_fuer_schueler(s_id: int, db) -> tuple[dict, bool]:
    profil = kp_service.berechne_profil(s_id, db)
    alle_k = db.query(Kompetenz).order_by(Kompetenz.kuerzel).all()
    scores = {k.kuerzel: profil.get(k.id, 0) for k in alle_k}
    getestete = {k.kuerzel for k in alle_k if k.id in profil}
    return _radar(scores, getestete=getestete), bool(profil)


@router.get("/schueler/{s_id}/schulaufgabe/{lid}/empfehlung.pdf")
def schulaufgabe_empfehlung_pdf_einzeln(s_id: int, lid: int, db: Session = Depends(get_db)):
    from app.services.schulaufgabe_empfehlung import empfehlungen_fuer_schulaufgabe
    from app.services.pdf_export import empfehlung_pdf
    from fastapi.responses import Response
    schueler, leistung, bloecke = empfehlungen_fuer_schulaufgabe(s_id, lid, db)
    klasse = db.get(Klasse, schueler.klasse_id)
    radar, profil_vorhanden = _radar_fuer_schueler(s_id, db)
    items = [{"schueler": schueler, "klasse": klasse, "leistung": leistung,
              "bloecke": bloecke, "radar": radar, "profil_vorhanden": profil_vorhanden}]
    pdf_bytes = empfehlung_pdf(items)
    dateiname = f"Uebung_{schueler.nachname}_{leistung.titel}.pdf".replace(" ", "_")
    return Response(pdf_bytes, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{dateiname}"'})


@router.get("/schriftliche-leistungen/{lid}/empfehlung-alle.pdf")
def schulaufgabe_empfehlung_pdf_alle(lid: int, db: Session = Depends(get_db)):
    from app.services.schulaufgabe_empfehlung import empfehlungen_fuer_schulaufgabe
    from app.services.pdf_export import empfehlung_pdf
    from app.models.schriftliche_leistung import SchriftlicheLeistung
    from fastapi.responses import Response
    leistung = db.get(SchriftlicheLeistung, lid)
    schueler_liste = (
        db.query(Schueler)
        .filter(Schueler.klasse_id == leistung.klasse_id, Schueler.geloescht_am.is_(None))
        .order_by(Schueler.nachname, Schueler.vorname)
        .all()
    )
    klasse = db.get(Klasse, leistung.klasse_id)
    items = []
    for s in schueler_liste:
        _, _, bloecke = empfehlungen_fuer_schulaufgabe(s.id, lid, db)
        radar, profil_vorhanden = _radar_fuer_schueler(s.id, db)
        items.append({"schueler": s, "klasse": klasse, "leistung": leistung,
                      "bloecke": bloecke, "radar": radar, "profil_vorhanden": profil_vorhanden})
    pdf_bytes = empfehlung_pdf(items)
    dateiname = f"Uebung_Klasse_{leistung.titel}.pdf".replace(" ", "_")
    return Response(pdf_bytes, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{dateiname}"'})


# ── Aufgabenpool ──────────────────────────────────────────────

@router.get("/aufgaben")
def aufgaben_pool(request: Request, db: Session = Depends(get_db)):
    aufgaben = db.query(Aufgabe).order_by(Aufgabe.erstellt_am.desc()).all()
    return templates.TemplateResponse(request, "aufgaben_pool.html", {
        "aufgaben": aufgaben,
        "msg": request.query_params.get("msg"),
    })


@router.get("/aufgaben/suche")
def aufgaben_suche(request: Request, q: str = "", afb: str = "", js: str = "", db: Session = Depends(get_db)):
    import sqlalchemy as sa
    query = db.query(Aufgabe)
    if q:
        term = f"%{q}%"
        query = query.filter(sa.or_(Aufgabe.titel.ilike(term), Aufgabe.aufgabenstellung.ilike(term), Aufgabe.tags.ilike(term)))
    if afb:
        query = query.filter(Aufgabe.afb_niveau == AfbNiveau(afb))
    if js and js.isdigit():
        query = query.filter(Aufgabe.jahrgangsstufe == int(js))
    return templates.TemplateResponse(request, "htmx_aufgaben.html", {
        "aufgaben": query.order_by(Aufgabe.erstellt_am.desc()).all(),
    })


@router.get("/aufgaben/meta/unterkapitel")
def aufgaben_meta_unterkapitel(kapitel: str = "", db: Session = Depends(get_db)):
    from app.models.buchaufgabe import Buchaufgabe
    q = db.query(Buchaufgabe.unterkapitel).filter(Buchaufgabe.unterkapitel != "")
    if kapitel:
        q = q.filter(Buchaufgabe.kapitel == kapitel)
    werte = sorted(set(r[0] for r in q.distinct().all()))
    opts = '<option value="">– keine –</option>' + "".join(
        f'<option value="{v}">{v}</option>' for v in werte
    )
    from fastapi.responses import HTMLResponse
    return HTMLResponse(opts)


@router.get("/aufgaben/meta/beschreibungen")
def aufgaben_meta_beschreibungen(kapitel: str = "", unterkapitel: str = "", db: Session = Depends(get_db)):
    from app.models.buchaufgabe import Buchaufgabe
    q = db.query(Buchaufgabe.beschreibung).filter(
        Buchaufgabe.beschreibung.isnot(None),
        Buchaufgabe.beschreibung != "",
    )
    if kapitel:
        q = q.filter(Buchaufgabe.kapitel == kapitel)
    if unterkapitel:
        q = q.filter(Buchaufgabe.unterkapitel == unterkapitel)
    werte = sorted(set(r[0] for r in q.distinct().all()))
    opts = '<option value="">– alle –</option>' + "".join(
        f'<option value="{v}">{v}</option>' for v in werte
    )
    from fastapi.responses import HTMLResponse
    return HTMLResponse(opts)


def _kapitel_liste(db):
    from app.models.buchaufgabe import Buchaufgabe
    return sorted(set(r[0] for r in db.query(Buchaufgabe.kapitel).distinct().all()))


@router.get("/aufgaben/neu")
def aufgabe_neu_form(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(request, "aufgabe_neu.html", {
        "kapitel_liste": _kapitel_liste(db),
    })


@router.get("/aufgaben/meta/jahrgangsstufe")
def aufgaben_meta_jahrgangsstufe(kapitel: str = "", db: Session = Depends(get_db)):
    from app.models.buchaufgabe import Buchaufgabe
    from fastapi.responses import HTMLResponse
    import re as _re
    if not kapitel:
        return HTMLResponse("")
    row = db.query(Buchaufgabe.buch).filter(Buchaufgabe.kapitel == kapitel).first()
    if row:
        m = _re.search(r'\b(\d{1,2})\b', row[0])
        if m and 5 <= int(m.group(1)) <= 13:
            return HTMLResponse(m.group(1))
    return HTMLResponse("")


@router.post("/aufgaben")
def aufgabe_erstellen(
    titel: str = Form(...), aufgabenstellung: str = Form(...), loesung: str = Form(""),
    max_punkte: float = Form(...), afb_niveau: str = Form(...), tags: str = Form(""),
    jahrgangsstufe: str = Form(""), kapitel: str = Form(""), unterkapitel: str = Form(""),
    db: Session = Depends(get_db),
):
    js = int(jahrgangsstufe) if jahrgangsstufe.strip().isdigit() else None
    a = Aufgabe(titel=titel, aufgabenstellung=aufgabenstellung, loesung=loesung or None,
                max_punkte=max_punkte, afb_niveau=AfbNiveau(afb_niveau), tags=tags or None,
                jahrgangsstufe=js, kapitel=kapitel or None, unterkapitel=unterkapitel or None)
    db.add(a)
    db.commit()
    db.refresh(a)
    return REDIRECT(f"/ui/aufgaben/{a.id}?msg=Aufgabe+angelegt")


@router.post("/aufgaben/{a_id}/loeschen")
def aufgabe_loeschen(a_id: int, db: Session = Depends(get_db)):
    obj = db.get(Aufgabe, a_id)
    if obj:
        db.delete(obj)
        db.commit()
    return REDIRECT("/ui/aufgaben?msg=Aufgabe+gelöscht")


@router.get("/aufgaben/{a_id}")
def aufgabe_detail(a_id: int, request: Request, db: Session = Depends(get_db)):
    from app.models.buchaufgabe import Buchaufgabe
    a = db.get(Aufgabe, a_id)
    alle_k = db.query(Kompetenz).order_by(Kompetenz.kuerzel).all()
    aks = db.query(AufgabeKompetenz).filter(AufgabeKompetenz.aufgabe_id == a_id).all()
    kompetenzen_map = {ak.kompetenz_id: ak.gewichtung for ak in aks}
    kap_liste = _kapitel_liste(db)
    uk_liste = sorted(set(r[0] for r in db.query(Buchaufgabe.unterkapitel)
                          .filter(Buchaufgabe.kapitel == a.kapitel, Buchaufgabe.unterkapitel != "")
                          .distinct().all())) if a.kapitel else []
    from app.models.grundwissen import AufgabeGrundwissen
    gw_eintraege = db.query(AufgabeGrundwissen).filter(AufgabeGrundwissen.aufgabe_id == a_id).all()
    return templates.TemplateResponse(request, "aufgabe_detail.html", {
        "aufgabe": a,
        "kompetenzen_aktuell": aks, "alle_kompetenzen": alle_k,
        "kompetenzen_map": kompetenzen_map,
        "kapitel_liste": kap_liste, "unterkapitel_liste": uk_liste,
        "grundwissen_aktuell": gw_eintraege,
        "msg": request.query_params.get("msg"),
        "err": request.query_params.get("err"),
    })


@router.post("/aufgaben/{a_id}/bearbeiten")
def aufgabe_bearbeiten(
    a_id: int, titel: str = Form(...), aufgabenstellung: str = Form(...),
    loesung: str = Form(""), max_punkte: float = Form(...),
    afb_niveau: str = Form(...), tags: str = Form(""),
    jahrgangsstufe: str = Form(""), kapitel: str = Form(""), unterkapitel: str = Form(""),
    db: Session = Depends(get_db),
):
    a = db.get(Aufgabe, a_id)
    a.titel = titel; a.aufgabenstellung = aufgabenstellung
    a.loesung = loesung or None; a.max_punkte = max_punkte
    a.afb_niveau = AfbNiveau(afb_niveau); a.tags = tags or None
    a.jahrgangsstufe = int(jahrgangsstufe) if jahrgangsstufe.strip().isdigit() else None
    a.kapitel = kapitel or None; a.unterkapitel = unterkapitel or None
    db.commit()
    return REDIRECT(f"/ui/aufgaben/{a_id}?msg=Gespeichert")


@router.post("/aufgaben/{a_id}/kompetenzen")
async def aufgabe_kompetenzen_setzen(a_id: int, request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    alle_k = db.query(Kompetenz).all()
    eintraege = []
    for k in alle_k:
        val = form.get(f"gew_{k.id}", "")
        if val:
            try:
                gew = float(val)
                if gew > 0:
                    eintraege.append((k.id, gew))
            except ValueError:
                pass
    if eintraege:
        gesamt = sum(g for _, g in eintraege)
        if abs(gesamt - 1.0) > 0.01:
            return REDIRECT(f"/ui/aufgaben/{a_id}?err=Gewichtungen+müssen+1.0+ergeben+(aktuell+{gesamt:.2f})")
    db.query(AufgabeKompetenz).filter(AufgabeKompetenz.aufgabe_id == a_id).delete()
    for k_id, gew in eintraege:
        db.add(AufgabeKompetenz(aufgabe_id=a_id, kompetenz_id=k_id, gewichtung=gew))
    db.commit()
    return REDIRECT(f"/ui/aufgaben/{a_id}?msg=Kompetenzen+gespeichert")


# ── CSV-Import ────────────────────────────────────────────────

def _normalize(s: str) -> str:
    return unicodedata.normalize("NFC", s.strip().lower())


@router.post("/klassen/{kl_id}/schueler-import")
async def schueler_csv_import(kl_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    raw = await file.read()
    content = raw.decode("utf-8", errors="replace").lstrip("﻿")
    reader = csv.reader(io.StringIO(content))
    hinzugefuegt = uebersprungen = 0
    for row in reader:
        if len(row) < 2:
            continue
        nachname, vorname = row[0].strip(), row[1].strip()
        if not nachname or not vorname:
            continue
        if _normalize(nachname) in ("nachname", "name", "familienname"):
            continue
        existing = db.query(Schueler).filter(
            Schueler.klasse_id == kl_id,
            Schueler.nachname.ilike(nachname),
            Schueler.vorname.ilike(vorname),
            Schueler.geloescht_am.is_(None),
        ).first()
        if existing:
            uebersprungen += 1
        else:
            db.add(Schueler(vorname=vorname, nachname=nachname, klasse_id=kl_id))
            hinzugefuegt += 1
    db.commit()
    msg = f"{hinzugefuegt}+Schüler+hinzugefügt"
    if uebersprungen:
        msg += f",+{uebersprungen}+übersprungen"
    return REDIRECT(f"/ui/klassen/{kl_id}?msg={msg}")


@router.post("/schriftliche-leistungen/{lid}/punkte-import")
async def punkte_csv_import_vorschau(lid: int, request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)):
    leistung = db.get(SchriftlicheLeistung, lid)
    if not leistung or not leistung.detailliert:
        return REDIRECT(f"/ui/schriftliche-leistungen/{lid}")

    las = sorted(leistung.leistung_aufgaben, key=lambda x: x.reihenfolge)
    la_by_nr = {la.aufgabennummer.lower(): la for la in las}

    raw = await file.read()
    content = raw.decode("utf-8", errors="replace").lstrip("﻿")
    rows = list(csv.reader(io.StringIO(content)))
    if not rows:
        return REDIRECT(f"/ui/schriftliche-leistungen/{lid}?err=Leere+CSV")

    header = [c.strip().lower() for c in rows[0]]
    aufgaben_cols = {i: la_by_nr[h] for i, h in enumerate(header) if h in la_by_nr}

    schueler_liste = db.query(Schueler).filter(
        Schueler.klasse_id == leistung.klasse_id, Schueler.geloescht_am.is_(None)
    ).all()
    schueler_by_name = {(_normalize(s.nachname), _normalize(s.vorname)): s for s in schueler_liste}

    gematchte, nicht_gefunden = [], []
    for row in rows[1:]:
        if len(row) < 2 or not row[0].strip():
            continue
        nachname, vorname = row[0].strip(), row[1].strip()
        schueler = schueler_by_name.get((_normalize(nachname), _normalize(vorname)))
        punkte_row, la_ids_row = {}, {}
        for col_idx, la in aufgaben_cols.items():
            raw = row[col_idx].strip().replace(",", ".") if col_idx < len(row) else ""
            try:
                punkte_row[la.aufgabennummer] = float(raw) if raw else None
            except ValueError:
                punkte_row[la.aufgabennummer] = None
            la_ids_row[la.aufgabennummer] = la.id
        if schueler:
            gematchte.append({"schueler": schueler, "punkte": punkte_row, "la_ids": la_ids_row})
        else:
            nicht_gefunden.append(f"{nachname}, {vorname}")

    return templates.TemplateResponse(request, "punkte_import_vorschau.html", {
        "leistung": leistung, "aufgaben": las,
        "gematchte": gematchte, "nicht_gefunden": nicht_gefunden,
    })


@router.post("/schriftliche-leistungen/{lid}/punkte-import/bestaetigen")
async def punkte_import_bestaetigen(lid: int, request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    count = 0
    for key, val in form.items():
        if not key.startswith("s_") or not val:
            continue
        parts = key.split("_")
        if len(parts) != 3:
            continue
        try:
            s_id, la_id, punkte = int(parts[1]), int(parts[2]), float(str(val).replace(",", "."))
        except ValueError:
            continue
        existing = db.query(SchuelerErgebnis).filter(
            SchuelerErgebnis.schueler_id == s_id,
            SchuelerErgebnis.leistung_aufgabe_id == la_id,
        ).first()
        if existing:
            existing.erreichte_punkte = punkte
        else:
            db.add(SchuelerErgebnis(schueler_id=s_id, leistung_aufgabe_id=la_id, erreichte_punkte=punkte))
        count += 1
    db.commit()
    return REDIRECT(f"/ui/schriftliche-leistungen/{lid}/auswertung?msg={count}+Einträge+importiert")


# ── Kapitel-Empfehlung (Klasse) ───────────────────────────────

def _kapitel_empfehlung_kontext(kl_id: int, kapitel: str, uk_anzahl: dict, db):
    from app.services.kapitel_empfehlung import empfehlungen_fuer_kapitel
    from app.models.kompetenz import Kompetenz
    ergebnis, komps, afb_profil, ziel = empfehlungen_fuer_kapitel(kl_id, kapitel, uk_anzahl, db)
    alle_k = db.query(Kompetenz).order_by(Kompetenz.kuerzel).all()
    schwach_ids = {k_id for k_id, score in komps.items() if score < 60}
    komp_map = {k.id: k.kuerzel for k in alle_k}
    return ergebnis, komps, afb_profil, ziel, alle_k, schwach_ids, komp_map


def _parse_uk_anzahl(form) -> dict[str, int]:
    uk_namen = form.getlist("uk")
    anz_werte = form.getlist("anz")
    return {uk: int(anz or 0) for uk, anz in zip(uk_namen, anz_werte)}


@router.get("/klassen/{kl_id}/schueler-kapitelempfehlung")
def schueler_kapitel_empfehlung_form(kl_id: int, request: Request, db: Session = Depends(get_db)):
    kl = db.get(Klasse, kl_id)
    return templates.TemplateResponse(request, "schueler_kapitel_empfehlung.html", {
        "klasse": kl, "kapitel_liste": _kapitel_liste(db),
    })


@router.post("/klassen/{kl_id}/schueler-kapitelempfehlung")
async def schueler_kapitel_empfehlung_post(kl_id: int, request: Request, db: Session = Depends(get_db)):
    from app.services.kapitel_empfehlung import empfehlungen_pro_schueler
    form = await request.form()
    kapitel = form.get("kapitel", "")
    uk_anzahl = _parse_uk_anzahl(form)
    kl = db.get(Klasse, kl_id)
    ergebnisse = empfehlungen_pro_schueler(kl_id, kapitel, uk_anzahl, db)
    return templates.TemplateResponse(request, "schueler_kapitel_empfehlung.html", {
        "klasse": kl, "kapitel_liste": _kapitel_liste(db),
        "gewaehltes_kapitel": kapitel,
        "ergebnisse": ergebnisse,
        "uk_anzahl_hidden": uk_anzahl,
        "unterkapitel_liste": [(uk, uk_anzahl[uk]) for uk in uk_anzahl],
    })


@router.post("/klassen/{kl_id}/schueler-kapitelempfehlung/pdf")
async def schueler_kapitel_empfehlung_pdf(kl_id: int, request: Request, db: Session = Depends(get_db)):
    from app.services.kapitel_empfehlung import empfehlungen_pro_schueler
    from app.services.pdf_export import _jinja_env
    from fastapi.responses import Response
    import weasyprint
    form = await request.form()
    kapitel = form.get("kapitel", "")
    uk_anzahl = _parse_uk_anzahl(form)
    kl = db.get(Klasse, kl_id)
    ergebnisse = empfehlungen_pro_schueler(kl_id, kapitel, uk_anzahl, db)
    html = _jinja_env().get_template("pdf_schueler_kapitel_empfehlung.html").render(
        klasse=kl, kapitel=kapitel, ergebnisse=ergebnisse,
    )
    pdf_bytes = weasyprint.HTML(string=html, base_url=".").write_pdf()
    dateiname = f"Individuelle_Empfehlung_{kl.name}_{kapitel[:25]}.pdf".replace(" ", "_")
    return Response(pdf_bytes, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{dateiname}"'})


@router.get("/klassen/{kl_id}/kapitelempfehlung")
def kapitel_empfehlung_form(kl_id: int, request: Request, db: Session = Depends(get_db)):
    kl = db.get(Klasse, kl_id)
    return templates.TemplateResponse(request, "kapitel_empfehlung.html", {
        "klasse": kl, "kapitel_liste": _kapitel_liste(db),
    })


@router.get("/klassen/{kl_id}/kapitelempfehlung/uk-liste")
def kapitel_empfehlung_uk_liste(kl_id: int, kapitel: str = "", db: Session = Depends(get_db)):
    from app.models.buchaufgabe import Buchaufgabe
    from fastapi.responses import HTMLResponse
    import sqlalchemy as sa_mod
    from jinja2 import Environment, FileSystemLoader
    if not kapitel:
        return HTMLResponse("")
    rows = (
        db.query(Buchaufgabe.unterkapitel, sa_mod.func.count(Buchaufgabe.id))
        .filter(Buchaufgabe.kapitel == kapitel, Buchaufgabe.unterkapitel != "")
        .group_by(Buchaufgabe.unterkapitel)
        .order_by(Buchaufgabe.unterkapitel)
        .all()
    )
    env = Environment(loader=FileSystemLoader("templates"), autoescape=True)
    html = env.get_template("htmx_kapitel_uk_liste.html").render(
        unterkapitel_liste=[(uk, cnt) for uk, cnt in rows]
    )
    return HTMLResponse(html)


@router.post("/klassen/{kl_id}/kapitelempfehlung")
async def kapitel_empfehlung_post(kl_id: int, request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    kapitel = form.get("kapitel", "")
    uk_anzahl = _parse_uk_anzahl(form)
    kl = db.get(Klasse, kl_id)
    ergebnis, komps, afb_profil, ziel, alle_k, schwach_ids, komp_map = \
        _kapitel_empfehlung_kontext(kl_id, kapitel, uk_anzahl, db)
    return templates.TemplateResponse(request, "kapitel_empfehlung.html", {
        "klasse": kl, "kapitel_liste": _kapitel_liste(db),
        "gewaehltes_kapitel": kapitel,
        "ergebnis": ergebnis, "komps": komps, "afb_profil": afb_profil,
        "ziel": ziel, "alle_kompetenzen": alle_k,
        "schwach_ids": schwach_ids, "komp_map": komp_map,
        "unterkapitel_liste": [(uk, len(v)) for uk, v in ergebnis.items()],
    })


@router.post("/klassen/{kl_id}/kapitelempfehlung/pdf")
async def kapitel_empfehlung_pdf_route(kl_id: int, request: Request, db: Session = Depends(get_db)):
    from app.services.pdf_export import kapitel_empfehlung_pdf
    from fastapi.responses import Response
    form = await request.form()
    kapitel = form.get("kapitel", "")
    uk_anzahl = _parse_uk_anzahl(form)
    kl = db.get(Klasse, kl_id)
    ergebnis, komps, afb_profil, ziel, alle_k, schwach_ids, komp_map = \
        _kapitel_empfehlung_kontext(kl_id, kapitel, uk_anzahl, db)
    pdf_bytes = kapitel_empfehlung_pdf({
        "klasse": kl, "kapitel": kapitel,
        "ergebnis": ergebnis, "komps": komps, "afb_profil": afb_profil,
        "ziel": ziel, "schwach_ids": schwach_ids, "komp_map": komp_map,
    })
    dateiname = f"Kapitel_Empfehlung_{kl.name}_{kapitel[:30]}.pdf".replace(" ", "_")
    return Response(pdf_bytes, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{dateiname}"'})


# ── Grundwissen ───────────────────────────────────────────────

def _gw_kapitel_liste(db):
    from app.models.grundwissen import Grundwissen as GW
    from app.models.buchaufgabe import Buchaufgabe
    buch_kap = sorted(set(r[0] for r in db.query(Buchaufgabe.kapitel).distinct().all()))
    gw_kap = sorted(set(r[0] for r in db.query(GW.kapitel).distinct().all()))
    return sorted(set(buch_kap + gw_kap))



@router.get("/grundwissen")
def grundwissen_liste(request: Request, js: str = "", kap: str = "", db: Session = Depends(get_db)):
    from app.models.grundwissen import Grundwissen as GW
    query = db.query(GW)
    if js and js.isdigit():
        query = query.filter(GW.jahrgangsstufe == int(js))
    if kap:
        query = query.filter(GW.kapitel == kap)
    eintraege = query.order_by(GW.jahrgangsstufe, GW.kapitel, GW.unterkapitel).all()
    return templates.TemplateResponse(request, "grundwissen_liste.html", {
        "eintraege": eintraege,
        "kapitel_liste": _gw_kapitel_liste(db),
        "js_filter": js,
        "kap_filter": kap,
    })


@router.get("/grundwissen/suche")
def grundwissen_suche(request: Request, q: str = "", js: str = "", kap: str = "", db: Session = Depends(get_db)):
    from app.models.grundwissen import Grundwissen as GW
    import sqlalchemy as sa
    query = db.query(GW)
    if q:
        like = f"%{q}%"
        query = query.filter(
            sa.or_(GW.aufgabe.ilike(like), GW.kapitel.ilike(like), GW.unterkapitel.ilike(like))
        )
    if js and js.isdigit():
        query = query.filter(GW.jahrgangsstufe == int(js))
    if kap:
        query = query.filter(GW.kapitel == kap)
    eintraege = query.order_by(GW.jahrgangsstufe, GW.kapitel).all()
    return templates.TemplateResponse(request, "htmx_grundwissen.html", {"eintraege": eintraege})


@router.get("/grundwissen/neu")
def grundwissen_neu_form(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(request, "grundwissen_neu.html", {
        "kapitel_liste": _kapitel_liste(db),
    })


@router.post("/grundwissen")
def grundwissen_erstellen(
    jahrgangsstufe: int = Form(...),
    kapitel: str = Form(""), kapitel_frei: str = Form(""),
    unterkapitel_sel: str = Form(""), unterkapitel_frei: str = Form(""),
    aufgabe: str = Form(...), loesung: str = Form(""), theorielink: str = Form(""),
    db: Session = Depends(get_db),
):
    from app.models.grundwissen import Grundwissen as GW
    kap = kapitel_frei.strip() or kapitel.strip() or "–"
    uk = unterkapitel_frei.strip() or unterkapitel_sel.strip() or None
    g = GW(jahrgangsstufe=jahrgangsstufe, kapitel=kap, unterkapitel=uk,
            aufgabe=aufgabe, loesung=loesung or None, theorielink=theorielink or None)
    db.add(g)
    db.commit()
    db.refresh(g)
    return REDIRECT(f"/ui/grundwissen/{g.id}?msg=Angelegt")


@router.get("/grundwissen/{gid}")
def grundwissen_detail(gid: int, request: Request, db: Session = Depends(get_db)):
    from app.models.grundwissen import Grundwissen as GW, AufgabeGrundwissen
    g = db.get(GW, gid)
    verwendungen = db.query(AufgabeGrundwissen).filter(AufgabeGrundwissen.grundwissen_id == gid).all()
    return templates.TemplateResponse(request, "grundwissen_detail.html", {
        "eintrag": g, "verwendungen": verwendungen,
        "msg": request.query_params.get("msg"),
    })


@router.post("/grundwissen/{gid}/bearbeiten")
def grundwissen_bearbeiten(
    gid: int,
    jahrgangsstufe: int = Form(...), kapitel: str = Form(...), unterkapitel: str = Form(""),
    aufgabe: str = Form(...), loesung: str = Form(""), theorielink: str = Form(""),
    db: Session = Depends(get_db),
):
    from app.models.grundwissen import Grundwissen as GW
    g = db.get(GW, gid)
    g.jahrgangsstufe = jahrgangsstufe
    g.kapitel = kapitel
    g.unterkapitel = unterkapitel or None
    g.aufgabe = aufgabe
    g.loesung = loesung or None
    g.theorielink = theorielink or None
    db.commit()
    return REDIRECT(f"/ui/grundwissen/{gid}?msg=Gespeichert")


@router.post("/grundwissen/{gid}/loeschen")
def grundwissen_loeschen(gid: int, db: Session = Depends(get_db)):
    from app.models.grundwissen import Grundwissen as GW
    g = db.get(GW, gid)
    if g:
        db.delete(g)
        db.commit()
    return REDIRECT("/ui/grundwissen?msg=Gelöscht")


@router.get("/aufgaben/{aid}/grundwissen/suche")
def aufgabe_gw_suche(aid: int, request: Request, q: str = "", db: Session = Depends(get_db)):
    from app.models.grundwissen import Grundwissen as GW, AufgabeGrundwissen
    import sqlalchemy as sa
    bereits = {ag.grundwissen_id for ag in db.query(AufgabeGrundwissen).filter(AufgabeGrundwissen.aufgabe_id == aid).all()}
    query = db.query(GW)
    if q:
        like = f"%{q}%"
        query = query.filter(
            sa.or_(GW.aufgabe.ilike(like), GW.kapitel.ilike(like), GW.unterkapitel.ilike(like))
        )
    treffer = [g for g in query.order_by(GW.jahrgangsstufe, GW.kapitel).limit(20).all() if g.id not in bereits]
    return templates.TemplateResponse(request, "htmx_gw_suche.html", {"treffer": treffer, "q": q, "aufgabe_id": aid})


@router.post("/aufgaben/{aid}/grundwissen/{gid}/zuordnen")
def aufgabe_gw_zuordnen(aid: int, gid: int, request: Request, db: Session = Depends(get_db)):
    from app.models.grundwissen import AufgabeGrundwissen
    existing = db.query(AufgabeGrundwissen).filter(
        AufgabeGrundwissen.aufgabe_id == aid, AufgabeGrundwissen.grundwissen_id == gid
    ).first()
    if not existing:
        db.add(AufgabeGrundwissen(aufgabe_id=aid, grundwissen_id=gid))
        db.commit()
    eintraege = db.query(AufgabeGrundwissen).filter(AufgabeGrundwissen.aufgabe_id == aid).all()
    return templates.TemplateResponse(request, "htmx_gw_zugeordnet.html", {
        "grundwissen_aktuell": eintraege, "aufgabe_id": aid,
    })


@router.post("/aufgaben/{aid}/grundwissen/{gid}/entfernen")
def aufgabe_gw_entfernen(aid: int, gid: int, request: Request, db: Session = Depends(get_db)):
    from app.models.grundwissen import AufgabeGrundwissen
    obj = db.query(AufgabeGrundwissen).filter(
        AufgabeGrundwissen.aufgabe_id == aid, AufgabeGrundwissen.grundwissen_id == gid
    ).first()
    if obj:
        db.delete(obj)
        db.commit()
    eintraege = db.query(AufgabeGrundwissen).filter(AufgabeGrundwissen.aufgabe_id == aid).all()
    return templates.TemplateResponse(request, "htmx_gw_zugeordnet.html", {
        "grundwissen_aktuell": eintraege, "aufgabe_id": aid,
    })


# ── Buchaufgaben ──────────────────────────────────────────────

@router.get("/buchaufgaben")
def buchaufgaben_liste(
    request: Request,
    buch: str = "", kompetenz_id: str = "", afb: str = "", suche: str = "", minimalfahrplan: str = "",
    db: Session = Depends(get_db),
):
    from app.models.buchaufgabe import Buchaufgabe
    buecher = [r[0] for r in db.query(Buchaufgabe.buch).distinct().order_by(Buchaufgabe.buch).all()]
    gesamt = db.query(Buchaufgabe).count()
    return templates.TemplateResponse(request, "buchaufgaben.html", {
        "buecher": buecher, "kompetenzen": db.query(Kompetenz).order_by(Kompetenz.kuerzel).all(),
        "gesamt": gesamt,
        "filter_buch": buch, "filter_kompetenz_id": kompetenz_id,
        "filter_afb": afb, "filter_suche": suche, "filter_minimalfahrplan": minimalfahrplan,
        "buchaufgaben": _buchaufgaben_gefiltert(buch, kompetenz_id, afb, suche, minimalfahrplan, db),
        "msg": request.query_params.get("msg"),
    })


@router.get("/buchaufgaben/suche")
def buchaufgaben_suche(
    request: Request,
    buch: str = "", kompetenz_id: str = "", afb: str = "", suche: str = "", minimalfahrplan: str = "",
    db: Session = Depends(get_db),
):
    return templates.TemplateResponse(request, "htmx_buchaufgaben.html", {
        "buchaufgaben": _buchaufgaben_gefiltert(buch, kompetenz_id, afb, suche, minimalfahrplan, db),
    })


def _buchaufgaben_gefiltert(buch, kompetenz_id, afb, suche, minimalfahrplan, db):
    from app.models.buchaufgabe import Buchaufgabe, BuchaufgabeKompetenz
    import sqlalchemy as sa_mod
    q = db.query(Buchaufgabe)
    if buch:
        q = q.filter(Buchaufgabe.buch == buch)
    if afb:
        q = q.filter(Buchaufgabe.afb_niveau == afb)
    if minimalfahrplan:
        q = q.filter(Buchaufgabe.minimalfahrplan.is_(True))
    if suche:
        term = f"%{suche}%"
        q = q.filter(sa_mod.or_(Buchaufgabe.beschreibung.ilike(term), Buchaufgabe.buch.ilike(term), Buchaufgabe.kapitel.ilike(term)))
    if kompetenz_id:
        try:
            q = q.join(BuchaufgabeKompetenz).filter(BuchaufgabeKompetenz.kompetenz_id == int(kompetenz_id))
        except ValueError:
            pass
    return q.order_by(Buchaufgabe.buch, Buchaufgabe.kapitel, Buchaufgabe.aufgabennummer).all()


@router.post("/buchaufgaben/import")
async def buchaufgaben_import_ui(request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)):
    from app.routers.buchaufgabe import import_csv
    ergebnis = await import_csv(file, db)
    msg = f"{ergebnis.importiert}+neu,+{ergebnis.aktualisiert}+aktualisiert"
    if ergebnis.fehler:
        msg += f",+{ergebnis.fehler}+Fehler"
    return REDIRECT(f"/ui/buchaufgaben?msg={msg}")


@router.post("/buchaufgaben/{ba_id}/loeschen")
def buchaufgabe_loeschen(ba_id: int, db: Session = Depends(get_db)):
    from app.models.buchaufgabe import Buchaufgabe
    obj = db.get(Buchaufgabe, ba_id)
    if obj:
        db.delete(obj)
        db.commit()
    return REDIRECT("/ui/buchaufgaben?msg=Aufgabe+gelöscht")
