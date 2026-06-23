"""
Motore di matching per l'aggregatore unico di bandi e finanziamenti.

Copre QUALSIASI soggetto (grande impresa, PMI, micro, partita IVA, libero
professionista, freelance, startup, terzo settore) e QUALSIASI fonte
(UE, Stato, Regione, Camera di Commercio, Comune).

Dato il PROFILO del soggetto, trova i bandi APERTI compatibili, li ordina per
rilevanza e urgenza, e spiega PERCHE' ciascun bando combacia.

Compatibilita':
  - beneficiari: il soggetto deve rientrare tra i destinatari (o 'tutti');
  - territorio: il bando vale se è UE/nazionale o se uno degli ambiti = regione
    del soggetto (un bando può valere per più regioni, es. "Veneto;Lombardia");
  - settore: vale se 'tutti' o se include il settore del soggetto;
  - dimensione: applicata solo alle imprese (micro/piccola/media/grande);
  - obiettivo (facoltativo): premia i bandi che coprono gli obiettivi indicati;
  - stato/scadenza: solo bandi aperti e non scaduti.

Nessuna dipendenza esterna: solo libreria standard.
"""

from __future__ import annotations

import csv
import datetime as dt
import os
from dataclasses import dataclass, field

OGGI_DEFAULT = dt.date.today()

AUTONOMI = {"partita_iva", "libero_professionista", "freelance", "autonomo"}

SOGGETTI = {
    "impresa": "Impresa",
    "partita_iva": "Partita IVA",
    "libero_professionista": "Libero professionista",
    "freelance": "Freelance",
    "startup": "Startup",
    "terzo_settore": "Terzo settore / No-profit",
}


def _split(s: str) -> list[str]:
    return [x.strip() for x in (s or "").split(";") if x.strip()]


def _num(s: str) -> float:
    """Estrae il primo numero da un campo (gli importi reali a volte hanno testo)."""
    import re
    m = re.search(r"\d+", str(s or ""))
    return float(m.group()) if m else 0.0


@dataclass
class Bando:
    id: str
    titolo: str
    ente: str
    fonte: str
    tipo_agevolazione: str
    beneficiari: list[str]
    settori: list[str]
    ambito: str               # testo grezzo (per visualizzazione)
    dimensioni: list[str]
    obiettivi: list[str]
    dotazione: float
    data_apertura: dt.date | None
    data_scadenza: dt.date | None
    stato: str
    url: str
    ambiti: list[str] = field(default_factory=list)   # ambito può essere multi-regione
    titolo_it: str = ""                                # traduzione IT (per i bandi UE)

    def aperto(self, oggi: dt.date) -> bool:
        # "Disponibile" = non scaduto. Mostriamo anche i bandi IN ARRIVO
        # (apertura futura): sono opportunità per cui prepararsi per tempo.
        if self.stato.lower() == "scaduto":
            return False
        if self.data_scadenza and self.data_scadenza < oggi:
            return False
        return True

    def in_arrivo(self, oggi: dt.date) -> bool:
        """True se il bando non è ancora aperto (apertura futura)."""
        return bool(self.data_apertura and self.data_apertura > oggi)

    def giorni_alla_scadenza(self, oggi: dt.date) -> int | None:
        if not self.data_scadenza:
            return None
        return (self.data_scadenza - oggi).days


@dataclass
class Profilo:
    tipo_soggetto: str
    regione: str
    settore: str
    dimensione: str = "tutte"
    obiettivi: list[str] = field(default_factory=list)


@dataclass
class Match:
    bando: Bando
    punteggio: float
    motivi: list[str]
    giorni_scadenza: int | None


def _parse_data(s: str) -> dt.date | None:
    s = (s or "").strip()
    return dt.datetime.strptime(s, "%Y-%m-%d").date() if s else None


