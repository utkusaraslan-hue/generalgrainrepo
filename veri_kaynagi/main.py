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


def _tarih_araligi_getir_ve_kaydet(conn, ad: str, info: dict, gun: date) -> None:
    print(f"[{ad}] {gun.isoformat()} cekiliyor...", file=sys.stderr)
    try:
        kayitlar = info["cek"](gun.isoformat())
    except Exception as e:
        print(f"[{ad}] {gun.isoformat()} HATA: {e}", file=sys.stderr)
        return
    n = db.upsert_kayitlar(conn, kayitlar)
    print(f"[{ad}] {gun.isoformat()}: {n} kayit yazildi/guncellendi", file=sys.stderr)


def calistir(tarih: str | None, sadece: list[str] | None = None) -> None:
    """Belirli TEK bir tarih icin calistirir (manuel kullanim / cron'un kendisi)."""
    conn = db.get_connection()
    hedefler = sadece or list(KAYNAKLAR.keys())
    gun = date.fromisoformat(tarih) if tarih else date.today()
    for ad in hedefler:
        _tarih_araligi_getir_ve_kaydet(conn, ad, KAYNAKLAR[ad], gun)
    conn.close()


def bosluk_doldurarak_calistir(sadece: list[str] | None = None, azami_gun: int = 60) -> None:
    """Varsayilan mod: her kaynagin veritabanindaki son gununden bugune kadar
    eksik gunleri otomatik tamamlar. azami_gun: bir kaynak hic hic calismamissa
    (ilk kurulum) sonsuz geriye gitmesin diye guvenlik siniri (varsayilan devre disi,
    ilk calistirmada zaten sadece 'bugun' baz alinir)."""
    conn = db.get_connection()
    bugun = date.today()
    hedefler = sadece or list(KAYNAKLAR.keys())
    for ad in hedefler:
        info = KAYNAKLAR[ad]
        if not info["backfill_destekler"]:
            _tarih_araligi_getir_ve_kaydet(conn, ad, info, bugun)
            continue
        son = _son_cekilen_tarih(conn, info["kaynak_onek"])
        baslangic = (son + timedelta(days=1)) if son else bugun
        if baslangic > bugun:
            print(f"[{ad}] zaten guncel (son: {son})", file=sys.stderr)
            continue
        gunler = [baslangic + timedelta(days=i) for i in range((bugun - baslangic).days + 1)]
        gunler = gunler[-azami_gun:]
        for gun in gunler:
            _tarih_araligi_getir_ve_kaydet(conn, ad, info, gun)
            time.sleep(0.5)  # kaynak sunucusunu yormamak icin
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tarih", default=None,
                         help="Sadece bu tek tarihi cek (verilmezse bosluk-doldurma modu calisir)")
    parser.add_argument("--kaynak", nargs="*", choices=list(KAYNAKLAR.keys()),
                         help="Sadece belirtilen kaynaklari calistir")
    args = parser.parse_args()

    if args.tarih:
        calistir(args.tarih, args.kaynak)
    else:
        bosluk_doldurarak_calistir(args.kaynak)
