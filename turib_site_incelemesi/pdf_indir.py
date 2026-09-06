import json
import re
import time
from pathlib import Path
from urllib.parse import urlparse, unquote

import requests

KOK = Path(__file__).parent
# Agir PDF arsivi git'e alinmiyor - Masaustunde saklaniyor (bkz PROJE_GECMISI.md).
HEDEF = Path.home() / "Desktop" / "4-09-2026-turib" / "mevzuat-arsiv" / "pdf_arsiv"
HEDEF.mkdir(parents=True, exist_ok=True)

linkler = json.loads((KOK / "tum_pdf_linkleri.json").read_text())
basliklar = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

sonuc = []
for i, url in enumerate(linkler, 1):
    ad = unquote(Path(urlparse(url).path).name) or f"dosya_{i}.pdf"
    ad = re.sub(r"[^\w.\-]", "_", ad)[:150]
    if not ad.lower().endswith(".pdf"):
        ad += ".pdf"
    hedef_yol = HEDEF / ad
    if hedef_yol.exists():
        sonuc.append({"url": url, "dosya": ad, "durum": "zaten_var"})
        continue
    try:
        r = requests.get(url, headers=basliklar, timeout=30, verify=False)
        if r.status_code == 200 and len(r.content) > 500:
            hedef_yol.write_bytes(r.content)
            sonuc.append({"url": url, "dosya": ad, "durum": "indirildi", "boyut": len(r.content)})
        else:
            sonuc.append({"url": url, "dosya": ad, "durum": f"hata_{r.status_code}"})
    except Exception as e:
        sonuc.append({"url": url, "dosya": ad, "durum": f"hata: {e}"})
    if i % 30 == 0:
        print(f"[{i}/{len(linkler)}] islendi")
    time.sleep(0.15)

(KOK / "pdf_indirme_sonucu.json").write_text(json.dumps(sonuc, ensure_ascii=False, indent=2), encoding="utf-8")
basarili = sum(1 for s in sonuc if s["durum"] in ("indirildi", "zaten_var"))
print(f"\nToplam: {len(sonuc)}, basarili: {basarili}")
