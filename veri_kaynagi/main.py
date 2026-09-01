"""Tum kaynaklari (TMO, TURIB, Konya) calistirip SQLite'a yazan orkestrator.

Varsayilan davranis "bosluk doldurma": her kaynak icin veritabanindaki son
tarihten bugune kadar olan GUNLERI otomatik tamamlar. Boylece Mac kapali/uykuda
oldugu bir gunden sonra calistirildiginda o araya sikisan gunler kaybolmaz.

ONEMLI ISTISNA: TMO'nun bulten URL'i sabit ve TMO tarafinda arsivlenmiyor -
gecmis bir tarih icin PDF istemenin bir anlami yok, o an yayinda olan PDF
gelir. Bu yuzden TMO icin bosluk doldurma yapilmaz, sadece "bugun" cekilir;
gun kacirilirsa o gunun TMO verisi telafi edilemez.

Kullanim:
    python -m veri_kaynagi.main                # bosluk doldur + bugun
    python -m veri_kaynagi.main --tarih 2026-08-31   # sadece belirli bir gun (manuel)
    python -m veri_kaynagi.main --kaynak turib konya  # sadece belirli kaynaklar
"""
import argparse
import sys
import time
from datetime import date, timedelta

import urllib3

from . import db
from .fetchers import konya, tmo, turib

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# backfill_destekler=False olan kaynaklar sadece "bugun" icin cekilir.
KAYNAKLAR = {
    "tmo": {"cek": tmo.cek, "backfill_destekler": False, "kaynak_onek": "TMO"},
    "turib": {"cek": turib.cek, "backfill_destekler": True, "kaynak_onek": "TURIB"},
    "konya": {"cek": konya.cek, "backfill_destekler": True, "kaynak_onek": "KONYA"},
}


def _son_cekilen_tarih(conn, kaynak_onek: str) -> date | None:
    row = conn.execute(
        "SELECT MAX(tarih) FROM fiyatlar WHERE kaynak LIKE ?", (f"{kaynak_onek}%",)
    ).fetchone()
    return date.fromisoformat(row[0]) if row and row[0] else None


def _tarih_araligi_getir_ve_kaydet(conn, ad: str, info: dict, gun: date, deneme: int = 3) -> bool:
    """Basarili olursa True doner. Gecici ag hatalarina (timeout vb.) karsi
    birkac kez dener; hepsi basarisiz olursa False doner (caller job'i
    basarisiz isaretleyip GitHub'in bildirim gondermesini saglar)."""
    for i in range(1, deneme + 1):
        print(f"[{ad}] {gun.isoformat()} cekiliyor... (deneme {i}/{deneme})", file=sys.stderr)
        try:
            kayitlar = info["cek"](gun.isoformat())
        except Exception as e:
            print(f"[{ad}] {gun.isoformat()} HATA: {e}", file=sys.stderr)
            if i < deneme:
                time.sleep(5 * i)
            continue
        n = db.upsert_kayitlar(conn, kayitlar)
        print(f"[{ad}] {gun.isoformat()}: {n} kayit yazildi/guncellendi", file=sys.stderr)
        return True
    return False


def calistir(tarih: str | None, sadece: list[str] | None = None) -> bool:
    """Belirli TEK bir tarih icin calistirir (manuel kullanim / cron'un kendisi).
    Hepsi basarili olursa True doner."""
    conn = db.get_connection()
    hedefler = sadece or list(KAYNAKLAR.keys())
    gun = date.fromisoformat(tarih) if tarih else date.today()
    hepsi_basarili = True
    for ad in hedefler:
        if not _tarih_araligi_getir_ve_kaydet(conn, ad, KAYNAKLAR[ad], gun):
            hepsi_basarili = False
    conn.close()
    return hepsi_basarili


def bosluk_doldurarak_calistir(sadece: list[str] | None = None, azami_gun: int = 60) -> bool:
    """Varsayilan mod: her kaynagin veritabanindaki son gununden bugune kadar
    eksik gunleri otomatik tamamlar. azami_gun: bir kaynak hic hic calismamissa
    (ilk kurulum) sonsuz geriye gitmesin diye guvenlik siniri (varsayilan devre disi,
    ilk calistirmada zaten sadece 'bugun' baz alinir). Hepsi basarili olursa True doner."""
    conn = db.get_connection()
    bugun = date.today()
    hedefler = sadece or list(KAYNAKLAR.keys())
    hepsi_basarili = True
    for ad in hedefler:
        info = KAYNAKLAR[ad]
        if not info["backfill_destekler"]:
            if not _tarih_araligi_getir_ve_kaydet(conn, ad, info, bugun):
                hepsi_basarili = False
            continue
        son = _son_cekilen_tarih(conn, info["kaynak_onek"])
        baslangic = (son + timedelta(days=1)) if son else bugun
        if baslangic > bugun:
            print(f"[{ad}] zaten guncel (son: {son})", file=sys.stderr)
            continue
        gunler = [baslangic + timedelta(days=i) for i in range((bugun - baslangic).days + 1)]
        gunler = gunler[-azami_gun:]
        for gun in gunler:
            if not _tarih_araligi_getir_ve_kaydet(conn, ad, info, gun):
                hepsi_basarili = False
            time.sleep(0.5)  # kaynak sunucusunu yormamak icin
    conn.close()
    return hepsi_basarili


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tarih", default=None,
                         help="Sadece bu tek tarihi cek (verilmezse bosluk-doldurma modu calisir)")
    parser.add_argument("--kaynak", nargs="*", choices=list(KAYNAKLAR.keys()),
                         help="Sadece belirtilen kaynaklari calistir")
    args = parser.parse_args()

    basarili = calistir(args.tarih, args.kaynak) if args.tarih else bosluk_doldurarak_calistir(args.kaynak)
    if not basarili:
        # En az bir kaynak (birkac deneme sonunda) basarisiz oldu. Diger
        # kaynaklarin verisi zaten yazildi/commit'lenecek; burada job'i
        # basarisiz isaretliyoruz ki GitHub bildirim gondersin, sessizce
        # kaybolmasin.
        print("UYARI: en az bir kaynak basarisiz oldu, yukarisi loglara bakin", file=sys.stderr)
        sys.exit(1)
