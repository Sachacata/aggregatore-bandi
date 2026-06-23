"""
Interfaccia beta dell'aggregatore unico di bandi e finanziamenti (Streamlit).

Avvio in locale:
    cd aggregatore-bandi
    pip install streamlit
    streamlit run app.py

Usa i dati reali (data/bandi_reali.csv) se presenti, altrimenti i dati di esempio
(data/bandi.csv). I menù (regioni, settori, obiettivi) si adattano ai dati caricati.
"""

from __future__ import annotations

import datetime as dt
import os
import sys

import streamlit as st

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
sys.path.insert(0, SRC)

import matching as M   # noqa: E402
import alert as A      # noqa: E402

REALI = os.path.join(DATA, "bandi_reali.csv")     # nazionale (incentivi.gov.it)
UE = os.path.join(DATA, "bandi_ue.csv")           # europeo (API SEDIA)
ESEMPIO = os.path.join(DATA, "bandi.csv")
FONTI = [f for f in (REALI, UE) if os.path.exists(f)]
DATI_REALI = bool(FONTI)
BANDI_CSV = FONTI[0] if FONTI else ESEMPIO        # chiave per la cache

ICONE_FONTE = {"UE": "🇪🇺", "Stato": "🇮🇹", "Regione": "📍", "CCIAA": "🏛️", "Comune": "🏛️"}

# Descrizione in italiano dei bandi UE, dedotta dal programma/cluster (più specifico prima)
DESCR_UE = [
    ("horizon-cl5", "Horizon Europe – Cluster 5: Clima, Energia e Mobilità."),
    ("horizon-cl6", "Horizon Europe – Cluster 6: Alimentazione, Bioeconomia e Ambiente."),
    ("horizon-cl4", "Horizon Europe – Cluster 4: Digitale, Industria e Spazio."),
    ("horizon-cl3", "Horizon Europe – Cluster 3: Sicurezza civile."),
    ("horizon-cl2", "Horizon Europe – Cluster 2: Cultura, creatività e società inclusiva."),
    ("horizon-hlth", "Horizon Europe – Salute."),
    ("horizon-eic", "Consiglio europeo per l'innovazione (EIC) – innovazione e deep tech."),
    ("horizon", "Horizon Europe – Ricerca e innovazione."),
    ("digital", "Digital Europe – Trasformazione e competenze digitali."),
    ("life", "Programma LIFE – Ambiente e azione per il clima."),
    ("erasmus", "Erasmus+ – Istruzione, formazione, gioventù e sport."),
    ("eic", "Consiglio europeo per l'innovazione (EIC) – startup e deep tech."),
    ("cosme", "Programma per la competitività delle PMI."),
    ("smp", "Programma per il Mercato Unico – competitività e PMI."),
    ("cef", "Connecting Europe Facility – infrastrutture (trasporti, energia, digitale)."),
    ("interreg", "Interreg – cooperazione territoriale europea."),
    ("creative", "Europa Creativa – settori culturali e creativi."),
    ("crea", "Europa Creativa – settori culturali e creativi."),
    ("cerv", "CERV – Cittadini, uguaglianza, diritti e valori."),
    ("amif", "AMIF – Asilo, migrazione e integrazione."),
]


def descrizione_ue(b) -> str:
    chiave_testo = (b.id + " " + b.ente).lower()
    for chiave, desc in DESCR_UE:
        if chiave in chiave_testo:
            return desc
    return "Bando dell'Unione Europea."


def euro(v: float) -> str:
    if v >= 1_000_000:
        return f"{v/1_000_000:.1f} mln €".replace(".", ",")
    if v > 0:
        return f"{v:,.0f} €".replace(",", ".")
    return "n.d."


@st.cache_data
def carica():
    if FONTI:
        out = []
        for f in FONTI:
            out += M.carica_bandi(f)
        return out
    return M.carica_bandi(ESEMPIO)


@st.cache_data
def opzioni(_bandi_key):
    """Costruisce le liste dei menù dai dati effettivamente caricati."""
    bandi = carica()
    regioni, settori, obiettivi = set(), set(), set()
    for b in bandi:
        for a in b.ambiti:
            if a.lower() not in ("ue", "nazionale"):
                regioni.add(a)
        for s in b.settori:
            if s.lower() != "tutti":
                settori.add(s)
        for o in b.obiettivi:
            obiettivi.add(o)
    return (sorted(regioni), ["tutti"] + sorted(settori), sorted(obiettivi))


st.set_page_config(page_title="Volano — Bandi e finanziamenti", page_icon="🚀",
                   layout="centered")
bandi = carica()
oggi = dt.date.today()
REGIONI, SETTORI, OBIETTIVI = opzioni(BANDI_CSV)

st.title("🚀 Volano")
st.subheader("Il volano dei tuoi progetti")
st.caption("Trova i bandi e i finanziamenti — Italia + Unione Europea — che danno "
           "slancio alla tua impresa. Dicci chi sei: ti mostriamo solo quelli che "
           "fanno per te e ti avvisiamo prima che scadano.")
if DATI_REALI:
    aperti = sum(1 for b in bandi if b.aperto(oggi))
    st.success(f"✅ Dati **reali** da incentivi.gov.it: {len(bandi)} incentivi in archivio, "
               f"{aperti} aperti oggi.")
