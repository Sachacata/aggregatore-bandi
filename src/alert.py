"""
Logica di alert per l'aggregatore di bandi.

Due tipi di avviso, entrambi basati sul profilo del soggetto:
  1. SCADENZE IMMINENTI: bandi compatibili che scadono entro N giorni;
  2. NUOVI BANDI: bandi compatibili comparsi dall'ultimo controllo
     (confronto con l'elenco di id già visti, persistito su file JSON).

Questa logica è il cuore del servizio "ti avviso prima che scada".
Nessuna dipendenza esterna: solo libreria standard.
"""

from __future__ import annotations

import datetime as dt
import json
import os

import matching as M


def scadenze_imminenti(profilo: M.Profilo, bandi: list[M.Bando],
                       entro_giorni: int = 30,
                       oggi: dt.date = M.OGGI_DEFAULT) -> list[M.Match]:
    """Bandi compatibili che scadono entro 'entro_giorni', dal più urgente."""
    res = M.trova(profilo, bandi, oggi=oggi)
    imminenti = [m for m in res
                 if m.giorni_scadenza is not None and 0 <= m.giorni_scadenza <= entro_giorni]
    imminenti.sort(key=lambda m: m.giorni_scadenza)
    return imminenti


def nuovi_bandi(profilo: M.Profilo, bandi: list[M.Bando], visti_ids: set[str],
                oggi: dt.date = M.OGGI_DEFAULT) -> list[M.Match]:
    """Bandi compatibili non ancora visti (rispetto a visti_ids)."""
    res = M.trova(profilo, bandi, oggi=oggi)
    return [m for m in res if m.bando.id not in visti_ids]


# --- Persistenza degli id già visti (per non riavvisare due volte) ---------- #

def carica_visti(path: str) -> set[str]:
    if not os.path.exists(path):
        return set()
    with open(path, encoding="utf-8") as f:
        return set(json.load(f))


def salva_visti(path: str, ids: set[str]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(sorted(ids), f, ensure_ascii=False, indent=2)


def componi_avviso(profilo: M.Profilo, nuovi: list[M.Match],
                   imminenti: list[M.Match]) -> str:
    """Testo dell'avviso (es. corpo email) per un dato profilo."""
    et = M.SOGGETTI.get(profilo.tipo_soggetto, profilo.tipo_soggetto)
    righe = [f"Aggiornamento bandi per: {et} · {profilo.settore} · {profilo.regione}", ""]
    if nuovi:
        righe.append(f"NUOVI BANDI ({len(nuovi)}):")
        for m in nuovi:
            righe.append(f"  • {m.bando.titolo} ({m.bando.fonte}) — scad. {m.bando.data_scadenza}")
        righe.append("")
    if imminenti:
        righe.append(f"IN SCADENZA ({len(imminenti)}):")
        for m in imminenti:
            righe.append(f"  • {m.bando.titolo} — tra {m.giorni_scadenza} giorni")
        righe.append("")
    if not nuovi and not imminenti:
        righe.append("Nessuna novità o scadenza imminente per il tuo profilo.")
    return "\n".join(righe)


# --------------------------------------------------------------------------- #
# Demo
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    bandi = M.carica_bandi(os.path.join(here, "..", "data", "bandi.csv"))
    oggi = dt.date(2026, 6, 22)
    profilo = M.Profilo("impresa", regione="Veneto", settore="artigianato",
                        dimensione="micro")

    # Simuliamo: l'utente ha già visto due bandi
    visti = {"B011", "B018"}
    nuovi = nuovi_bandi(profilo, bandi, visti, oggi=oggi)
    imminenti = scadenze_imminenti(profilo, bandi, entro_giorni=30, oggi=oggi)

    print(componi_avviso(profilo, nuovi, imminenti))
