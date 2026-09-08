"""TURIB gunluk bultenlerini 2023-01-01'den bugune kadar TUM is gunleri icin ceker.

Ayni desen: hafta ici her gun icin POST edilir; Normal Seans + Endeks ikisi de
bossa (resmi tatil / islem yok) o gun atlanir. Kaldigi yerden devam edebilir
(zaten kaydedilmis gunler tekrar cekilmez) - kesinti olursa yeniden calistirmak
guvenli.
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
# Ham veri (agir, gunluk buyuyen) git'e alinmiyor - Masaustunde saklaniyor.
# bkz PROJE_GECMISI.md: "gerekli olmayanlari masaustundeki 4-09-2026-turib
# dosyasina" karari (2026-09-06).
VERI_KOK = Path.home() / "Desktop" / "4-09-2026-turib"
GUNLUK_VERI_DIZINI = VERI_KOK / "gunluk-bulten"
GUNLUK_HAM_DIZINI = VERI_KOK / "gunluk-bulten-ham" / "turib_2023_2026"
GUNLUK_URL = "https://www.turib.com.tr/gunluk-bulten/"
# TURIB Agustos 2019'da kuruldu - kurulusun hemen sonrasindaki gunlerde
# saglikli/eksiksiz veri girilmemis olabilir, bu normal (bkz PROJE_GECMISI.md).
BASLANGIC = date(2019, 8, 1)


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


def _hafta_ici_gunler(baslangic: date, bitis: date) -> list[date]:
    gunler = []
    gun = baslangic
    while gun <= bitis:
        if gun.weekday() < 5:
            gunler.append(gun)
        gun += timedelta(days=1)
    return gunler


def gunluk_cek(gun: date, deneme: int = 3) -> str:
    """Doner: 'kaydedildi' | 'tatil' | 'zaten_var' | 'hata'"""
    GUNLUK_VERI_DIZINI.mkdir(parents=True, exist_ok=True)
    GUNLUK_HAM_DIZINI.mkdir(parents=True, exist_ok=True)
    veri_yolu = GUNLUK_VERI_DIZINI / f"{gun.isoformat()}.json"
    if veri_yolu.exists():
        return "zaten_var"

    for i in range(deneme):
        try:
            r = requests.post(GUNLUK_URL, data={"getbulletin_date": gun.isoformat(), "submit": "Listele"},
                               timeout=30, verify=False, headers=TARAYICI_BASLIKLARI)
            r.raise_for_status()
            break
        except Exception as e:
            if i == deneme - 1:
                print(f"  HATA {gun}: {e}")
                return "hata"
            time.sleep(3 * (i + 1))

    soup = BeautifulSoup(r.text, "html.parser")
    endeks = _tabloyu_oku(soup, "nav-home2")
    normal_seans = _tabloyu_oku(soup, "nav-home")
    anlasmali = _tabloyu_oku(soup, "nav-profile")

    if not normal_seans and not endeks:
        return "tatil"

    (GUNLUK_HAM_DIZINI / f"{gun.isoformat()}.html").write_text(r.text, encoding="utf-8")
    veri_yolu.write_text(
        json.dumps({"tarih": gun.isoformat(), "endeks": endeks,
                    "normal_seans": normal_seans, "anlasmali": anlasmali},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return "kaydedildi"


if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    bugun = date.today()

    # --bugun: gunluk otomasyon (gunluk_ozet_yerel_calistir.sh) icin hizli yol -
    # sadece bugunu cek, 2023'ten itibaren TUM gunleri taramaz.
    if len(sys.argv) > 1 and sys.argv[1] == "--bugun":
        sonuc = gunluk_cek(bugun)
        print(f"{bugun.isoformat()} -> {sonuc}")
        sys.exit(0)

    tum_gunler = _hafta_ici_gunler(BASLANGIC, bugun)
    print(f"{BASLANGIC} - {bugun}: {len(tum_gunler)} hafta ici gun")

    sayaclar = {"kaydedildi": 0, "tatil": 0, "zaten_var": 0, "hata": 0}
    hatali_gunler = []
    for idx, gun in enumerate(tum_gunler, start=1):
        sonuc = gunluk_cek(gun)
        sayaclar[sonuc] += 1
        if sonuc == "hata":
            hatali_gunler.append(gun.isoformat())
        if idx % 25 == 0 or idx == len(tum_gunler):
            print(f"[{idx}/{len(tum_gunler)}] {gun.isoformat()} -> {sonuc} | "
                  f"kaydedildi={sayaclar['kaydedildi']} tatil={sayaclar['tatil']} "
                  f"zaten_var={sayaclar['zaten_var']} hata={sayaclar['hata']}")
        time.sleep(0.4)

    print("\n=== SONUC ===")
    print(sayaclar)
    if hatali_gunler:
        print("Hatali gunler (tekrar calistirilinca otomatik denenir):", hatali_gunler)
