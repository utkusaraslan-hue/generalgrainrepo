"""Kirklareli Ticaret Borsasi (KTB) - digerlerinin aksine gunluk canli bulten
sistemi YOK, sadece AYLIK PDF bulten yayinliyor (ay bittikten ~2-3 hafta sonra).

Bu yuzden bu kaynak GUNLUK degil, AYLIK cozunurlukte veri uretir - ayni urun
icin ay boyunca satis sekline (HMS/HTS/KOP.A/Y.T.K vb.) gore ayri satirlar halinde
min/max/ortalama fiyat + toplam miktar veriyor, tek bir gune indirgemiyor.

PDF sabit bir URL'de degil, her ay yeni bir dosya adiyla /bultenler sayfasinda
yayinlaniyor; bu yuzden TMO gibi "sadece en guncel" mantigiyla calisiyoruz -
her calistirmada /bultenler sayfasindaki EN UST (en yeni) bulten linkini bulup
onu isliyoruz. Ayni ay tekrar cekilirse DB'deki UNIQUE kisit (kaynak, tarih,
urun, detay, il, ilce) sayesinde idempotent kalir.
"""
import re
from datetime import date
from pathlib import Path

import pdfplumber
import requests
from bs4 import BeautifulSoup

from ..utils import TARAYICI_BASLIKLARI, simdi_iso, tr_sayi

BULTENLER_URL = "https://www.kirklarelitb.org.tr/bultenler"
ARSIV_DIZINI = Path(__file__).parent.parent / "arsiv" / "kirklareli"

TR_AYLAR = {
    "OCAK": 1, "ŞUBAT": 2, "MART": 3, "NİSAN": 4, "MAYIS": 5, "HAZİRAN": 6,
    "TEMMUZ": 7, "AĞUSTOS": 8, "EYLÜL": 9, "EKİM": 10, "KASIM": 11, "ARALIK": 12,
}

SATIR_DESENI = re.compile(
    r"^([A-ZÇĞİÖŞÜ][A-ZÇĞİÖŞÜ .'0-9]*?)\s+(\d+)\s+0\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+KG\s+([\d,.]+)\s+(\S+)$",
    re.MULTILINE,
)
DONEM_DESENI = re.compile(r"Tarih Aralığı:\s*([A-ZÇĞİÖŞÜ]+)-(\d{4})")
# Eski bultenler (2025 sonu ve oncesi) farkli bir tarih formati kullaniyor:
# "BültenTarih Aralığı: 01.09.2025 - 30.09.2025" (ay adi degil, DD.MM.YYYY araligi)
DONEM_ARALIK_DESENI = re.compile(r"Tarih Aralığı:\s*\d{2}\.\d{2}\.\d{4}\s*-\s*(\d{2})\.(\d{2})\.(\d{4})")


def _en_guncel_bulten_linki() -> tuple[str, str]:
    """(sayfa_url, baslik) dondurur - /bultenler listesindeki EN UST (en yeni) satir."""
    r = requests.get(BULTENLER_URL, timeout=30, verify=False, headers=TARAYICI_BASLIKLARI)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    for a in soup.find_all("a", href=True):
        metin = a.get_text(strip=True)
        if "AYLIK BÜLTEN" in metin.upper() or "AYI BÜLTENİ" in metin.upper():
            return a["href"], metin
    raise RuntimeError("Kirklareli: /bultenler sayfasinda aylik bulten linki bulunamadi")


def _pdf_linkini_bul(sayfa_url: str) -> str:
    r = requests.get(sayfa_url, timeout=30, verify=False, headers=TARAYICI_BASLIKLARI)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    for a in soup.find_all("a", href=True):
        if a["href"].lower().endswith(".pdf"):
            return a["href"]
    raise RuntimeError(f"Kirklareli: {sayfa_url} icinde PDF linki bulunamadi")


