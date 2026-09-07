#!/bin/bash
# TMO GitHub Actions'tan (bulut IP'leri) engellendigi icin (bkz. commit gecmisi
# ve proje hafizasi) SADECE bu script yerel olarak (kullanicinin Mac'i) TMO'yu
# cekip repoya push ediyor. TURIB + Konya hala GitHub Actions'ta.
set -uo pipefail

PROJE_DIZINI="/Users/utkus/yine-bi-agent"
cd "$PROJE_DIZINI"

# borsa_verileri.db ikili (binary) bir dosya oldugu icin, eger onceki bir
# calisma (bu script ya da gunluk_ozet scripti) yarim kalmis bir rebase
# birakmissa git rebase --continue/--abort ISTER ISTEMEZ conflict verir ve
# set -e ile script burada takilip kalirdi (09-2026'da 4 gun boyunca boyle
# oldu). Once temizle: yarim rebase varsa guvenle abort et (calisma agacinda
# commit edilmemis TMO verisi henuz yok, cunku fetch daha calismadi).
if [ -d .git/rebase-merge ] || [ -d .git/rebase-apply ]; then
  /usr/bin/git rebase --abort || true
fi

# ONCE pull yap (boylece TMO fetch'i zaten guncel db uzerine yazilir, commit
# yapmadan once local ile origin ayni noktada olur - boylece asagidaki commit
# origin ile hicbir zaman catallanmaz).
if ! /usr/bin/git pull --rebase origin main; then
  /usr/bin/git rebase --abort || true
  /usr/bin/git fetch origin main
  /usr/bin/git reset --hard origin/main
fi

"$PROJE_DIZINI/.venv/bin/python3" -m veri_kaynagi.main --kaynak tmo

if ! /usr/bin/git diff --quiet -- veri_kaynagi/borsa_verileri.db veri_kaynagi/arsiv \
   || ! /usr/bin/git diff --cached --quiet -- veri_kaynagi/borsa_verileri.db veri_kaynagi/arsiv; then
  /usr/bin/git add veri_kaynagi/borsa_verileri.db veri_kaynagi/arsiv
  /usr/bin/git commit -m "TMO yerel cekim: $(date +%Y-%m-%d\ %H:%M)"

  # push sirasinda araya biri (GH Actions) girmis olabilir; birkac kez
  # pull --rebase + push dene, basarisiz olursa rebase'i abort edip birakma -
  # bir sonraki calisma zaten pull ile toparlar.
  basarili=0
  for deneme in 1 2 3; do
    if /usr/bin/git push origin main; then
      basarili=1
      break
    fi
    if /usr/bin/git pull --rebase origin main; then
      continue
    else
      /usr/bin/git rebase --abort || true
      break
    fi
  done
  if [ "$basarili" -ne 1 ]; then
    echo "UYARI: TMO commit'i push edilemedi, bir sonraki calismada tekrar denenecek" >&2
  fi
fi
