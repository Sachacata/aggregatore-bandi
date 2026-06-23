@echo off
REM Aggiornamento automatico dell'aggregatore bandi.
REM Pianificabile con l'Utilita di pianificazione di Windows (Task Scheduler).
cd /d "C:\Users\Utente-XB\Documents\Claude\Projects\Creazione sito comparativo farmacie\aggregatore-bandi"
python src\aggiorna.py >> data\aggiorna.log 2>&1
