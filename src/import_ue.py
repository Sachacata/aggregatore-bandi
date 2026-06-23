"""
Importer Fase B: API UE Funding & Tenders Portal (SEDIA)  ->  data/bandi_ue.csv

Interroga l'API pubblica anonima del portale europeo (chiave anonima "SEDIA"),
filtra ai bandi rilevanti e li normalizza nello schema interno (ambito = UE).

FILTRI applicati (per evitare il "rumore" dell'API, che restituisce anche aiuti
internazionali e record senza scadenza):
  - esclusi i bandi di aiuto esterno (datasource/URL 'prospect': EuropeAid, EIDHR…);
  - tenuti solo i bandi con DATA DI SCADENZA FUTURA (i veri bandi aperti);
  - il programma (Horizon, Digital Europe, LIFE…) viene mappato su un OBIETTIVO,
    così anche i bandi UE rispondono ai filtri dell'app.

Eseguire sul proprio PC/server (l'accesso in lettura è anonimo, niente registrazione).

Uso:
  python3 src/import_ue.py --inspect     # campi del 1° risultato reale
  python3 src/import_ue.py --stats        # distribuzione programmi/datasource/scadenze
  python3 src/import_ue.py --sample resp.json   # normalizza una risposta salvata
  python3 src/import_ue.py                # interroga l'API e genera data/bandi_ue.csv

Solo libreria standard.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import os
import sys
import urllib.request
from collections import Counter

OGGI = dt.date.today()
ENDPOINT = "https://api.tech.ec.europa.eu/search-api/prod/rest/search?apiKey=SEDIA&text=***"

COLONNE = ["id", "titolo", "ente", "fonte", "tipo_agevolazione", "beneficiari",
           "settore", "ambito", "dimensione", "obiettivo", "dotazione",
           "data_apertura", "data_scadenza", "stato", "url"]

# Programma/cluster europeo -> obiettivo interno (match per sottostringa).
# L'ordine conta: le voci PIÙ SPECIFICHE (es. cluster Horizon) vanno PRIMA.
PROG_OBJ = [
    ("horizon-cl5", "transizione_ecologica"),   # Clima, Energia, Mobilità
    ("horizon-cl6", "transizione_ecologica"),   # Alimentazione, Bioeconomia, Ambiente
    ("horizon-cl4", "ricerca_sviluppo"),         # Digitale, Industria, Spazio
    ("horizon-cl3", "sicurezza"),                # Sicurezza civile
    ("horizon-cl2", "inclusione"),               # Cultura, Società
    ("horizon-hlth", "ricerca_sviluppo"),        # Salute
    ("horizon-eic", "startup"),
    ("horizon", "ricerca_sviluppo"),
    ("digital", "digitalizzazione"),
    ("life", "transizione_ecologica"),
    ("erasmus", "formazione"),
    ("eic", "startup"),
    ("cosme", "startup"),
    ("smp", "startup"),                           # Single Market Programme
    ("single market", "startup"),
    ("innovfund", "transizione_ecologica"),
    ("innovation fund", "transizione_ecologica"),
    ("cef", "transizione_ecologica"),             # Connecting Europe Facility
    ("interreg", "internazionalizzazione"),
    ("creative", "internazionalizzazione"),
    ("crea", "internazionalizzazione"),           # Europa Creativa
    ("cerv", "inclusione"),
    ("amif", "inclusione"),
]

# Programmi di aiuto esterno / cooperazione internazionale da escludere
ESCLUDI_PROG = ("europeaid", "eidhr", "ndici", "ipa", "humanitarian",
                "pre-accession", "neighbourhood", "global europe",
                "development cooperation")

# Codici di stato SEDIA: 31094501=In arrivo (Forthcoming), 31094502=Aperto (Open),
# 31094503=Chiuso. Filtriamo lato server ai soli aperti/in arrivo.
STATUS_APERTI = ["31094501", "31094502"]
QUERY = {"bool": {"must": [{"terms": {"status": STATUS_APERTI}}]}}

# Prefissi di identificativo dei programmi UE rilevanti per imprese/organizzazioni.
# L'API restituisce migliaia di voci: ci concentriamo sui programmi utili e
# limitiamo a un numero ragionevole, ordinati per scadenza più vicina.
WHITELIST_PROG = ("horizon", "digital", "life", "erasmus", "eic", "cosme", "smp",
                  "single", "cef", "crea", "cerv", "interreg", "innovfund",
                  "emfaf", "i3", "edf", "eu4health")
MAX_BANDI_UE = 500


# --------------------------------------------------------------------------- #
# Chiamata API
# --------------------------------------------------------------------------- #
def _multipart(campi: dict[str, str]) -> tuple[bytes, str]:
    boundary = "----bandihub-boundary"
    parti = []
    for nome, valore in campi.items():
        parti += [f"--{boundary}",
                  f'Content-Disposition: form-data; name="{nome}"',
                  "Content-Type: application/json", "", valore]
    parti += [f"--{boundary}--", ""]
    return "\r\n".join(parti).encode("utf-8"), boundary


def _fetch(pagina: int, page_size: int, use_sort: bool) -> dict:
    campi = {
        "query": json.dumps(QUERY),
        "languages": json.dumps(["en"]),
        "page": json.dumps(pagina),
        "pageSize": json.dumps(page_size),
    }
    if use_sort:
        # ordina per scadenza DECRESCENTE: le scadenze più lontane nel futuro
        # vengono per prime, i record passati/senza data finiscono in fondo.
        # Così i bandi aperti rientrano nella finestra dei 10.000 risultati.
        campi["sort"] = json.dumps({"field": "deadlineDate", "order": "DESC"})
    body, boundary = _multipart(campi)
    req = urllib.request.Request(
        ENDPOINT, data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}",
                 "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def query_sedia(page_size: int = 100, max_pagine: int = 100,
                verbose: bool = True) -> list[dict]:
    # pre-volo: prova con l'ordinamento per scadenza; se l'API non lo accetta,
    # prosegue con l'ordine predefinito senza interrompersi
    use_sort = True
    try:
        _fetch(1, 1, True)
    except Exception:  # noqa: BLE001
        use_sort = False
        if verbose:
            print("  (ordinamento per scadenza non supportato: uso l'ordine predefinito)",
                  flush=True)

    risultati: list[dict] = []
    for pagina in range(1, max_pagine + 1):
        try:
            data = _fetch(pagina, page_size, use_sort)
        except Exception as e:  # noqa: BLE001
            print(f"  ! errore di rete alla pagina {pagina}: {type(e).__name__}: {e}",
                  flush=True)
            print("    (se sei dietro un proxy aziendale, l'API potrebbe essere bloccata)",
                  flush=True)
            break
        blocco = data.get("results", []) or []
        if verbose:
            print(f"  pagina {pagina}: ricevuti {len(blocco)} record "
                  f"(totale {len(risultati) + len(blocco)})", flush=True)
        if not blocco:
            break
        risultati.extend(blocco)
        if len(blocco) < page_size:
            break
    return risultati


# --------------------------------------------------------------------------- #
# Normalizzazione + filtri
# --------------------------------------------------------------------------- #
def _first(m: dict, k: str) -> str:
    v = m.get(k)
    if isinstance(v, list):
        return str(v[0]) if v else ""
    return str(v) if v not in (None, "") else ""


def _date(s: str):
    if not s:
        return None
    s = str(s).strip()
    if s.isdigit():                       # epoch (secondi o millisecondi)
        ts = int(s)
        if ts > 1_000_000_000_000:
            ts //= 1000
        try:
            return dt.datetime.utcfromtimestamp(ts).date()
        except (ValueError, OSError):
            return None
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return dt.datetime.strptime(s[:10], "%Y-%m-%d").date()
        except ValueError:
            return None


def _num(s) -> str:
    import re
    m = re.search(r"\d+", str(s or ""))
    return m.group() if m else "0"


def _obiettivo(programma: str) -> str:
    p = (programma or "").lower()
    for chiave, obj in PROG_OBJ:
        if chiave in p:
            return obj
    return ""


def _esterno(res: dict, programma: str) -> bool:
    """True se è un bando di aiuto esterno (da escludere)."""
    url = (res.get("url", "") or _first(res.get("metadata", {}), "url")).lower()
    ds = (_first(res.get("metadata", {}), "datasource")
          or _first(res.get("metadata", {}), "DATASOURCE")).lower()
    ident = _first(res.get("metadata", {}), "identifier").lower()
    if "prospect" in url or "prospect" in ds:
        return True
    if "europeaid" in ident:
        return True
    if any(x in programma.lower() for x in ESCLUDI_PROG):
        return True
    return False


def normalizza_ue(res: dict) -> dict:
    m = res.get("metadata", {}) or {}
    dl = _date(_first(m, "deadlineDate"))
    st = _date(_first(m, "startDate"))
    programma = _first(m, "frameworkProgramme")
    stato = "scaduto" if (dl and dl < OGGI) else "aperto"
    ident = _first(m, "identifier") or _first(m, "callIdentifier")
    ente = "Commissione UE" + (f" — {programma}" if programma else "")
    return {
        "id": "UE" + ident,
        "titolo": _first(m, "title").strip(),
        "ente": ente,
        "fonte": "UE",
        "tipo_agevolazione": "fondo_perduto",
        "beneficiari": "impresa;startup;terzo_settore;ricerca",
        "settore": "tutti",
        "ambito": "UE",
        "dimensione": "tutte",
        "obiettivo": _obiettivo(ident or programma),
        "dotazione": _num(_first(m, "budget")),
        "data_apertura": st.isoformat() if st else "",
        "data_scadenza": dl.isoformat() if dl else "",
        "stato": stato,
        "url": res.get("url", "") or _first(m, "url"),
    }


def filtra_e_normalizza(results: list[dict]) -> list[dict]:
    out = []
    visti = set()
    for res in results:
        programma = _first(res.get("metadata", {}), "frameworkProgramme")
        if _esterno(res, programma):
            continue                      # via gli aiuti esterni
        riga = normalizza_ue(res)
        if not riga["titolo"] or riga["id"] == "UE":
            continue
        if not riga["data_scadenza"] or riga["stato"] != "aperto":
            continue                      # solo bandi con scadenza futura
        ident = riga["id"][2:].lower()    # identificativo senza prefisso 'UE'
        if not any(ident.startswith(w) for w in WHITELIST_PROG):
            continue                      # solo programmi rilevanti
        if riga["id"] in visti:
            continue                      # niente doppioni
        visti.add(riga["id"])
        out.append(riga)
    # i più urgenti per primi, con un tetto ragionevole
    out.sort(key=lambda r: r["data_scadenza"])
    return out[:MAX_BANDI_UE]


def scrivi(righe: list[dict], out_csv: str) -> int:
    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLONNE)
        w.writeheader()
        w.writerows(righe)
    return len(righe)


# --------------------------------------------------------------------------- #
# Modalità diagnostiche
# --------------------------------------------------------------------------- #
def inspect() -> None:
    res = query_sedia(page_size=5, max_pagine=1)
    print(f"Risultati ricevuti: {len(res)}")
    if not res:
        return
    print("\nChiavi 'metadata' del primo risultato:")
    for k in (res[0].get("metadata", {}) or {}).keys():
        print(f"  - {k}")
    print("\nEsempio normalizzato:")
    print(json.dumps(normalizza_ue(res[0]), ensure_ascii=False, indent=2))


def stats() -> None:
    print("Interrogazione API UE (SEDIA) in corso… (può richiedere qualche secondo)",
          flush=True)
    res = query_sedia()
    print(f"\nTotale record ricevuti: {len(res)}", flush=True)
    if not res:
        print("Nessun record ricevuto. Possibili cause: rete/proxy che blocca l'API, "
              "oppure risposta vuota. Riprova o controlla la connessione.")
        return
    prog = Counter(); status_c = Counter(); type_c = Counter(); fut = 0; ext = 0
    for r in res:
        m = r.get("metadata", {})
        p = _first(m, "frameworkProgramme") or "(nessuno)"
        prog[p] += 1
        status_c[_first(m, "status") or "(vuoto)"] += 1
        type_c[_first(m, "type") or "(vuoto)"] += 1
        if _esterno(r, p):
            ext += 1
        dl = _date(_first(m, "deadlineDate"))
        if dl and dl >= OGGI:
            fut += 1
    tenuti = filtra_e_normalizza(res)
    print(f"Con scadenza futura: {fut} | aiuti esterni (esclusi): {ext} | "
          f"TENUTI dopo i filtri: {len(tenuti)}")
    print("\nDistribuzione 'status' (codici):")
    for s, n in status_c.most_common():
        print(f"  {n:5}  {s}")
    print("\nDistribuzione 'type' (codici):")
    for t, n in type_c.most_common():
        print(f"  {n:5}  {t}")
    print("\nTop 12 programmi (codici):")
    for p, n in prog.most_common(12):
        print(f"  {n:5}  {p}")


# --------------------------------------------------------------------------- #
def main():
    args = sys.argv[1:]
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(here, "..", "data", "bandi_ue.csv")

    if args and args[0] == "--inspect":
        inspect(); return
    if args and args[0] == "--stats":
        stats(); return
    if args and args[0] == "--sample":
        data = json.load(open(args[1], encoding="utf-8"))
        righe = filtra_e_normalizza(data.get("results", []))
        print(f"[sample] Bandi UE tenuti dopo i filtri: {scrivi(righe, out)} -> {out}")
        return

    print("Interrogazione API UE (SEDIA)…")
    righe = filtra_e_normalizza(query_sedia())
    n = scrivi(righe, out)
    print(f"Importati {n} bandi UE aperti e pertinenti -> {out}")


if __name__ == "__main__":
    main()
