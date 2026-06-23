# BandiHub — Portale unico bandi & finanziamenti (Beta)

Aggregatore verticale di **bandi e finanziamenti** — italiani **e UE** — per
**qualsiasi soggetto**: grandi imprese, PMI, micro, partite IVA, liberi
professionisti, freelance, startup e terzo settore. L'utente definisce il proprio
profilo e riceve i bandi **compatibili**, ordinati per pertinenza, con le
**scadenze imminenti** in evidenza e avvisi prima che scadano.

## Idea in una riga

> "Dicci chi sei e cosa vuoi finanziare: ti mostriamo solo i bandi che fanno per
> te — da Comune, Regione, Stato e Unione Europea — e ti avvisiamo prima della scadenza."

## Stato

- **Fase 1 — Motore di matching** ✅ — `src/matching.py`
  - profilo (soggetto, regione, settore, dimensione, obiettivi) → bandi compatibili
  - copre tutti i tipi di soggetto e tutte le fonti (UE/Stato/Regione/CCIAA/Comune)
- **Fase 2 — Alert** ✅ — `src/alert.py` (scadenze imminenti + nuovi bandi + testo avviso)
- **Fase 3 — Interfaccia** ✅ — `app.py` (Streamlit), collaudata end-to-end
- 9/9 test verdi (`tests/test_matching.py`)
- **Fase 4 (A) — Dati reali nazionali** ✅ — `src/import_incentivi.py` (5.507 incentivi reali da incentivi.gov.it)
- **Fase B — Bandi UE** ✅ — `src/import_ue.py` (API Funding & Tenders / SEDIA)
- Prossimo: regioni aggiuntive, aggiornamento automatico programmato, scelta nicchia di lancio

## Aggiornare i dati reali

```bash
# Nazionale: scarica il file Open Data da incentivi.gov.it, poi:
python src/import_incentivi.py --inspect "percorso\file.json"   # (la prima volta) verifica i campi
python src/import_incentivi.py "percorso\file.json"             # genera data/bandi_reali.csv

# Europa (chiamate all'API UE, vanno eseguite sul proprio PC/server):
python src/import_ue.py --inspect      # (la prima volta) conferma i campi dell'API
python src/import_ue.py                # genera data/bandi_ue.csv
```

L'app unisce automaticamente `bandi_reali.csv` (nazionale) e `bandi_ue.csv` (UE).

## Come avviarlo

```bash
cd aggregatore-bandi
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Si apre nel browser su http://localhost:8501

### Provare i pezzi senza interfaccia

```bash
python src/matching.py        # demo: 3 profili diversi (partita IVA, impresa, terzo settore)
python src/alert.py           # demo: avviso scadenze + nuovi bandi
python tests/test_matching.py # 9 test
```

## Architettura

```
data/bandi.csv     archivio bandi (di esempio): soggetti, fonte, ambito, settore,
                   dimensione, obiettivi, scadenze
        │
        ▼  matching.py   profilo soggetto → bandi compatibili (punteggio + motivi)
        │
        ▼  alert.py      scadenze entro N giorni + nuovi bandi + testo avviso email
        │
        ▼  app.py        interfaccia Streamlit (profilo → risultati + scadenze)
```

Il motore è indipendente dalla sorgente dati: domani al posto del CSV si collega
l'Open Data di incentivi.gov.it (o un'API) senza toccare la logica.

## Posizionamento (sintesi)

Mercato reale e che paga (es. FASI.biz da ~10 €/mese), presidiato da player ampi.
Il catalogo è volutamente **largo** (tutti i soggetti, anche UE), ma in vendita ci
si presenta con un **messaggio mirato** (es. "anche i bandi UE in un posto solo",
o "il portale pensato per partite IVA e freelance") per non essere "l'ennesimo
aggregatore". La nicchia di lancio si sceglie in Fase 4.

## Note

- **Dati di esempio**: i bandi in `data/bandi.csv` sono realistici ma inventati.
  Le fonti reali (incentivi.gov.it Open Data, portali regionali, UE) arrivano in Fase 4.
- **Solo fonti pubbliche** e nessuna risorsa/informazione d'ufficio.
- Progetto pensato per **veste societaria** (intestazione e gestione a un
  familiare/socio). Da validare con un commercialista.
