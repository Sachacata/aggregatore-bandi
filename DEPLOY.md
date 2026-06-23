# Deploy di Volano su Streamlit Community Cloud

Guida passo-passo per mettere l'app online (gratis) e tenerla aggiornata da sola.

## A. Mettere il progetto su GitHub

### Opzione consigliata: GitHub Desktop (no riga di comando)
1. Installa **GitHub Desktop** e accedi col tuo account GitHub.
2. `File → Add local repository` → seleziona la cartella `aggregatore-bandi`.
   Se chiede di creare il repository, conferma ("create a repository").
3. In basso a sinistra scrivi un messaggio (es. *"Primo commit Volano"*) →
   **Commit to main**.
4. In alto **Publish repository** → dai un nome (es. `volano`) → scegli
   pubblico o privato → **Publish**.

> Streamlit Community Cloud funziona anche con repo **privato** (collegando il
> tuo account GitHub). Se preferisci tenere il codice non visibile, scegli privato.

### Opzione alternativa: riga di comando (git)
```bash
cd "percorso\aggregatore-bandi"
git init
git add .
git commit -m "Primo commit Volano"
git branch -M main
git remote add origin https://github.com/TUO-UTENTE/volano.git
git push -u origin main
```

## B. Pubblicare l'app

1. Vai su **share.streamlit.io** e accedi con GitHub.
2. **Create app** → seleziona il repository `volano`, branch `main`,
   **Main file path:** `app.py`.
3. **Deploy**. In 1-2 minuti hai il link pubblico (es. `volano.streamlit.app`).

`requirements.txt` è già presente: Streamlit installa le dipendenze da solo.

## C. Attivare l'aggiornamento automatico (già pronto)

Il file `.github/workflows/aggiorna.yml` è già nel repo: ogni notte scarica i
dati nazionali (incentivi.gov.it) ed europei (API UE), rileva i nuovi bandi e
ricarica i dati. Streamlit ridispiega l'app a ogni aggiornamento.

Per farlo funzionare:
1. Su GitHub: `Settings → Actions → General → Workflow permissions` →
   seleziona **Read and write permissions** → Save.
2. (Facoltativo) Lancialo subito a mano per provarlo: tab **Actions** →
   *"Aggiorna dati bandi"* → **Run workflow**.

## Note

- **Repo pubblico**: il codice è visibile a tutti. Va bene: contiene solo dati di
  bandi **pubblici**, nessun dato personale.
- **Traduzione titoli UE**: non viene eseguita nell'aggiornamento notturno (per
  leggerezza). I bandi UE mostrano il titolo in inglese + la descrizione in
  italiano. La traduzione automatica si può aggiungere in un secondo momento.
- **Quando aggiungerai account/email utenti** (per gli alert personali), quello è
  trattamento di dati personali: va gestito separatamente, con informativa e
  base giuridica (GDPR), e NON nel repo pubblico.
