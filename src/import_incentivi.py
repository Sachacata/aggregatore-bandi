"""
Importer Fase A: file Open Data di incentivi.gov.it  ->  schema interno (bandi_reali.csv)

Mappatura tarata sui campi REALI dell'export JSON di incentivi.gov.it
(ID_Incentivo, Titolo, Forma_agevolazione, Dimensioni, Tipologia_Soggetto,
Obiettivo_Finalita, Settore_Attivita, Codici_ATECO, Regioni, date, Stanziamento…).

Uso:
  python3 src/import_incentivi.py --inspect <file.json|file.csv>   # vedi i campi
  python3 src/import_incentivi.py <file.json>                      # genera data/bandi_reali.csv

Nessuna dipendenza esterna: solo libreria standard.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import os
import re
import sys

OGGI = dt.date.today()

COLONNE = ["id", "titolo", "ente", "fonte", "tipo_agevolazione", "beneficiari",
           "settore", "ambito", "dimensione", "obiettivo", "dotazione",
           "data_apertura", "data_scadenza", "stato", "url"]

FORMA = {
    "Contributo/Fondo perduto": "fondo_perduto",
    "Prestito/Anticipo rimborsabile": "finanziamento_agevolato",
    "Capitale di rischio": "capitale_rischio",
    "Agevolazione fiscale": "credito_imposta",
    "Interventi a garanzia": "garanzia",
    "Riduzione dei contributi di previdenza sociale": "riduzione_contributi",
}
DIM = {"Microimpresa": "micro", "Piccola Impresa": "piccola",
       "Media Impresa": "media", "Grande Impresa": "grande"}
SOGG = {
    "Impresa": "impresa", "Impresa - SU/PMI innovativa": "startup",
    "Consorzio": "impresa", "Rete d'impresa": "impresa",
    "Ente Pubblico": "ente_pubblico", "Impresa da costituire - Altro": "startup",
    "Professionista": "partita_iva", "Università/Ente di Ricerca": "ricerca",
    "Cittadino": "persona_fisica", "Impresa - prevalenza femminile": "impresa",
    "Impresa - prevalenza giovanile": "impresa",
    "Impresa da costituire - Giovanile": "startup",
    "Impresa da costituire - Femminile": "startup",
    "Istituto finanziario": "istituto_finanziario",
    "Cooperative/Associazioni Non Profit": "terzo_settore",
}
OBJ = {
    "Sostegno investimenti": "investimenti", "Sostegno liquidità": "liquidita",
    "Internazionalizzazione": "internazionalizzazione",
    "Innovazione e ricerca": "ricerca_sviluppo",
    "Start up/Sviluppo d'impresa": "startup", "Digitalizzazione": "digitalizzazione",
    "Transizione ecologica": "transizione_ecologica", "Crisi d'impresa": "crisi",
    "Inclusione sociale": "inclusione", "Imprenditoria giovanile": "giovani",
    "Imprenditoria femminile": "donne",
}
REG_FIX = {"Trentino-Alto Adige/Südtirol": "Trentino-Alto Adige",
           "Valle d'Aosta/Vallée d'Aoste": "Valle d'Aosta"}


def _list(v):
    return v if isinstance(v, list) else ([v] if v not in (None, "") else [])


def _uniq(seq):
    out = []
    for x in seq:
        if x and x not in out:
            out.append(x)
    return out


def _num(s) -> str:
    m = re.search(r"\d+", str(s or ""))
    return m.group() if m else "0"


def _date(s):
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(str(s).replace("Z", "+00:00")).date()
    except ValueError:
        return None


def leggi(path: str) -> list[dict]:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".json":
        data = json.load(open(path, encoding="utf-8"))
        if isinstance(data, dict):
            # formato Solr (endpoint incentivi.gov.it): i dati sono in response.docs
            resp = data.get("response")
            if isinstance(resp, dict) and isinstance(resp.get("docs"), list):
                return resp["docs"]
            for k in ("data", "result", "records", "incentivi", "items"):
                if isinstance(data.get(k), list):
                    return data[k]
            return [data]
        return data
    with open(path, encoding="utf-8-sig", newline="") as f:
        camp = f.read(4096)
        f.seek(0)
        sep = ";" if camp.count(";") > camp.count(",") else ","
        return list(csv.DictReader(f, delimiter=sep))


def inspect(path: str) -> None:
    rec = leggi(path)
    print(f"File: {path}\nRecord: {len(rec)}")
    if not rec:
        return
    print("\nCampi del primo record:")
    for k, v in rec[0].items():
        print(f"  {str(k):26} = {str(v)[:80]}")


def normalizza(r: dict) -> dict:
    forme = _uniq(FORMA.get(x, "") for x in _list(r.get("Forma_agevolazione")))
    dims = _uniq(DIM.get(x, "") for x in _list(r.get("Dimensioni")))
    sogg = _uniq(SOGG.get(x, "") for x in _list(r.get("Tipologia_Soggetto")))
    obj = _uniq(OBJ.get(x, "") for x in _list(r.get("Obiettivo_Finalita")))

    ateco = str(r.get("Codici_ATECO") or "")
    if "Tutti i settori" in ateco or not r.get("Settore_Attivita"):
        settore = "tutti"
    else:
        settore = ";".join(s.lower() for s in _list(r.get("Settore_Attivita")))

    regs = _uniq(REG_FIX.get(x, x) for x in _list(r.get("Regioni")) if x != "Estero")
    if len(regs) >= 18 or not regs:
        ambito = "nazionale"
    else:
        ambito = ";".join(regs)

    ap = _date(r.get("Data_apertura"))
    ch = _date(r.get("Data_chiusura"))
    stato = "scaduto" if (ch and ch < OGGI) else "aperto"

    return {
        "id": "INC" + str(r.get("ID_Incentivo", "")),
        "titolo": (r.get("Titolo") or "").strip().replace("\n", " "),
        "ente": (r.get("Soggetto_Concedente") or "").strip(),
        "fonte": "Stato",
        "tipo_agevolazione": forme[0] if forme else "fondo_perduto",
        "beneficiari": ";".join(sogg) if sogg else "impresa",
        "settore": settore,
        "ambito": ambito,
        "dimensione": ";".join(dims) if dims else "tutte",
        "obiettivo": ";".join(obj),
        "dotazione": _num(r.get("Stanziamento_incentivo")),
        "data_apertura": ap.isoformat() if ap else "",
        "data_scadenza": ch.isoformat() if ch else "",
        "stato": stato,
        "url": (r.get("Link_istituzionale") or "").strip(),
    }


def importa(path: str, out_csv: str) -> tuple[int, int]:
    rec = leggi(path)
    righe = [normalizza(r) for r in rec]
    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLONNE)
        w.writeheader()
        w.writerows(righe)
    aperti = sum(1 for x in righe if x["stato"] == "aperto")
    return len(righe), aperti


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(0)
    if args[0] == "--inspect":
        inspect(args[1])
    else:
        here = os.path.dirname(os.path.abspath(__file__))
        out = os.path.join(here, "..", "data", "bandi_reali.csv")
        tot, ap = importa(args[0], out)
        print(f"Importati {tot} incentivi ({ap} aperti) -> {out}")