def _donem_tarihi(metin: str) -> str:
    """PDF icindeki 'Tarih Aralığı: TEMMUZ-2026' (yeni) veya
    'Tarih Aralığı: 01.09.2025 - 30.09.2025' (eski) -> o ayin son gunu (ISO)."""
    m2 = DONEM_ARALIK_DESENI.search(metin)
    if m2:
        gun, ay_no, yil = m2.groups()
        return f"{yil}-{ay_no}-{gun}"

    m = DONEM_DESENI.search(metin)
    if not m:
        raise ValueError("Kirklareli: PDF icinde 'Tarih Aralığı' bulunamadi - bilinmeyen format, tarihi tahmin etmek yerine hata veriliyor")
    ay = TR_AYLAR.get(m.group(1).upper())
    yil = int(m.group(2))
    if not ay:
        raise ValueError(f"Kirklareli: bilinmeyen ay adi '{m.group(1)}'")
    # ayin son gunu
    if ay == 12:
        son_gun = date(yil, 12, 31)
    else:
        from datetime import timedelta
        son_gun = date(yil, ay + 1, 1) - timedelta(days=1)
    return son_gun.isoformat()


def cek(tarih: str | None = None) -> list[dict]:
    """tarih parametresi yok sayilir - her zaman /bultenler sayfasindaki EN GUNCEL
    aylik bulteni ceker (backfill desteklenmiyor, TMO/ETB ile ayni mantik)."""
    sayfa_url, baslik = _en_guncel_bulten_linki()
    pdf_url = _pdf_linkini_bul(sayfa_url)

    r = requests.get(pdf_url, timeout=60, verify=False, headers=TARAYICI_BASLIKLARI)
    r.raise_for_status()

    ARSIV_DIZINI.mkdir(parents=True, exist_ok=True)
    dosya_adi = pdf_url.rsplit("/", 1)[-1]
    (ARSIV_DIZINI / dosya_adi).write_bytes(r.content)

    import io
    with pdfplumber.open(io.BytesIO(r.content)) as pdf:
        tam_metin = "\n".join(p.extract_text() or "" for p in pdf.pages)

    donem_tarihi = _donem_tarihi(tam_metin)

    kayitlar = []
    for i, m in enumerate(SATIR_DESENI.findall(tam_metin)):
        urun, islem_sayisi, en_az, en_cok, ort, miktar, tutar, satis_sekli = m
        kayitlar.append({
            "kaynak": "KIRKLARELI_AYLIK",
            "tarih": donem_tarihi,
            "il": "Kırklareli",
            "ilce": None,
            "urun": urun.strip(),
            "detay": f"{satis_sekli}#{i}",
            # PDF'teki fiyat sutunlari aslinda TL/TON (dip not: nokta bin ayraci,
            # ondalik yok - "12.350" = 12.350 TL/ton). Diger tum kaynaklarla (TÜRİB,
            # Bandirma, TDAG, ETB canli - hepsi TL/KG) tutarli olmasi icin 1000'e
            # bolunuyor - bolunmezse min/ort/max_fiyat yanlislikla 1000 kat buyuk
            # cikiyor (bkz proje hafizasi, kullanici fark etti).
            "min_fiyat": tr_sayi(en_az) / 1000 if tr_sayi(en_az) is not None else None,
            "ort_fiyat": tr_sayi(ort) / 1000 if tr_sayi(ort) is not None else None,
            "max_fiyat": tr_sayi(en_cok) / 1000 if tr_sayi(en_cok) is not None else None,
            "kapanis_fiyat": None,
            "miktar": tr_sayi(miktar),
            "birim": "KG",
            "ham_veri": {
                "islem_sayisi": islem_sayisi, "tutar_tl": tutar, "satis_sekli": satis_sekli,
                "bulten_baslik": baslik, "pdf_url": pdf_url,
            },
            "cekilme_zamani": simdi_iso(),
        })
    return kayitlar
