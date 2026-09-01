"""TMO Gunluk Piyasa ve Borsa Fiyatlari Bulteni.

PDF URL'i sabit ve her gun uzerine yaziliyor (TMO tarafinda arsiv yok), bu yuzden
her calistirmada PDF'i tarih damgali olarak diske arsivliyoruz ve ayrica ana
borsa fiyatlarini (Konya/Polatli/Eskisehir/Edirne/Adana - bugday/arpa/misir)
duzenli satirlar halinde veritabanina yaziyoruz. Tum metni de tek bir "ham"
kayit olarak sakliyoruz ki regex'in yakalayamadigi hicbir sey kaybolmasin.
"""
import re
from datetime import date
from pathlib import Path

import pdfplumber
import requests

from ..utils import TARAYICI_BASLIKLARI, simdi_iso, tr_sayi

BULTEN_URL = "https://www.tmo.gov.tr/Upload/Document/piyasabulteni/piyasabulteni_tr.pdf"
ARSIV_DIZINI = Path(__file__).parent.parent / "arsiv" / "tmo"

# "Konya 93 17.172 356 156 17.050 354 13.022 32" gibi satirlari yakalar:
# borsa_adi, miktar1, tl1, usd1, miktar2, tl2, usd2, gecenyil_tl, yillik_degisim
BORSA_SATIR = re.compile(
    r"^(Konya|Polatlı|Eskişehir|Edirne|Adana|Çorum)\s+"
    r"([\d.,-]+)\s+([\d.,-]+)\s+([\d.,-]+)\s+([\d.,-]+)\s+([\d.,-]+)\s+([\d.,-]+)\s+([\d.,-]+)\s+([\d.,-]+)$"
)

URUN_BASLIKLARI = {
    "MAKARNALIK BUĞDAY": "Makarnalık Buğday",
    "KIRMIZI SERT BUĞDAY": "Kırmızı Sert Buğday",
    "DİĞER BEYAZ BUĞDAYLAR": "Diğer Beyaz Buğdaylar",
    "DİĞER KIRMIZI BUĞDAYLAR": "Diğer Kırmızı Buğdaylar",
    "ARPA": "Arpa",
    "MISIR": "Mısır",
    "YULAF": "Yulaf",
    "SOYA FASULYESİ": "Soya Fasulyesi",
}


def _pdf_indir() -> bytes:
    r = requests.get(BULTEN_URL, timeout=30, verify=False, headers=TARAYICI_BASLIKLARI)
    r.raise_for_status()
    return r.content


def _arsivle(icerik: bytes, tarih: str) -> Path:
    ARSIV_DIZINI.mkdir(parents=True, exist_ok=True)
    hedef = ARSIV_DIZINI / f"piyasabulteni_{tarih}.pdf"
    hedef.write_bytes(icerik)
    return hedef


def _metni_cikar(pdf_yolu: Path) -> str:
    """Tum sayfa metnini (fallback/arsiv icin) ve ilk sayfanin sol yarisini
    (yurt ici fiyat tablosu - grafik/uluslararasi sutunla karismadan) ayri doner."""
    with pdfplumber.open(pdf_yolu) as pdf:
        tam_metin = "\n".join(sayfa.extract_text() or "" for sayfa in pdf.pages)
        ilk_sayfa = pdf.pages[0]
        sol_yari = ilk_sayfa.crop((0, 0, ilk_sayfa.width * 0.52, ilk_sayfa.height))
        yurt_ici_metin = sol_yari.extract_text() or ""
    return tam_metin, yurt_ici_metin


def _satirlari_parse_et(metin: str, tarih: str) -> list[dict]:
    kayitlar = []
    urun = None
    for satir in metin.splitlines():
        satir = satir.strip()
        if satir in URUN_BASLIKLARI:
            urun = URUN_BASLIKLARI[satir]
            continue
        m = BORSA_SATIR.match(satir)
        if m and urun:
            borsa, miktar1, tl1, usd1, miktar2, tl2, usd2, gecen_tl, _yillik = m.groups()
            kayitlar.append({
                "kaynak": "TMO",
                "tarih": tarih,
                "il": borsa,
                "ilce": None,
                "urun": urun,
                "detay": "borsa_fiyati",
                "min_fiyat": None,
                "ort_fiyat": tr_sayi(tl1),
                "max_fiyat": None,
                "kapanis_fiyat": tr_sayi(tl1),
                "miktar": tr_sayi(miktar1),
                "birim": "TL/ton",
                "ham_veri": {
                    "satir": satir, "miktar_ton": tr_sayi(miktar1), "tl_ton": tr_sayi(tl1),
                    "usd_ton": tr_sayi(usd1), "onceki_donem_miktar_ton": tr_sayi(miktar2),
                    "onceki_donem_tl_ton": tr_sayi(tl2), "onceki_donem_usd_ton": tr_sayi(usd2),
                    "gecen_yil_tl_ton": tr_sayi(gecen_tl),
                },
                "cekilme_zamani": simdi_iso(),
            })
    return kayitlar


def cek(tarih: str | None = None) -> list[dict]:
    tarih = tarih or date.today().isoformat()
    icerik = _pdf_indir()
    pdf_yolu = _arsivle(icerik, tarih)
    tam_metin, yurt_ici_metin = _metni_cikar(pdf_yolu)

    kayitlar = _satirlari_parse_et(yurt_ici_metin, tarih)
    # Regex'in yakalamadigi her sey icin tum metni tek bir yedek kayit olarak sakla.
    kayitlar.append({
        "kaynak": "TMO_HAM_METIN",
        "tarih": tarih,
        "il": None, "ilce": None,
        "urun": "tam_bulten_metni",
        "detay": None,
        "min_fiyat": None, "ort_fiyat": None, "max_fiyat": None, "kapanis_fiyat": None,
        "miktar": None, "birim": None,
        "ham_veri": {"metin": tam_metin, "pdf_dosyasi": str(pdf_yolu)},
        "cekilme_zamani": simdi_iso(),
    })
    return kayitlar
