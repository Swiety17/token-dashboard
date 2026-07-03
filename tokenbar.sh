#!/bin/bash
# TokenBar Launcher — uruchamia apkę menu bar
# Sposoby odpalenia:
#   1. Kliknij dwukrotnie w Finderze
#   2. ./tokenbar.sh
#   3. Dodaj do Login Items (System Settings → General → Login Items)

cd "$(dirname "$0")"
python3 tokenbar.py &
echo "TokenBar uruchomiony — ikona 🪙 w menu barze."
echo "Aby zatrzymać: kliknij ikonę → Quit"