def carica_bandi(path: str) -> list[Bando]:
    bandi = []
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            bandi.append(Bando(
                id=r["id"], titolo=r["titolo"], ente=r["ente"], fonte=r["fonte"].strip(),
                tipo_agevolazione=r["tipo_agevolazione"],
                beneficiari=_split(r["beneficiari"]), settori=_split(r["settore"]),
                ambito=r["ambito"].strip(), ambiti=_split(r["ambito"]),
                dimensioni=_split(r["dimensione"]),
                obiettivi=_split(r["obiettivo"]), dotazione=_num(r["dotazione"]),
                data_apertura=_parse_data(r["data_apertura"]),
                data_scadenza=_parse_data(r["data_scadenza"]),
                stato=r["stato"], url=r["url"],
                titolo_it=r.get("titolo_it", ""),
            ))
    return bandi


def _beneficiario_ok(b: Bando, p: Profilo) -> tuple[bool, str]:
    ben = [x.lower() for x in b.beneficiari]
    if "tutti" in ben:
        return True, "aperto a tutti i soggetti"
    s = p.tipo_soggetto.lower()
    if s in ben:
        return True, SOGGETTI.get(p.tipo_soggetto, p.tipo_soggetto).lower()
    if s in AUTONOMI and (AUTONOMI & set(ben)):
        return True, "lavoratori autonomi"
    return False, ""


def _territorio_ok(b: Bando, p: Profilo) -> tuple[bool, float, str]:
    ambiti = [a.lower() for a in (b.ambiti or [b.ambito])]
    if "ue" in ambiti:
        return True, 1.0, "fondo UE"
    if "nazionale" in ambiti:
        return True, 1.0, "misura nazionale"
    if p.regione.lower() in ambiti:
        return True, 2.0, f"specifico per {p.regione}"
    return False, 0.0, ""


def _compatibile(b: Bando, p: Profilo) -> tuple[bool, float, list[str]]:
    motivi: list[str] = []
    punteggio = 0.0

    ok, motivo_ben = _beneficiario_ok(b, p)
    if not ok:
        return False, 0.0, []
    punteggio += 1.0
    motivi.append(motivo_ben)

    ok, pt, motivo_terr = _territorio_ok(b, p)
    if not ok:
        return False, 0.0, []
    punteggio += pt
    motivi.append(motivo_terr)

    # Settore. Se il profilo non specifica un settore ('tutti'), non si filtra.
    sett = [s.lower() for s in b.settori]
    if p.settore.lower() in ("tutti", "", "qualsiasi"):
        pass
    elif "tutti" in sett:
        punteggio += 0.5
    elif p.settore.lower() in sett:
        punteggio += 2.0
        motivi.append(f"settore {p.settore}")
    else:
        return False, 0.0, []

    # Dimensione: vincolo solo per le imprese
    if p.tipo_soggetto.lower() == "impresa":
        dim = [d.lower() for d in b.dimensioni]
        if "tutte" in dim or not dim:
            punteggio += 0.5
        elif p.dimensione.lower() in dim:
            punteggio += 1.0
            motivi.append(f"dimensione {p.dimensione}")
        else:
            return False, 0.0, []

    # Obiettivi (facoltativo, premiante)
    if p.obiettivi:
        obj_b = [o.lower() for o in b.obiettivi]
        coperti = [o for o in p.obiettivi if o.lower() in obj_b]
        if coperti:
            punteggio += 1.5 * len(coperti)
            motivi.append("obiettivo: " + ", ".join(coperti))

    return True, punteggio, motivi


def trova(profilo: Profilo, bandi: list[Bando], oggi: dt.date = OGGI_DEFAULT,
          solo_aperti: bool = True) -> list[Match]:
    out: list[Match] = []
    for b in bandi:
        if solo_aperti and not b.aperto(oggi):
            continue
        ok, punteggio, motivi = _compatibile(b, profilo)
        if not ok:
            continue
        g = b.giorni_alla_scadenza(oggi)
        if g is not None and g <= 30:
            punteggio += 0.5
            motivi.append(f"scade tra {g} giorni")
        out.append(Match(bando=b, punteggio=round(punteggio, 2),
                         motivi=motivi, giorni_scadenza=g))
    out.sort(key=lambda m: (-m.punteggio,
                            m.giorni_scadenza if m.giorni_scadenza is not None else 9999))
    return out
