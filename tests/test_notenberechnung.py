from app.services.notenberechnung import ist_grenzfall, punkte_zu_note

# --- Abiturschlüssel ---

def test_note_1():
    assert punkte_zu_note(85, 100) == 1
    assert punkte_zu_note(100, 100) == 1

def test_note_2():
    assert punkte_zu_note(70, 100) == 2
    assert punkte_zu_note(84, 100) == 2

def test_note_3():
    assert punkte_zu_note(55, 100) == 3

def test_note_4():
    assert punkte_zu_note(40, 100) == 4

def test_note_5():
    assert punkte_zu_note(20, 100) == 5

def test_note_6():
    assert punkte_zu_note(19, 100) == 6
    assert punkte_zu_note(0, 100) == 6

def test_skaliert_mit_max_punkten():
    # 34 von 40 = 85% → Note 1
    assert punkte_zu_note(34, 40) == 1
    # 16 von 40 = 40% → Note 4
    assert punkte_zu_note(16, 40) == 4


# --- Grenzfall ---

def test_grenzfall_exakt_0_5_be():
    # Grenze Note 2→1: 85% von 40 = 34 Punkte → bei 33.5 BE Abstand = 0.5 → Grenzfall
    assert ist_grenzfall(33.5, 40) is True

def test_grenzfall_0_6_be_kein_grenzfall():
    assert ist_grenzfall(33.4, 40) is False

def test_grenzfall_genau_an_grenze():
    # Exakt 34/40 = Note 1 → kein Grenzfall möglich
    assert ist_grenzfall(34.0, 40) is False

def test_grenzfall_note_6_kein_grenzfall():
    # Note 6 hat keine bessere Note 5... doch! 20% Grenze
    # 20% von 40 = 8 Punkte. Bei 7.5 Punkte: 8 - 7.5 = 0.5 → Grenzfall
    assert ist_grenzfall(7.5, 40) is True
    assert ist_grenzfall(7.4, 40) is False
