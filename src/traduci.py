"""
Traduzione EN->IT dei titoli dei bandi UE, con motore OFFLINE (argostranslate).
Gratuito, senza chiavi API, automatizzabile nella pipeline.

Aggiunge/riempie la colonna 'titolo_it' in un CSV di bandi (di norma
data/bandi_ue.csv). I bandi nazionali sono già in italiano: non serve tradurli.

PRIMA VOLTA (una tantum, richiede connessione per scaricare il modello):
    pip install argostranslate
    python3 src/traduci.py setup

POI (anche in automatico, dopo ogni import UE):
    python3 src/traduci.py data/bandi_ue.csv

Se argostranslate non è installato o il modello manca, lo script avvisa e
NON modifica il file (l'app continuerà a mostrare il titolo in inglese).

Solo libreria standard + argostranslate (opzionale).
"""

from __future__ import annotations

import csv
import sys

_translate = None
_pronto = False


def _get_translation():
    import argostranslate.translate as tr
    lingue = tr.get_installed_languages()
    da = next((l for l in lingue if l.code == "en"), None)
    a = next((l for l in lingue if l.code == "it"), None)
    return da.get_translation(a) if (da and a) else None


def _init(auto_install: bool = True) -> bool:
    """Carica (e se serve scarica) il modello EN->IT. True se pronto."""
    global _translate, _pronto
    if _pronto:
        return _translate is not None
    _pronto = True
    try:
        import argostranslate.package as pkg  # noqa: F401
    except ImportError:
        print("argostranslate non installato. Esegui:  pip install argostranslate")
        return False

    t = _get_translation()
    if t is None and auto_install:
        try:
            import argostranslate.package as pkg
            print("Scarico il modello di traduzione EN->IT (una tantum)…", flush=True)
            pkg.update_package_index()
            disponibili = pkg.get_available_packages()
            p = next((x for x in disponibili
                      if x.from_code == "en" and x.to_code == "it"), None)
            if p:
                pkg.install_from_path(p.download())
                t = _get_translation()
        except Exception as e:  # noqa: BLE001
            print(f"Impossibile installare il modello EN->IT: {e}")
    _translate = t
    if t is None:
        print("Modello EN->IT non disponibile: traduzione saltata.")
    return t is not None


def traduci_it(testo: str) -> str:
    """Traduce in italiano; in caso di problemi restituisce il testo originale."""
    if not testo or not _init():
        return testo
    try:
        return _translate.translate(testo)
    except Exception:  # noqa: BLE001
        return testo


def aggiorna_csv(path: str) -> int:
    """Riempie la colonna 'titolo_it' (solo dove mancante). Ritorna n. tradotti."""
    if not _init():
        return 0
    with open(path, encoding="utf-8", newline="") as f:
        righe = list(csv.DictReader(f))
    if not righe:
        return 0
    campi = list(righe[0].keys())
    if "titolo_it" not in campi:
        campi.append("titolo_it")
    n = 0
    for r in righe:
        if not r.get("titolo_it"):
            r["titolo_it"] = traduci_it(r.get("titolo", ""))
            n += 1
            if n % 25 == 0:
                print(f"  tradotti {n}…", flush=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campi)
        w.writeheader()
        w.writerows(righe)
    return n


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "setup":
        print("Modello EN->IT pronto." if _init() else "Setup non riuscito.")
    elif args:
        n = aggiorna_csv(args[0])
        print(f"Tradotti {n} titoli in italiano -> {args[0]}")
    else:
        print(__doc__)
