"""
Orchestratore di aggiornamento dell'aggregatore bandi.

Esegue in sequenza, senza intervento manuale:
  1. NAZIONALE  – scarica l'Open Data di incentivi.gov.it (se URL configurato)
                   e lo importa  -> data/bandi_reali.csv
  2. EUROPA     – interroga l'API UE (SEDIA) e importa  -> data/bandi_ue.csv
  3. TRADUZIONE – traduce in italiano i titoli UE (se argostranslate è installato)
  4. NOVITÀ     – confronta col giro precedente e segnala i NUOVI bandi
                   -> data/nuovi_bandi.json  (base per gli alert)

Pensato per essere PIANIFICATO (Windows Task Scheduler / cron). Ogni fase è
protetta: se una fallisce, le altre proseguono.

Uso:
  python3 src/aggiorna.py                 # ciclo completo
  python3 src/aggiorna.py --no-nazionale  # salta il nazionale (usa il file esistente)
  python3 src/aggiorna.py --no-ue         # salta l'UE

Configurazione: imposta NAZIONALE_URL qui sotto con l'URL del file Open Data.
Solo libreria standard (+ argostranslate opzionale per la traduzione).
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
sys.path.insert(0, HERE)

import matching as M          # noqa: E402
import import_incentivi as NI  # noqa: E402
import import_ue as UE        # noqa: E402

# Endpoint Solr ufficiale di incentivi.gov.it (restituisce JSON: response.docs).
# rows=8000 copre l'intero catalogo; i campi sono gli stessi dell'export manuale.
NAZIONALE_URL = (
    "https://www.incentivi.gov.it/solr/coredrupal/select?q.op=OR&wt=json&rows=8000"
    "&fl=ID_Incentivo:zs_nid,Titolo:zs_title,Descrizione:zs_body,"
    "Obiettivo_Finalita:zm_field_scopes_value,Data_apertura:zs_field_open_date,"
    "Data_chiusura:zs_field_close_date,Dimensioni:zm_field_dimensions_value,"
    "Tipologia_Soggetto:zm_field_subject_type_value,"
    "Forma_agevolazione:zm_field_support_form_value,"
    "Costi_Ammessi:zm_field_granted_costs_value,"
    "Settore_Attivita:zm_field_activity_sector_value,Codici_ATECO:zs_field_ateco,"
    "Regioni:zm_field_regions_value,Soggetto_Concedente:zs_field_subject_grant,"
    "Stanziamento_incentivo:zs_field_budget_allocation,"
    "Link_istituzionale:zs_field_link,Data_ultimo_aggiornamento:ds_last_update"
    "&q=index_id:incentivi"
)

FILE_NAZIONALE = os.path.join(DATA, "incentivi_opendata.json")
BANDI_REALI = os.path.join(DATA, "bandi_reali.csv")
BANDI_UE = os.path.join(DATA, "bandi_ue.csv")
VISTI = os.path.join(DATA, "visti_bandi.json")
NUOVI = os.path.join(DATA, "nuovi_bandi.json")


def _log(msg):
    print(f"[{dt.datetime.now():%H:%M:%S}] {msg}", flush=True)


def fase_nazionale() -> None:
    _log("NAZIONALE: avvio")
    sorgente = None
    if NAZIONALE_URL:
        try:
            _log("  scarico l'Open Data da incentivi.gov.it (Solr)…")
            req = urllib.request.Request(
                NAZIONALE_URL,
                headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=180) as r:
                contenuto = r.read()
            with open(FILE_NAZIONALE, "wb") as f:
                f.write(contenuto)
            sorgente = FILE_NAZIONALE
        except Exception as e:  # noqa: BLE001
            _log(f"  ! download fallito: {e}")
    elif os.path.exists(FILE_NAZIONALE):
        sorgente = FILE_NAZIONALE
    if not sorgente:
        _log("  URL non configurato e nessun file locale: salto (uso bandi_reali.csv esistente)")
        return
    tot, ap = NI.importa(sorgente, BANDI_REALI)
    _log(f"  importati {tot} incentivi ({ap} aperti) -> bandi_reali.csv")


def fase_ue() -> None:
    _log("EUROPA: interrogo l'API SEDIA (scarico ~10.000 record, può richiedere 1-3 min)…")
    risultati = UE.query_sedia(verbose=True)
    righe = UE.filtra_e_normalizza(risultati)
    n = UE.scrivi(righe, BANDI_UE)
    _log(f"  importati {n} bandi UE (curati) -> bandi_ue.csv")


def fase_traduzione() -> None:
    _log("TRADUZIONE: titoli UE EN->IT")
    try:
        import traduci  # noqa: E402
        n = traduci.aggiorna_csv(BANDI_UE)
        _log(f"  tradotti {n} titoli" if n else "  nessuna traduzione (argostranslate assente o già tradotto)")
    except Exception as e:  # noqa: BLE001
        _log(f"  traduzione saltata: {e}")


def fase_novita() -> None:
    _log("NOVITÀ: confronto col giro precedente")
    attuali = {}
    for f in (BANDI_REALI, BANDI_UE):
        if os.path.exists(f):
            for b in M.carica_bandi(f):
                attuali[b.id] = b.titolo
    visti = set()
    if os.path.exists(VISTI):
        try:
            visti = set(json.load(open(VISTI, encoding="utf-8")))
        except Exception:  # noqa: BLE001
            visti = set()
    nuovi_ids = [i for i in attuali if i not in visti]
    nuovi = [{"id": i, "titolo": attuali[i]} for i in nuovi_ids]
    json.dump(nuovi, open(NUOVI, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    json.dump(sorted(attuali), open(VISTI, "w", encoding="utf-8"), ensure_ascii=False)
    _log(f"  {len(nuovi)} nuovi bandi rispetto all'ultimo aggiornamento -> nuovi_bandi.json")


def main():
    args = sys.argv[1:]
    inizio = dt.datetime.now()
    _log(f"=== Aggiornamento aggregatore bandi ===")
    if "--no-nazionale" not in args:
        try:
            fase_nazionale()
        except Exception as e:  # noqa: BLE001
            _log(f"NAZIONALE fallita: {e}")
    if "--no-ue" not in args:
        try:
            fase_ue()
        except Exception as e:  # noqa: BLE001
            _log(f"EUROPA fallita: {e}")
        fase_traduzione()
    try:
        fase_novita()
    except Exception as e:  # noqa: BLE001
        _log(f"NOVITÀ fallita: {e}")
    _log(f"=== Completato in {(dt.datetime.now()-inizio).seconds}s ===")


if __name__ == "__main__":
    main()
