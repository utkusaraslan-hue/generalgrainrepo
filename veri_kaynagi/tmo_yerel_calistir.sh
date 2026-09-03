#!/bin/bash
# TMO GitHub Actions'tan (bulut IP'leri) engellendigi icin (bkz. commit gecmisi
# ve proje hafizasi) SADECE bu script yerel olarak (kullanicinin Mac'i) TMO'yu
# cekip repoya push ediyor. TURIB + Konya hala GitHub Actions'ta.
set -euo pipefail

PROJE_DIZINI="/Users/utkus/yine-bi-agent"
cd "$PROJE_DIZINI"

"$PROJE_DIZINI/.venv/bin/python3" -m veri_kaynagi.main --kaynak tmo

if ! /usr/bin/git diff --quiet -- veri_kaynagi/borsa_verileri.db veri_kaynagi/arsiv \
   || ! /usr/bin/git diff --cached --quiet -- veri_kaynagi/borsa_verileri.db veri_kaynagi/arsiv; then
  /usr/bin/git add veri_kaynagi/borsa_verileri.db veri_kaynagi/arsiv
  /usr/bin/git commit -m "TMO yerel cekim: $(date +%Y-%m-%d\ %H:%M)"
  /usr/bin/git pull --rebase origin main
  /usr/bin/git push origin main
fi
