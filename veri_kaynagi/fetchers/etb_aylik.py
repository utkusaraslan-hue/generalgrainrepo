"""Edirne Ticaret Borsasi (ETB) - AYLIK PDF bulten arsivi.

ONEMLI: Ilk kesifte (bkz proje hafizasi) bu kaynak KACIRILMISTI - "/aylikbulten/
aylik-bulten" sayfasinin nav linkine bakilip icerigi hic ACILMAMISTI. Kullanici
gercek bir PDF ornegi verince (AĞUSTOS 2026.pdf) fark edildi. Sayfanin PDF listesi
sayfa govdesinde degil, "/filterAylikBultenData/{yil}" AJAX endpoint'inden JS ile
yukleniyor; yil=0 verilirse TUM YILLARIN (2005'ten 2026'ya, 257 PDF) listesi tek
seferde donuyor - kimlik dogrulama gerekmiyor.

PDF sablonu Kirklareli ile AYNI (ayni "Dok. No: 7.5 S1 F05" altyapisi/yazilim
saglayicisi olmali) - ayni SATIR_DESENI regex'i calisiyor.

Ay isimleri dosya adinda gecuyor (orn. "AĞUSTOS 2026.pdf", bazen "EKİM-2025.pdf"
tire ile) - buradan tarih (ayin son gunu) turetiliyor.

Backfill: TAM DESTEKLIYOR - istenen ay listede varsa (2005-2026 arasi) dogrudan
cekilebiliyor, TMO/canli-ETB'nin aksine.
"""
import re
from datetime import date, timedelta
from pathlib import Path

import pdfplumber
import requests
from bs4 import BeautifulSoup

from ..utils import TARAYICI_BASLIKLARI, simdi_iso, tr_sayi

LISTE_URL = "https://www.etb.org.tr/filterAylikBultenData/0"
ARSIV_DIZINI = Path(__file__).parent.parent / "arsiv" / "etb_aylik"

TR_AYLAR = {
    "OCAK": 1, "ŞUBAT": 2, "MART": 3, "NİSAN": 4, "MAYIS": 5, "HAZİRAN": 6,
    "TEMMUZ": 7, "AĞUSTOS": 8, "EYLÜL": 9, "EKİM": 10, "KASIM": 11, "ARALIK": 12,
}

SATIR_DESENI = re.compile(
    r"^([A-ZÇĞİÖŞÜa-zçğıöşü][A-ZÇĞİÖŞÜa-zçğıöşü .'()0-9]*?)\s+(\d+)\s+0\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+Kg\s+([\d,.]+)\s+(\S+)$",
    re.MULTILINE | re.IGNORECASE,
)
DOSYA_ADI_DESENI = re.compile(r"([A-ZÇĞİÖŞÜ]+)[-\s](\d{4})\.pdf$", re.IGNORECASE)


def _tum_bultenleri_listele() -> dict[tuple[int, int], str]:
    """(yil, ay) -> pdf_url sozlugu."""
    r = requests.get(LISTE_URL, timeout=30, verify=False, headers=TARAYICI_BASLIKLARI)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    sozluk = {}
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not href.lower().endswith(".pdf"):
            continue
        dosya_adi = href.rsplit("/", 1)[-1]
        m = DOSYA_ADI_DESENI.search(dosya_adi)
        if not m:
            continue
        ay_adi, yil = m.group(1).upper(), int(m.group(2))
        ay = TR_AYLAR.get(ay_adi)
        if ay:
            sozluk[(yil, ay)] = href
    return sozluk


def _ay_sonu(yil: int, ay: int) -> str:
    if ay == 12:
        return date(yil, 12, 31).isoformat()
    return (date(yil, ay + 1, 1) - timedelta(days=1)).isoformat()


def cek(tarih: str | None = None) -> list[dict]:
    hedef = date.fromisoformat(tarih) if tarih else date.today()
    bultenler = _tum_bultenleri_listele()

    pdf_url = bultenler.get((hedef.year, hedef.month))
    if not pdf_url:
        return []  # o ay icin bulten henuz yayinlanmamis / arsivde yok

    r = requests.get(pdf_url, timeout=60, verify=False, headers=TARAYICI_BASLIKLARI)
    r.raise_for_status()

    ARSIV_DIZINI.mkdir(parents=True, exist_ok=True)
    dosya_adi = pdf_url.rsplit("/", 1)[-1]
    (ARSIV_DIZINI / dosya_adi).write_bytes(r.content)

    import io
    with pdfplumber.open(io.BytesIO(r.content)) as pdf:
        tam_metin = "\n".join(p.extract_text() or "" for p in pdf.pages)

    donem_tarihi = _ay_sonu(hedef.year, hedef.month)

    kayitlar = []
    for i, m in enumerate(SATIR_DESENI.findall(tam_metin)):
        urun, islem_sayisi, en_az, en_cok, ort, miktar, tutar, satis_sekli = m
        kayitlar.append({
            "kaynak": "ETB_AYLIK",
            "tarih": donem_tarihi,
            "il": "Edirne",
            "ilce": None,
            "urun": urun.strip(),
            "detay": f"{satis_sekli}#{i}",
            # PDF'teki fiyat sutunlari aslinda TL/TON (Kirklareli ile ayni sablon,
            # bkz kirklareli.py'deki ayni notu) - diger kaynaklarla (TL/KG) tutarli
            # olmasi icin 1000'e bolunuyor.
            "min_fiyat": tr_sayi(en_az) / 1000 if tr_sayi(en_az) is not None else None,
            "ort_fiyat": tr_sayi(ort) / 1000 if tr_sayi(ort) is not None else None,
            "max_fiyat": tr_sayi(en_cok) / 1000 if tr_sayi(en_cok) is not None else None,
            "kapanis_fiyat": None,
            "miktar": tr_sayi(miktar),
            "birim": "KG",
            "ham_veri": {
                "islem_sayisi": islem_sayisi, "tutar_tl": tutar, "satis_sekli": satis_sekli,
                "pdf_url": pdf_url,
            },
            "cekilme_zamani": simdi_iso(),
        })
    return kayitlar
