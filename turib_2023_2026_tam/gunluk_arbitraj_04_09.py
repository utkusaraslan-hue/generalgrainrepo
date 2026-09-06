"""04.09.2026 gunune ozel: depolar arasi navlun-ayarli arbitraj firsatlari.

Ayni mantik: depo_analiz.py (temmuz_agustos), ama tek gunluk bulten uzerinde.
Navlun: navlun_modeli/navlun_formulu.py (km+ton hassasiyetli, 27 ton dorse
varsayimiyla FTL bandi = depo_analiz.py'deki 4416+81,79*km modeliyle ayni).
"""
import json
import math
import sys
import time
from pathlib import Path

import requests

KOK = Path(__file__).parent
GUNLUK_VERI_DIZINI = Path.home() / "Desktop" / "4-09-2026-turib" / "gunluk-bulten"  # agir veri, git disi (bkz PROJE_GECMISI.md)
sys.path.insert(0, str(KOK.parent / "navlun_modeli"))
from navlun_formulu import navlun_hesapla  # noqa: E402

YOL_DUZELTME_KATSAYISI = 1.3
VARSAYILAN_TON = 27  # dorse tam yuk (bu urun grubu icin - hububat)
MIN_NET_MARJ_TL_TON = 0  # tek gun oldugu icin esik dusuk tutuldu, hepsini gorelim

GEOCODE_CACHE_YOLU = KOK.parent / "turib_temmuz_agustos_2026" / "il_ilce_koordinat_cache.json"


def tr_sayi(s):
    if s is None or s == "" or s == "-":
        return None
    s = str(s).strip().replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def geocode(il_ilce_seti):
    cache = json.loads(GEOCODE_CACHE_YOLU.read_text(encoding="utf-8")) if GEOCODE_CACHE_YOLU.exists() else {}
    eksik = [k for k in il_ilce_seti if f"{k[0]}|{k[1]}" not in cache]
    print(f"Geocode: {len(il_ilce_seti)} lokasyon, {len(eksik)} yeni sorgu")
    for il, ilce in eksik:
        anahtar = f"{il}|{ilce}"
        for sorgu in (f"{ilce}, {il}, Turkey", f"{il}, Turkey"):
            try:
                r = requests.get("https://nominatim.openstreetmap.org/search",
                                  params={"q": sorgu, "format": "json", "limit": 1},
                                  headers={"User-Agent": "yine-bi-agent-depo-analiz/1.0 (utkusaraslan@gmail.com)"},
                                  timeout=15)
                sonuc = r.json()
            except Exception as e:
                print(f"  HATA {anahtar}: {e}")
                sonuc = []
            if sonuc:
                cache[anahtar] = {"lat": float(sonuc[0]["lat"]), "lon": float(sonuc[0]["lon"]), "sorgu": sorgu}
                print(f"  {anahtar} -> {sonuc[0]['lat']},{sonuc[0]['lon']}")
                break
            time.sleep(1.1)
        else:
            print(f"  BULUNAMADI: {anahtar}")
            cache[anahtar] = None
        time.sleep(1.1)
        GEOCODE_CACHE_YOLU.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    return cache


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def main():
    d = json.load(open(GUNLUK_VERI_DIZINI / "2026-09-04.json", encoding="utf-8"))
    satirlar = []
    for s in d["normal_seans"]:
        satirlar.append({
            "lidas": s.get("LİDAŞ Adı"), "il": s.get("İl"), "ilce": s.get("İlçe"),
            "urun": s.get("Enstrüman Sınıfı"),
            "ort_fiyat_tl_kg": tr_sayi(s.get("Ağırlıklı Ortalama Fiyat")),
            "miktar_kg": tr_sayi(s.get("İşlem Miktarı [KG]")),
            "hacim_tl": tr_sayi(s.get("İşlem Hacmi [TL]")),
            "isin": s.get("ISIN Kodu"),
        })

    print(f"04.09.2026 Normal Seans: {len(satirlar)} işlem")
    for s in satirlar:
        print(f"  {s['urun']:<45} {s['il']}/{s['ilce']:<12} {s['ort_fiyat_tl_kg']:.2f} TL/kg "
              f"x {s['miktar_kg']:>10,.0f} kg  ({s['lidas']})")

    lokasyonlar = {(s["il"], s["ilce"]) for s in satirlar}
    cache = geocode(lokasyonlar)

    from collections import defaultdict
    urune_gore = defaultdict(list)
    for s in satirlar:
        anahtar = f"{s['il']}|{s['ilce']}"
        koord = cache.get(anahtar)
        if not koord:
            continue
        s["lat"], s["lon"] = koord["lat"], koord["lon"]
        s["fiyat_tl_ton"] = s["ort_fiyat_tl_kg"] * 1000
        urune_gore[s["urun"]].append(s)

    print("\n=== ARBİTRAJ FIRSATLARI (aynı ürün, farklı depo, navlun düşülmüş) ===")
    firsatlar = []
    for urun, kayitlar in urune_gore.items():
        if len(kayitlar) < 2:
            continue
        for i, ucuz in enumerate(kayitlar):
            for pahali in kayitlar:
                if ucuz is pahali or ucuz["fiyat_tl_ton"] >= pahali["fiyat_tl_ton"]:
                    continue
                km = haversine_km(ucuz["lat"], ucuz["lon"], pahali["lat"], pahali["lon"]) * YOL_DUZELTME_KATSAYISI
                nav = navlun_hesapla(km, VARSAYILAN_TON)
                fiyat_farki = pahali["fiyat_tl_ton"] - ucuz["fiyat_tl_ton"]
                net_marj = fiyat_farki - nav["toplam_tl_ton"]
                firsatlar.append({
                    "urun": urun,
                    "al_depo": ucuz["lidas"], "al_yer": f"{ucuz['il']}/{ucuz['ilce']}", "al_fiyat": ucuz["fiyat_tl_ton"],
                    "sat_depo": pahali["lidas"], "sat_yer": f"{pahali['il']}/{pahali['ilce']}", "sat_fiyat": pahali["fiyat_tl_ton"],
                    "km": km, "navlun_sabit": nav["sabit_tl_ton"], "navlun_degisken": nav["degisken_tl_ton"],
                    "navlun_toplam": nav["toplam_tl_ton"], "fiyat_farki": fiyat_farki, "net_marj": net_marj,
                })

    firsatlar.sort(key=lambda x: -x["net_marj"])
    for f in firsatlar:
        print(f'{f["urun"]}: {f["al_yer"]} ({f["al_fiyat"]:.0f}) -> {f["sat_yer"]} ({f["sat_fiyat"]:.0f}) | '
              f'{f["km"]:.0f}km, navlun {f["navlun_sabit"]:.0f}+{f["navlun_degisken"]:.0f}={f["navlun_toplam"]:.0f} | '
              f'fark {f["fiyat_farki"]:.0f} | NET {f["net_marj"]:.0f} TL/ton')

    (KOK / "arbitraj_04_09_2026.json").write_text(
        json.dumps({"satirlar": satirlar, "firsatlar": firsatlar}, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8")
    print(f"\n{len(firsatlar)} firsat/cift bulundu -> arbitraj_04_09_2026.json'a yazildi")


if __name__ == "__main__":
    main()
