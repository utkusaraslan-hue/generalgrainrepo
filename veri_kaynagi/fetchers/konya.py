"""Konya Ticaret Borsasi (KTB) - Alpata altyapili API'den anlik gunluk bulten.

Sitenin Angular SPA'sinin JS bundle'indan cikarilan endpoint, kimlik dogrulama
gerektirmiyor.
"""
from datetime import date

import requests

from ..utils import TARAYICI_BASLIKLARI, simdi_iso, tr_sayi

API_URL = "https://www.ktb.org.tr/api/v1/Alpha.WebPanel/OnlineKullaniciBulten/GetAnlikBulten/{tarih}"


def cek(tarih: str | None = None) -> list[dict]:
    tarih = tarih or date.today().isoformat()
    r = requests.get(API_URL.format(tarih=tarih), timeout=30, verify=False, headers=TARAYICI_BASLIKLARI)
    r.raise_for_status()
    veri = r.json()

    kayitlar = []
    for i, satir in enumerate(veri):
        detay = f"{satir.get('SinifAdi')}#{i}"
        kayitlar.append({
            "kaynak": "KONYA",
            "tarih": tarih,
            "il": "Konya",
            "ilce": None,
            "urun": satir.get("GrupAdi"),
            "detay": detay,
            "min_fiyat": tr_sayi(satir.get("MinFiyat")),
            "ort_fiyat": tr_sayi(satir.get("OrtFiyat")),
            "max_fiyat": tr_sayi(satir.get("MaxFiyat")),
            "kapanis_fiyat": None,
            "miktar": tr_sayi(satir.get("Miktar")),
            "birim": "TL/ton",
            "ham_veri": satir,
            "cekilme_zamani": simdi_iso(),
        })
    return kayitlar
