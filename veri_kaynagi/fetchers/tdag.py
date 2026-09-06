"""Tekirdag Ticaret Borsasi (TDAG/TTB) - GUNLUK PDF bulten sistemi.

Anasayfada hicbir canli/gunluk link YOKTU ama kullanici /tr/bultentakvim sayfasindan
gercek bir ornek URL verdi: /gunluk/392026.pdf (03.09.2026 bulteni). O ornekten
ve komsu ID'leri (1..250 civari) tarayarak URL SEMASI TERS MUHENDISLIKLE cozuldu:

    ID = gun * 10 + ay   (orn. 03.09 -> 3*10+9 = 39 -> /gunluk/392026.pdf)

Bu formul gun=1..31, ay=1..9 icin dogrulandi (10.02->102, 20.02->202, 25.02->252,
15.01->151 hepsi doğru tarihi dondurdu). ONEMLI BELIRSIZLIK: ay=10/11/12 (Ekim-Aralik)
icin formul HENUZ DOGRULANAMADI - "gun*10+ay" mi yoksa "str(gun)+str(ay)" string
birlestirmesi mi kullanildigi iki haneli ay'da FARKLI sonuc verir (orn. 1 Ekim:
formul->1*10+10=20, string birlestirme->"1"+"10"="110"). Ekim 2026 geldiginde
gercek bir tarihle dogrulanip gerekirse duzeltilmeli.

Ayni /gunluk/ klasorunde ARADA SIRADA "Haftalik Bulten" da var (orn. ID 18, 44, 47)
ama bu ID'lerin formulu FARKLI/bilinmiyor - bu fetcher SADECE gunluk bultenleri
hedefliyor, haftaliklari atlar (indirdigi PDF'in basligi "Haftalık Bülten" cikarsa
veya PDF icindeki tarih istenen tarihle eslesmezse o gun icin veri DONDURMEZ - bu
sayede hem hafta sonu/tatil (bulten yok) hem yanlis ID eslesmesi guvenle ayirt edilir).

Backfill DESTEKLIYOR (URL dogrudan tarihten hesaplaniyor, sunucuya "hangi tarihler
var" diye sormaya gerek yok).
"""
import re
from datetime import date, datetime

import pdfplumber
import requests

from ..utils import TARAYICI_BASLIKLARI, simdi_iso, tr_sayi

BASE_URL = "https://www.tdag-ticbor.org.tr/gunluk/{id}{yil}.pdf"

SATIR_DESENI = re.compile(
    r"^([A-ZÇĞİÖŞÜa-zçğıöşü0-9][A-ZÇĞİÖŞÜa-zçğıöşü0-9. '/]*?)\s+(\d+)\s+0\s+"
    r"([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s+([\d.]+)\s+(Kg|Cv|Ad|Lt|Mt)\s+([\d.,]+)\s+(\S+)$",
    re.MULTILINE,
)
TARIH_DESENI = re.compile(r"(\d{2}\.\d{2}\.\d{4})")


def cek(tarih: str | None = None) -> list[dict]:
    tarih = tarih or date.today().isoformat()
    gun_obj = datetime.strptime(tarih, "%Y-%m-%d").date()
    beklenen_tarih_tr = gun_obj.strftime("%d.%m.%Y")

    bulten_id = gun_obj.day * 10 + gun_obj.month
    url = BASE_URL.format(id=bulten_id, yil=gun_obj.year)

    r = requests.get(url, timeout=30, verify=False, headers=TARAYICI_BASLIKLARI, allow_redirects=True)
    if r.status_code != 200 or not r.content.startswith(b"%PDF"):
        # o gun bulten yok (hafta sonu/tatil) ya da ID formulu bu ay icin gecersiz
        return []

    with __import__("io").BytesIO(r.content) as buf:
        with pdfplumber.open(buf) as pdf:
            tam_metin = "\n".join(p.extract_text() or "" for p in pdf.pages)

    if "Günlük Bülten" not in tam_metin:
        return []  # Haftalık Bülten'e denk gelmisiz, atla

    tarih_eslesme = TARIH_DESENI.search(tam_metin)
    if not tarih_eslesme or tarih_eslesme.group(1) != beklenen_tarih_tr:
        # ID formulu bu tarih icin yanlis PDF'e denk getirmis - guvenlik icin atla
        return []

    kayitlar = []
    for i, m in enumerate(SATIR_DESENI.findall(tam_metin)):
        urun, islem_sayisi, en_az, en_cok, ort, miktar, birim_kisa, tutar, satis_sekli = m
        kayitlar.append({
            "kaynak": "TDAG",
            "tarih": tarih,
            "il": "Tekirdağ",
            "ilce": None,
            "urun": urun.strip(),
            "detay": f"{satis_sekli}#{i}",
            "min_fiyat": tr_sayi(en_az),
            "ort_fiyat": tr_sayi(ort),
            "max_fiyat": tr_sayi(en_cok),
            "kapanis_fiyat": None,
            "miktar": tr_sayi(miktar),
            "birim": birim_kisa.upper(),
            "ham_veri": {"islem_sayisi": islem_sayisi, "tutar_tl": tutar, "satis_sekli": satis_sekli, "bulten_id": bulten_id},
            "cekilme_zamani": simdi_iso(),
        })
    return kayitlar
