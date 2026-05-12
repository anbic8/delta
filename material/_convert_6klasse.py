"""
Konvertiert 'Kompetenzen 6 Klasse.csv' ins Delta-Import-Format.
Aufruf: python material/_convert_6klasse.py
"""
import csv, pathlib

INPUT  = pathlib.Path("material/Kompetenzen 6 Klasse.csv")
OUTPUT = pathlib.Path("material/buchaufgaben_6_import.csv")

JAHRGANGSSTUFE = 6

# Spaltenindizes (0-basiert, Trennzeichen ;)
C_KAP  = 1   # Kapitel-Nummer
C_UK   = 2   # Unterkapitel-Nummer oder Label
C_AUF  = 3   # Aufgabennummer
C_DESC = 4   # Beschreibung (meist leer bei Aufgaben, Titel bei Headern)
C_MFP  = 5   # Minimalfahrplan (1=Ja)
C_WICH = 6   # Wichtigkeit (ignoriert – negative Werte aus Quelle)
C_TD   = 7   # Teste Dich (1=Ja)
C_AFB1 = 8   # AFB I
C_AFB2 = 9   # AFB II
C_AFB3 = 10  # AFB III
C_GW   = 11  # Grundwissen
C_K1   = 12  # K1–K6


def pad(row, n=20):
    return row + [""] * (n - len(row))


def alle_kompetenzen(row):
    return " ".join(k for i, k in enumerate(["K1","K2","K3","K4","K5","K6"], C_K1) if row[i].strip() == "1")


lines = INPUT.read_text(encoding="utf-8-sig").splitlines()
rows  = [pad(line.split(";")) for line in lines if line.strip()]
rows  = rows[1:]  # Header überspringen

cur_kap_nr   = ""
cur_kap_name = ""
cur_uk_nr    = ""
cur_uk_name  = ""

# Vorbekannte Kapitel-Titel aus den Header-Zeilen der Quelle
kap_names = {}   # nr -> name
uk_names  = {}   # (kap_nr, uk_nr) -> name

# Erster Pass: Titel einlesen
for row in rows:
    col1, col2, col3, col4 = row[C_KAP].strip(), row[C_UK].strip(), row[C_AUF].strip(), row[C_DESC].strip()
    if not col1 or not col4:
        continue
    if col3 == "" or col3 == "0":          # Header-Zeile
        if col2 in ("", "0"):
            if col1 not in kap_names:      # erster Treffer gewinnt (kein Überschreiben durch "Check In" etc.)
                kap_names[col1] = col4
        elif col2:                         # Unterkapitel-Header
            uk_names[(col1, col2)] = col4

output = []

for row in rows:
    col1 = row[C_KAP].strip()
    col2 = row[C_UK].strip()
    col3 = row[C_AUF].strip()
    col4 = row[C_DESC].strip()

    if not col1:
        continue

    # Kapitel gewechselt
    if col1 != cur_kap_nr:
        cur_kap_nr   = col1
        cur_kap_name = kap_names.get(col1, f"Kapitel {col1}")
        cur_uk_nr    = ""
        cur_uk_name  = ""

    # Header-Zeile → Kontext aktualisieren, keine Aufgabe ausgeben
    if col3 == "" or (col3 == "0" and col4):
        if col2 not in ("", "0") and col2:
            cur_uk_nr   = col2
            cur_uk_name = uk_names.get((col1, col2), col2)
        continue

    # Aufgaben-Zeile: Unterkapitel-Wechsel prüfen
    if col2 != cur_uk_nr:
        cur_uk_nr   = col2
        cur_uk_name = uk_names.get((col1, col2), col2)

    # AFB (erste Markierung gewinnt)
    if   row[C_AFB1].strip() == "1": afb = "AFB_I"
    elif row[C_AFB2].strip() == "1": afb = "AFB_II"
    elif row[C_AFB3].strip() == "1": afb = "AFB_III"
    else:                             afb = "AFB_II"

    # Beschreibung aus Teste-Dich- / Grundwissen-Spalte
    if   row[C_TD].strip() == "1": desc = "Teste dich"
    elif row[C_GW].strip() == "1": desc = "Grundwissen"
    elif cur_uk_nr.lower().startswith("teste"): desc = "Teste dich"
    else: desc = ""

    # Minimalfahrplan
    mfp = "Ja" if row[C_MFP].strip() == "1" else ""

    # Kapitel-String
    kap_str = f"{cur_kap_nr} - {cur_kap_name}" if cur_kap_name else f"Kapitel {cur_kap_nr}"

    # Unterkapitel-String
    try:
        uk_num = int(cur_uk_nr)
        if cur_uk_name and cur_uk_name != cur_uk_nr:
            uk_str = f"{cur_kap_nr}.{cur_uk_nr} - {cur_uk_name}"
        else:
            uk_str = f"{cur_kap_nr}.{cur_uk_nr}"
    except ValueError:
        uk_str = cur_uk_name if cur_uk_name else cur_uk_nr

    output.append({
        "Jahrgangsstufe": JAHRGANGSSTUFE,
        "Kapitel":        kap_str,
        "Unterkapitel":   uk_str,
        "Aufgabe":        col3,
        "Beschreibung":   desc,
        "AFB":            afb,
        "Minimalfahrplan":mfp,
        "Kompetenz":      alle_kompetenzen(row),
    })

FIELDS = ["Jahrgangsstufe","Kapitel","Unterkapitel","Aufgabe","Beschreibung","AFB","Minimalfahrplan","Kompetenz"]
with OUTPUT.open("w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=FIELDS)
    w.writeheader()
    w.writerows(output)

print(f"OK: {len(output)} Aufgaben -> {OUTPUT}")
