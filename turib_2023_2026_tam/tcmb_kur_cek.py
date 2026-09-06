"""TCMB'nin ucretsiz gunluk kur XML'inden (API key gerektirmez) her is gunu
icin USD Doviz Satis kurunu ceker ve yerel cache'e (usd_kur_cache.json) yazar.

Kaynak: https://www.tcmb.gov.tr/kurlar/{YYYYMM}/{DDMMYYYY}.xml
Kullanilan alan: Currency[Kod=USD]/ForexSelling (Efektif degil, Doviz Satis -
muhasebe/raporlamada standart kullanilan kur).

TCMB hafta sonu/resmi tatil gunlerinde XML yayinlamiyor - o gun icin bir onceki
YAYINLANMIS is gununun kuru kullanilir (standart pratik, kur "o günkü son
bilinen deger" olarak donuyor).
"""
import glob
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from xml.etree import ElementTree

import requests

KOK = Path(__file__).parent
GUNLUK_VERI_DIZINI = Path.home() / "Desktop" / "4-09-2026-turib" / "gunluk-bulten"  # agir veri, git disi (bkz PROJE_GECMISI.md)
CACHE_DOSYA = KOK / "usd_kur_cache.json"
BASLIKLAR = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}


def cache_yukle() -> dict:
    if CACHE_DOSYA.exists():
        return json.loads(CACHE_DOSYA.read_text(encoding="utf-8"))
    return {}


def cache_kaydet(cache: dict):
    CACHE_DOSYA.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def tcmb_xml_ceker(tarih: datetime) -> float | None:
    """Verilen tarih icin TCMB XML'ini ceker, USD ForexSelling degerini dondurur.
    Yayinlanmamissa (haftasonu/tatil) None doner."""
    yyyymm = tarih.strftime("%Y%m")
    ddmmyyyy = tarih.strftime("%d%m%Y")
    url = f"https://www.tcmb.gov.tr/kurlar/{yyyymm}/{ddmmyyyy}.xml"
    try:
        r = requests.get(url, headers=BASLIKLAR, timeout=15)
        if r.status_code != 200:
            return None
        root = ElementTree.fromstring(r.content)
        for currency in root.findall("Currency"):
            if currency.get("Kod") == "USD":
                deger = currency.find("ForexSelling").text
                return float(deger.replace(",", "."))
    except Exception:
        return None
    return None


def kur_bul(tarih_iso: str, cache: dict) -> tuple[float, str]:
    """tarih_iso: 'YYYY-MM-DD'. Cache'te varsa direkt doner. Yoksa TCMB'den
    ceker; yayinlanmamissa geriye dogru en fazla 10 gun arar (tatil zinciri).
    Doner: (kur, kullanilan_gercek_tarih_iso)"""
    if tarih_iso in cache:
        return cache[tarih_iso]["kur"], cache[tarih_iso]["kullanilan_tarih"]

    tarih = datetime.strptime(tarih_iso, "%Y-%m-%d")
    for geri in range(0, 11):
        deneme_tarihi = tarih - timedelta(days=geri)
        kur = tcmb_xml_ceker(deneme_tarihi)
        if kur is not None:
            cache[tarih_iso] = {"kur": kur, "kullanilan_tarih": deneme_tarihi.strftime("%Y-%m-%d")}
            return kur, deneme_tarihi.strftime("%Y-%m-%d")
        time.sleep(0.1)
    raise RuntimeError(f"{tarih_iso} icin 10 gun geriye gidildi, TCMB kuru bulunamadi")


def main():
    cache = cache_yukle()
    dosyalar = sorted(glob.glob(str(GUNLUK_VERI_DIZINI / "*.json")))
    tarihler = [Path(f).stem for f in dosyalar]  # YYYY-MM-DD
    print(f"{len(tarihler)} tarih icin USD kuru cekilecek (cache'te {len(cache)} tane var)")

    yeni = 0
    for i, t in enumerate(tarihler, 1):
        if t not in cache:
            kur, kullanilan = kur_bul(t, cache)
            yeni += 1
            if kullanilan != t:
                print(f"  [{i}/{len(tarihler)}] {t}: TCMB'de yok, {kullanilan} kuru kullanildi ({kur})")
            if yeni % 25 == 0:
                cache_kaydet(cache)  # periyodik kaydet, kesinti olursa kaybolmasin
                print(f"[{i}/{len(tarihler)}] islendi, ara kaydedildi")
            time.sleep(0.05)

    cache_kaydet(cache)
    print(f"\nToplam: {len(tarihler)} tarih, yeni cekilen: {yeni}, cache: {CACHE_DOSYA}")


if __name__ == "__main__":
    main()
