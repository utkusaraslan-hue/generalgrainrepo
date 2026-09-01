"""TMO Gunluk Piyasa ve Borsa Fiyatlari Bulteni.

ONEMLI: Bulten X gunu yayinlansa da icindeki fiyatlar X-1 gunune (bir onceki
is gunune) aittir - TMO PDF'i her is gunu ogleden sonra (~13:30 TRT, olcum:
Last-Modified header'i 10:33 GMT olarak gozlendi) bir onceki gunun kapanis
fiyatlarini yayinliyor. Bu yuzden veritabanina yazilan `tarih`, calistirma
gunu DEGIL, PDF'in kendi icindeki "YURT ICI FIYATLAR" basligindaki tarih
sutunundan (en guncel kolon) parse ediliyor - boylece TURIB/Konya ile ayni
takvim gunune hizalaniyor.

PDF URL'i sabit ve her gun uzerine yaziliyor (TMO tarafinda arsiv yok), bu yuzden
her calistirmada PDF'i (fiyatlarin ait oldugu gune gore) tarih damgali olarak
diske arsivliyoruz ve ayrica ana borsa fiyatlarini (Konya/Polatli/Eskisehir/
Edirne/Adana - bugday/arpa/misir) duzenli satirlar halinde veritabanina
yaziyoruz. Tum metni de tek bir "ham" kayit olarak sakliyoruz ki regex'in
yakalayamadigi hicbir sey kaybolmasin.
"""
import re
from datetime import date, datetime
from pathlib import Path

import pdfplumber
import requests

from ..utils import TARAYICI_BASLIKLARI, simdi_iso, tr_sayi

BULTEN_URL = "https://www.tmo.gov.tr/Upload/Document/piyasabulteni/piyasabulteni_tr.pdf"
ARSIV_DIZINI = Path(__file__).parent.parent / "arsiv" / "tmo"

TR_AYLAR = {
    "Ocak": 1, "Şubat": 2, "Mart": 3, "Nisan": 4, "Mayıs": 5, "Haziran": 6,
    "Temmuz": 7, "Ağustos": 8, "Eylül": 9, "Ekim": 10, "Kasım": 11, "Aralık": 12,
}

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


def _yayin_tarihini_bul(tam_metin: str) -> str | None:
    """Ust basliktaki '1 Eylül 2026 Salı' gibi ifadeyi bulur (sadece bilgi amacli)."""
    m = re.search(r"(\d{1,2})\s+(" + "|".join(TR_AYLAR) + r")\s+(\d{4})", tam_metin)
    if not m:
        return None
    gun, ay, yil = m.groups()
    return date(int(yil), TR_AYLAR[ay], int(gun)).isoformat()


def _fiyat_tarihini_bul(yurt_ici_metin: str) -> str:
    """Bultendeki fiyatlarin GERCEKTEN ait oldugu gunu bulur: 'YURT İÇİ FİYATLAR
    (TL/TON) 31.08.2026 28.08.2026 ...' satirindaki ilk (en guncel) tarih."""
    m = re.search(r"YURT İÇİ FİYATLAR.*?(\d{2})\.(\d{2})\.(\d{4})", yurt_ici_metin, re.S)
    if not m:
        raise ValueError("Bultende 'YURT İÇİ FİYATLAR' tarih basligi bulunamadi")
    gun, ay, yil = m.groups()
    return datetime.strptime(f"{gun}.{ay}.{yil}", "%d.%m.%Y").date().isoformat()


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
    """`tarih` parametresi TMO icin kullanilmiyor: URL sabit ve daima "su an
    yayinda olan" bulteni doner, gecmis bir tarih icin ozel olarak istenemez.
    Kayitlarin gercek `tarih`'i, bultenin kendi icindeki fiyat tarihinden
    parse ediliyor (bkz. modul dokstring'i - 1 gunluk gecikme var)."""
    icerik = _pdf_indir()
    # Once gecici bir isimle indirip metni okuyoruz ki fiyat tarihini ogrenip
    # arsiv dosyasini DOGRU isimle kaydedebilelim.
    gecici_yol = ARSIV_DIZINI.parent / "_tmo_gecici.pdf"
    gecici_yol.parent.mkdir(parents=True, exist_ok=True)
    gecici_yol.write_bytes(icerik)
    tam_metin, yurt_ici_metin = _metni_cikar(gecici_yol)
    gecici_yol.unlink()

    fiyat_tarihi = _fiyat_tarihini_bul(yurt_ici_metin)
    yayin_tarihi = _yayin_tarihini_bul(tam_metin)
    pdf_yolu = _arsivle(icerik, fiyat_tarihi)

    kayitlar = _satirlari_parse_et(yurt_ici_metin, fiyat_tarihi)
    # Regex'in yakalamadigi her sey icin tum metni tek bir yedek kayit olarak sakla.
    kayitlar.append({
        "kaynak": "TMO_HAM_METIN",
        "tarih": fiyat_tarihi,
        "il": None, "ilce": None,
        "urun": "tam_bulten_metni",
        "detay": None,
        "min_fiyat": None, "ort_fiyat": None, "max_fiyat": None, "kapanis_fiyat": None,
        "miktar": None, "birim": None,
        "ham_veri": {
            "metin": tam_metin, "pdf_dosyasi": str(pdf_yolu),
            "yayin_tarihi": yayin_tarihi, "fiyat_tarihi": fiyat_tarihi,
        },
        "cekilme_zamani": simdi_iso(),
    })
    return kayitlar
