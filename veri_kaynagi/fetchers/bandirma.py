"""Bandirma Ticaret Borsasi (BANTB) - Alpata degil, ayri bir ASP.NET/DevExtreme
altyapili "bulten.bantb.org.tr" tescil sistemi.

/Tescil/TescilTarihli endpoint'i StartDate/EndDate araligini kabul ediyor (format:
DD.MM.YYYY, Turkce virgullu ondalik), kimlik dogrulama gerektirmiyor. Urun bazinda
(ISIN degil, dahili urunKodu) gunluk ozet: min/ort/max fiyat + islem adedi + toplam
miktar. Backfill destekleniyor (herhangi bir gecmis tarih sorgulanabiliyor).
"""
from datetime import date, datetime

import requests

from ..utils import TARAYICI_BASLIKLARI, simdi_iso, tr_sayi

API_URL = "https://bulten.bantb.org.tr/Tescil/TescilTarihli"


def _fiyat_ayikla(deger) -> float | None:
    """'17,212 TL' -> 17.212 ; None/'' -> None"""
    if deger is None:
        return None
    s = str(deger).replace("TL", "").strip()
    return tr_sayi(s)


def cek(tarih: str | None = None) -> list[dict]:
    tarih = tarih or date.today().isoformat()
    tarih_tr = datetime.strptime(tarih, "%Y-%m-%d").strftime("%d.%m.%Y")

    r = requests.get(
        API_URL,
        params={"StartDate": tarih_tr, "EndDate": tarih_tr, "UrunGrubu": ""},
        timeout=30, verify=False, headers=TARAYICI_BASLIKLARI,
    )
    r.raise_for_status()
    veri = r.json()

    kayitlar = []
    for satir in veri:
        detay = f"{satir.get('anaUrunAdi')} > {satir.get('altUrunAdi')} ({satir.get('urunKodu')})"
        kayitlar.append({
            "kaynak": "BANDIRMA",
            "tarih": tarih,
            "il": "Balıkesir",
            "ilce": "Bandırma",
            "urun": satir.get("urunAdi"),
            "detay": detay,
            "min_fiyat": _fiyat_ayikla(satir.get("minFiyat")),
            "ort_fiyat": _fiyat_ayikla(satir.get("avgFiyat")),
            "max_fiyat": _fiyat_ayikla(satir.get("maxFiyat")),
            "kapanis_fiyat": None,
            "miktar": tr_sayi(satir.get("topMiktar")),
            "birim": "KG",
            "ham_veri": satir,
            "cekilme_zamani": simdi_iso(),
        })
    return kayitlar
