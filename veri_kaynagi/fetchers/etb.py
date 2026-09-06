"""Edirne Ticaret Borsasi (ETB) - Konya ile ayni "Alpata" altyapili Angular SPA
(online.etb.org.tr), kimlik dogrulama gerektirmeyen tek public endpoint
GetOnlineGunlukKartlarGrup.

ONEMLI KISIT: Konya'nin GetAnlikBulten'inin aksine bu endpoint tarih parametresini
YOK SAYIYOR - Tarih=... query string'i denenmis, hep "bugunku/en guncel" veriyi
donduruyor (dogrulama: farkli tarihlerle ayni IslemTarih donuyor). Yani backfill
YOK, TMO gibi sadece "su an" cekilebilir. Ayrica veri sinif bazinda degil GRUP
bazinda (orn. "KIRMIZI EKMEKLIK BUGDAYLAR"), TURIB'deki gibi ISIN/sinif detayi yok.
"""
from datetime import date

import requests

from ..utils import TARAYICI_BASLIKLARI, simdi_iso, tr_sayi

API_URL = "https://online.etb.org.tr/api/v1/Alpha.WebPanel/OnlineKullaniciBulten/GetOnlineGunlukKartlarGrup"


def cek(tarih: str | None = None) -> list[dict]:
    # tarih parametresi kayit icin kullanilir; API'nin kendisi yok sayiyor,
    # gercek tarih asagida her satirin kendi IslemTarih alanindan alinir.
    istenen_tarih = tarih or date.today().isoformat()

    r = requests.get(API_URL, timeout=30, verify=False, headers=TARAYICI_BASLIKLARI)
    r.raise_for_status()
    veri = r.json()

    kayitlar = []
    for satir in veri:
        islem_tarih = satir.get("IslemTarih")
        gercek_tarih = islem_tarih[:10] if islem_tarih else istenen_tarih
        kayitlar.append({
            "kaynak": "ETB",
            "tarih": gercek_tarih,
            "il": "Edirne",
            "ilce": None,
            "urun": satir.get("GrupAdi"),
            "detay": f"{satir.get('UstUrunGrubu')}#{satir.get('GrupKodu')}",
            "min_fiyat": tr_sayi(satir.get("MinFiyat")),
            "ort_fiyat": tr_sayi(satir.get("OrtFiyat")),
            "max_fiyat": tr_sayi(satir.get("MaxFiyat")),
            "kapanis_fiyat": None,
            "miktar": tr_sayi(satir.get("SatilanMiktar")),
            "birim": "KG",
            "ham_veri": satir,
            "cekilme_zamani": simdi_iso(),
        })
    return kayitlar
