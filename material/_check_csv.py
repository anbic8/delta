import csv
with open("material/buchaufgaben_6_import.csv", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))
multi = [r for r in rows if " " in r["Kompetenz"]]
print(f"Mehrere Kompetenzen: {len(multi)} Aufgaben")
for r in multi[:3]:
    print(f"  {r['Kapitel'][:35]} | {r['Unterkapitel'][:20]} | Aufg {r['Aufgabe']} | {r['Kompetenz']}")
print("Kapitel:")
for k in sorted(set(r["Kapitel"] for r in rows)):
    print(f"  {k}")
