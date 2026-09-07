#!/bin/bash
# Her gun 21:30'da (GitHub Actions'in son 21:00 TRT cekiminden sonra) calisir:
# 1) en guncel veriyi (TMO'nun yerel commit'leri + GH Actions'in pushladigi
#    TURIB/Konya/4 borsa) cekmek icin git pull yapar
# 2) o gunun klasorunu (~/Desktop/bizim-gunluk-bulten/{D-M-YYYY}/) olusturup
#    icine Excel + PDF ozet yazar
set -euo pipefail

PROJE_DIZINI="/Users/utkus/yine-bi-agent"
cd "$PROJE_DIZINI"

# Onceki calismadan yarim kalmis rebase varsa (ornek: TMO scripti ile ayni
# db dosyasi uzerinde catisma), sessizce "|| true" ile gecmek gelecekteki
# TUM pull'lari bozar (09-2026'da 4 gun boyle oldu) - once temizle.
if [ -d .git/rebase-merge ] || [ -d .git/rebase-apply ]; then
  /usr/bin/git rebase --abort || true
fi

if ! /usr/bin/git pull --rebase origin main; then
  /usr/bin/git rebase --abort || true
  /usr/bin/git fetch origin main
  /usr/bin/git reset --hard origin/main
fi

/Library/Frameworks/Python.framework/Versions/3.14/bin/python3 -m gunluk_ozet.gunluk_ozet_uret
