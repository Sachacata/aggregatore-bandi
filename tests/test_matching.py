"""
Test del motore di matching e degli alert.
Eseguire: python3 tests/test_matching.py
"""
import datetime as dt
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))

import matching as M   # noqa: E402
import alert as A      # noqa: E402

BANDI = os.path.join(HERE, "..", "data", "bandi.csv")
OGGI = dt.date(2026, 6, 22)


def _bandi():
    return M.carica_bandi(BANDI)


def test_caricamento():
    b = _bandi()
    assert len(b) == 22
    b001 = next(x for x in b if x.id == "B001")
    assert b001.ambito.lower() == "ue"
    assert "startup" in b001.beneficiari


def test_esclude_scaduti():
    b = _bandi()
    p = M.Profilo("impresa", regione="Emilia-Romagna", settore="tutti", dimensione="piccola")
    res = M.trova(p, b, oggi=OGGI)
    assert all(m.bando.id != "B021" for m in res)  # B021 è scaduto


def test_beneficiario_terzo_settore():
    b = _bandi()
    # Un terzo settore NON deve vedere bandi riservati alle sole imprese
    p = M.Profilo("terzo_settore", regione="nazionale", settore="tutti")
    res = M.trova(p, b, oggi=OGGI)
    for m in res:
        ben = [x.lower() for x in m.bando.beneficiari]
        assert "tutti" in ben or "terzo_settore" in ben
    # ma deve vedere il bando dedicato al terzo settore (B015)
    assert any(m.bando.id == "B015" for m in res)


def test_autonomi_sinonimi():
    b = _bandi()
    # Un freelance deve vedere il bando per 'partita_iva/libero_professionista/freelance' (B013)
    p = M.Profilo("freelance", regione="nazionale", settore="tutti")
    res = M.trova(p, b, oggi=OGGI)
    assert any(m.bando.id == "B013" for m in res)


def test_territorio_ue_e_nazionale_per_tutti():
    b = _bandi()
    # Una micro impresa in Veneto deve comunque vedere i fondi UE e nazionali
    p = M.Profilo("impresa", regione="Veneto", settore="ICT", dimensione="micro")
    res = M.trova(p, b, oggi=OGGI)
    ambiti = {m.bando.ambito.lower() for m in res}
    assert "ue" in ambiti and "nazionale" in ambiti
    # ma non i bandi di altre regioni (Lombardia)
    assert all(m.bando.ambito.lower() != "lombardia" for m in res)


def test_dimensione_solo_imprese():
    b = _bandi()
    # Una grande impresa non vede i bandi riservati a micro/piccola/media
    p = M.Profilo("impresa", regione="nazionale", settore="manifatturiero", dimensione="grande")
    res = M.trova(p, b, oggi=OGGI)
    for m in res:
        dim = [d.lower() for d in m.bando.dimensioni]
        assert "tutte" in dim or "grande" in dim
    # Un libero professionista invece ignora il vincolo dimensione
    p2 = M.Profilo("libero_professionista", regione="nazionale", settore="tutti")
    res2 = M.trova(p2, b, oggi=OGGI)
    assert len(res2) > 0


def test_regionale_batte_nazionale():
    b = _bandi()
    p = M.Profilo("impresa", regione="Veneto", settore="turismo", dimensione="micro",
                  obiettivi=["riqualificazione"])
    res = M.trova(p, b, oggi=OGGI)
    b016 = next(m for m in res if m.bando.id == "B016")  # Turismo Veneto
    naz = [m for m in res if m.bando.ambito.lower() in ("nazionale", "ue")]
    assert b016.punteggio >= max(m.punteggio for m in naz)


def test_alert_scadenze():
    b = _bandi()
    p = M.Profilo("impresa", regione="Veneto", settore="artigianato", dimensione="micro")
    imm = A.scadenze_imminenti(p, b, entro_giorni=30, oggi=OGGI)
    # Tutti entro 30 giorni e ordinati per urgenza
    assert all(0 <= m.giorni_scadenza <= 30 for m in imm)
    assert imm == sorted(imm, key=lambda m: m.giorni_scadenza)


def test_alert_nuovi():
    b = _bandi()
    p = M.Profilo("impresa", regione="Veneto", settore="artigianato", dimensione="micro")
    tutti_ids = {m.bando.id for m in M.trova(p, b, oggi=OGGI)}
    visti = set(list(tutti_ids)[:1])  # ne ho già visto uno
    nuovi = A.nuovi_bandi(p, b, visti, oggi=OGGI)
    assert all(m.bando.id not in visti for m in nuovi)
    assert len(nuovi) == len(tutti_ids) - 1


def _run():
    funcs = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    ok = 0
    for fn in funcs:
        try:
            fn(); print(f"  PASS  {fn.__name__}"); ok += 1
        except AssertionError as e:
            print(f"  FAIL  {fn.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            print(f"  ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{ok}/{len(funcs)} test superati.")
    return ok == len(funcs)


if __name__ == "__main__":
    print("Esecuzione test motore + alert:")
    sys.exit(0 if _run() else 1)