else:
    st.info("⚠️ Dati **di esempio**. Esegui l'import di incentivi.gov.it per i dati reali.",
            icon="ℹ️")

# --------------------------------------------------------------------------- #
# Profilo
# --------------------------------------------------------------------------- #
st.subheader("Dove vuoi cercare?")
cc1, cc2 = st.columns(2)
with cc1:
    ck_naz = st.checkbox("🇮🇹 Bandi nazionali e regionali", value=True)
with cc2:
    ck_ue = st.checkbox("🇪🇺 Bandi europei (UE)", value=True)


def _in_canale(b):
    is_ue = b.fonte.strip().upper() == "UE"
    return (ck_ue and is_ue) or (ck_naz and not is_ue)


bandi_canale = [b for b in bandi if _in_canale(b)]
if not bandi_canale:
    st.warning("Seleziona almeno un canale (nazionale o UE) per vedere i bandi.")

st.subheader("1. Chi sei?")
col1, col2 = st.columns(2)
with col1:
    tipo = st.selectbox("Tipo di soggetto", options=list(M.SOGGETTI.keys()),
                        format_func=lambda k: M.SOGGETTI[k])
    regione = st.selectbox("Regione", options=REGIONI,
                           index=(REGIONI.index("Veneto") if "Veneto" in REGIONI else 0))
with col2:
    settore = st.selectbox("Settore", options=SETTORI, index=0,
                           help="Lascia 'tutti' per non filtrare per settore")
    dimensione = "tutte"
    if tipo == "impresa":
        dimensione = st.selectbox("Dimensione impresa",
                                  options=["micro", "piccola", "media", "grande"])

obiettivi = st.multiselect("Cosa vuoi finanziare? (facoltativo)", options=OBIETTIVI)

profilo = M.Profilo(tipo_soggetto=tipo, regione=regione, settore=settore,
                    dimensione=dimensione, obiettivi=obiettivi)

# --------------------------------------------------------------------------- #
# Risultati
# --------------------------------------------------------------------------- #
st.subheader("2. I bandi che fanno per te")
risultati = M.trova(profilo, bandi_canale, oggi=oggi)

if not risultati:
    st.warning("Nessun bando aperto compatibile con questo profilo. Prova a cambiare "
               "regione, settore o dimensione.")
else:
    st.success(f"**{len(risultati)} bandi compatibili e aperti** per "
               f"{M.SOGGETTI[tipo]} · {settore} · {regione}")
    for m in risultati[:50]:
        b = m.bando
        icona = ICONE_FONTE.get(b.fonte, "•")
        scad = (f"⏳ scade tra **{m.giorni_scadenza} giorni** ({b.data_scadenza})"
                if m.giorni_scadenza is not None else "senza scadenza fissa")
        urgente = m.giorni_scadenza is not None and m.giorni_scadenza <= 30
        with st.container(border=True):
            c1, c2 = st.columns([4, 1])
            with c1:
                titolo_mostrato = b.titolo_it or b.titolo
                st.markdown(f"### {icona} {titolo_mostrato}")
                if b.titolo_it and b.titolo_it.strip() != b.titolo.strip():
                    st.caption(f"Titolo originale: {b.titolo}")
                if b.fonte.strip().upper() == "UE":
                    st.markdown(f"🇮🇹 *{descrizione_ue(b)}*")
                st.caption(f"{b.ente} · {b.tipo_agevolazione.replace('_', ' ')} · "
                           f"{b.ambito} · dotazione {euro(b.dotazione)}")
                st.markdown((":red[" if urgente else "") + scad + ("]" if urgente else ""))
                if b.in_arrivo(oggi):
                    st.markdown(f":orange[🔜 In arrivo — apre il {b.data_apertura}]")
                st.markdown("**Perché per te:** " + " · ".join(m.motivi))
                if b.url:
                    st.markdown(f"[Vai al bando]({b.url})")
            with c2:
                st.metric("Pertinenza", f"{m.punteggio:.1f}")
    if len(risultati) > 50:
        st.caption(f"…e altri {len(risultati) - 50}. Affina il profilo per restringere.")

# --------------------------------------------------------------------------- #
# Sidebar
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.header("⏰ In scadenza")
    giorni = st.slider("Entro quanti giorni", 7, 90, 30, step=7)
    imminenti = A.scadenze_imminenti(profilo, bandi_canale, entro_giorni=giorni, oggi=oggi)
    if imminenti:
        for m in imminenti[:15]:
            st.markdown(f"**{m.giorni_scadenza}g** — {m.bando.titolo[:50]}")
    else:
        st.caption("Nessuna scadenza imminente per questo profilo.")

    st.divider()
    st.subheader("Catalogo")
    st.metric("Bandi in archivio", len(bandi))
    st.metric("Nel canale selezionato", len(bandi_canale))
    st.metric("Aperti oggi (nel canale)", sum(1 for b in bandi_canale if b.aperto(oggi)))
    with st.expander("Anteprima avviso email"):
        st.code(A.componi_avviso(profilo, risultati[:3], imminenti[:3]))
