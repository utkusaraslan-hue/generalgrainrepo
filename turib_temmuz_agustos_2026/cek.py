"""Bir kerelik arsiv: TURIB'in Temmuz+Agustos 2026 tum is gunleri gunluk
bultenleri + 2 aylik bulteni (Temmuz, Agustos 2026).

Her hafta ici gun icin gunluk bulten cekilir; Normal Seans tablosu bossa
(resmi tatil) o gun atlanir - "is gunu" sayisi boylece TURIB'in kendi
takviminden dogrulanmis olur, tahmin edilmez.

Her gun/ay icin iki dosya kaydedilir:
  - *_ham/*.html   : sunucudan gelen ham HTML (kanit/kaynak)
  - *_veri/*.json  : parse edilmis tablo verisi (ileride kullanmak icin)
"""
import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from veri_kaynagi.utils import TARAYICI_BASLIKLARI  # noqa: E402

KOK = Path(__file__).parent
# Agir veri git'e alinmiyor - Masaustunde saklaniyor (bkz PROJE_GECMISI.md).
VERI_KOK = Path.home() / "Desktop" / "4-09-2026-turib" / "temmuz-agustos-2026-arsiv"
GUNLUK_URL = "https://www.turib.com.tr/gunluk-bulten/"
AYLIK_URL = "https://www.turib.com.tr/aylik-bulten/"


def _tabloyu_oku(soup: BeautifulSoup, panel_id: str) -> list[dict]:
    panel = soup.find(id=panel_id)
    if not panel:
        return []
    tablo = panel.find("table")
    if not tablo or not tablo.find("thead") or not tablo.find("tbody"):
        return []
    basliklar = [th.get_text(strip=True) for th in tablo.find("thead").find_all("th")]
    hucreler = [td.get_text(strip=True) for td in tablo.find("tbody").find_all("td")]
    n = len(basliklar)
    if n == 0:
        return []
    return [dict(zip(basliklar, hucreler[i:i + n])) for i in range(0, len(hucreler) - n + 1, n)]


def _is_gunleri(yil: int, ay: int) -> list[date]:
    gun = date(yil, ay, 1)
    sonraki_ay = date(yil, ay + 1, 1) if ay < 12 else date(yil + 1, 1, 1)
    gunler = []
    while gun < sonraki_ay:
        if gun.weekday() < 5:  # 0=Pazartesi ... 4=Cuma
            gunler.append(gun)
        gun += timedelta(days=1)
    return gunler


def gunluk_cek(gun: date) -> bool:
    """True: gercek islem gunuydu ve kaydedildi. False: bos donen (tatil), atlandi."""
    r = requests.post(GUNLUK_URL, data={"getbulletin_date": gun.isoformat(), "submit": "Listele"},
                       timeout=30, verify=False, headers=TARAYICI_BASLIKLARI)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    endeks = _tabloyu_oku(soup, "nav-home2")
    normal_seans = _tabloyu_oku(soup, "nav-home")
    anlasmali = _tabloyu_oku(soup, "nav-profile")

    if not normal_seans and not endeks:
        return False  # resmi tatil / islem yok

    (VERI_KOK / "gunluk_ham" / f"{gun.isoformat()}.html").write_text(r.text, encoding="utf-8")
    (VERI_KOK / "gunluk_veri" / f"{gun.isoformat()}.json").write_text(
        json.dumps({"tarih": gun.isoformat(), "endeks": endeks,
                    "normal_seans": normal_seans, "anlasmali": anlasmali},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return True


def aylik_cek(yil: int, ay: int) -> None:
    r = requests.post(AYLIK_URL, data={"getbulletinmonthly_month": ay,
                                        "getbulletinmonthly_year": yil, "submit": "Listele"},
                       timeout=30, verify=False, headers=TARAYICI_BASLIKLARI)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    normal_seans = _tabloyu_oku(soup, "nav-home")
    anlasmali = _tabloyu_oku(soup, "nav-profile")

    etiket = f"{yil}-{ay:02d}"
    (VERI_KOK / "aylik_ham" / f"{etiket}.html").write_text(r.text, encoding="utf-8")
    (VERI_KOK / "aylik_veri" / f"{etiket}.json").write_text(
        json.dumps({"yil": yil, "ay": ay, "normal_seans": normal_seans, "anlasmali": anlasmali},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[aylik] {etiket}: normal_seans={len(normal_seans)} anlasmali={len(anlasmali)} satir")


if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    tum_hafta_ici = _is_gunleri(2026, 7) + _is_gunleri(2026, 8)
    print(f"Temmuz+Agustos 2026 hafta ici gun sayisi: {len(tum_hafta_ici)}")

    kaydedilen = []
    atlanan = []
    for gun in tum_hafta_ici:
        basarili = gunluk_cek(gun)
        if basarili:
            kaydedilen.append(gun)
            print(f"[gunluk] {gun.isoformat()}: kaydedildi")
        else:
            atlanan.append(gun)
            print(f"[gunluk] {gun.isoformat()}: BOS (resmi tatil, atlandi)")
        time.sleep(0.4)

    print(f"\nToplam hafta ici gun: {len(tum_hafta_ici)}")
    print(f"Gercek is gunu (kaydedilen): {len(kaydedilen)}")
    print(f"Tatil/bos (atlanan): {len(atlanan)} -> {[g.isoformat() for g in atlanan]}")

    aylik_cek(2026, 7)
    aylik_cek(2026, 8)
