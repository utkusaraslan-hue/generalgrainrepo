"""Depo hacim siralamasi + navlun-ayarli arbitraj firsatlari.

Veri: Temmuz+Agustos 2026 gunluk bulten arsivi (gunluk_veri/*.json, Normal Seans).
Konum: il/ilce merkez koordinati (Nominatim, cache'lenir).
Mesafe: kus ucusu x 1.3 duzeltme katsayisi (yol mesafesi tahmini).

Navlun: 9 gercek referans tekliften (7'si NORA Global Logistics fiyatlandirma
arsivinden/skill.md, 2'si Cem Yoluk'un mail zincirinden - Ankara-Izmit ve
Aliaga-ESBAS) lineer regresyonla kalibre edilen SABIT + DEGISKEN maliyet
modeli - TEK bir harmanlanmis TL/ton/km oranina indirgenmiyor, cunku kisa
mesafede sabit maliyet (yukleme/elleçleme) toplamin buyuk kismini olusturuyor
ve bunu gizlemek yaniltici olur. Her hesapta iki bileşen ayri raporlanir:
  TL/sevkiyat = SABIT_MALIYET_TL + DEGISKEN_MALIYET_TL_KM * km
  TL/ton      = TL/sevkiyat / VARSAYILAN_TON_KAPASITESI (27 ton - dorse kapasitesi varsayimi)
"""
import glob
import json
import math
import time
from pathlib import Path

import requests

KOK = Path(__file__).parent
VERI_KOK = Path.home() / "Desktop" / "4-09-2026-turib" / "temmuz-agustos-2026-arsiv"  # agir veri, git disi
YOL_DUZELTME_KATSAYISI = 1.3

# Regresyon (2026-09-04): 7 skill.md referansi + Cem Yoluk'un 2 mail teklifi
# (Ankara-Izmit 30.450 TL / 329km, ve outlier olarak elenen Aliaga-ESBAS).
SABIT_MALIYET_TL = 4416       # TL / sevkiyat (yukleme, elleçleme - mesafeden bagimsiz)
DEGISKEN_MALIYET_TL_KM = 81.79  # TL / km
VARSAYILAN_TON_KAPASITESI = 27   # dorse/kamyon tam yuk varsayimi (bugday icin)

MIN_HACIM_TL = 500_000            # bu esigin altindaki depo/urun ciftleri (dusuk likidite) elenir
MIN_NET_MARJ_TL_TON = 300         # bu esigin altindaki "firsatlar" gurultu sayilir

GEOCODE_CACHE_YOLU = KOK / "il_ilce_koordinat_cache.json"


def tr_sayi(s):
    if s is None or s == "" or s == "-":
        return None
    s = str(s).strip().replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def tum_normal_seans_satirlarini_yukle():
    satirlar = []
    for f in sorted(glob.glob(str(VERI_KOK / "gunluk_veri" / "*.json"))):
        d = json.load(open(f, encoding="utf-8"))
        for s in d["normal_seans"]:
            satirlar.append({
                "tarih": d["tarih"],
                "lidas": s.get("LİDAŞ Adı"),
                "il": s.get("İl"),
                "ilce": s.get("İlçe"),
                "urun": s.get("Enstrüman Sınıfı"),
                "kapanis": tr_sayi(s.get("Kapanış Fiyatı")),
                "ort_fiyat": tr_sayi(s.get("Ağırlıklı Ortalama Fiyat")),
                "miktar_kg": tr_sayi(s.get("İşlem Miktarı [KG]")),
                "hacim_tl": tr_sayi(s.get("İşlem Hacmi [TL]")),
            })
    return satirlar


def il_ilce_koordinatlarini_getir(il_ilce_seti: set[tuple[str, str]]) -> dict:
    cache = {}
    if GEOCODE_CACHE_YOLU.exists():
        cache = json.loads(GEOCODE_CACHE_YOLU.read_text(encoding="utf-8"))

    eksik = [k for k in il_ilce_seti if f"{k[0]}|{k[1]}" not in cache]
    print(f"Geocode: {len(il_ilce_seti)} toplam, {len(eksik)} yeni sorgu gerekiyor")
    for il, ilce in eksik:
        anahtar = f"{il}|{ilce}"
        for sorgu in (f"{ilce}, {il}, Turkey", f"{il}, Turkey"):
            try:
                r = requests.get(
                    "https://nominatim.openstreetmap.org/search",
                    params={"q": sorgu, "format": "json", "limit": 1},
                    headers={"User-Agent": "yine-bi-agent-depo-analiz/1.0 (utkusaraslan@gmail.com)"},
                    timeout=15,
                )
                sonuc = r.json()
            except Exception as e:
                print(f"  HATA {anahtar}: {e}")
                sonuc = []
            if sonuc:
                cache[anahtar] = {"lat": float(sonuc[0]["lat"]), "lon": float(sonuc[0]["lon"]), "sorgu": sorgu}
                print(f"  {anahtar} -> {sonuc[0]['lat']}, {sonuc[0]['lon']} ({sorgu})")
                break
            time.sleep(1.1)  # Nominatim: max 1 istek/sn
        else:
            print(f"  BULUNAMADI: {anahtar}")
            cache[anahtar] = None
        time.sleep(1.1)
        GEOCODE_CACHE_YOLU.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    return cache


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def navlun_breakdown(km: float) -> dict:
    """Navlun maliyetini HER ZAMAN sabit+degisken bilesenlerine ayirarak dondurur -
    tek bir harmanlanmis TL/ton/km rakamina indirgemiyoruz (kullanici tercihi)."""
    sabit_sevkiyat = SABIT_MALIYET_TL
    degisken_sevkiyat = DEGISKEN_MALIYET_TL_KM * km
    toplam_sevkiyat = sabit_sevkiyat + degisken_sevkiyat
    return {
        "km": km,
        "sabit_tl_sevkiyat": sabit_sevkiyat,
        "degisken_tl_sevkiyat": degisken_sevkiyat,
        "toplam_tl_sevkiyat": toplam_sevkiyat,
        "sabit_tl_ton": sabit_sevkiyat / VARSAYILAN_TON_KAPASITESI,
        "degisken_tl_ton": degisken_sevkiyat / VARSAYILAN_TON_KAPASITESI,
        "toplam_tl_ton": toplam_sevkiyat / VARSAYILAN_TON_KAPASITESI,
    }


def main():
    satirlar = tum_normal_seans_satirlarini_yukle()
    print(f"Toplam Normal Seans satiri: {len(satirlar)}")

    il_ilce_seti = {(s["il"], s["ilce"]) for s in satirlar if s["il"] and s["ilce"]}
    koordinatlar = il_ilce_koordinatlarini_getir(il_ilce_seti)

    # --- 1) Depo hacim siralamasi ---
    depo_toplam = {}
    for s in satirlar:
        if not s["lidas"] or s["hacim_tl"] is None:
            continue
        anahtar = (s["lidas"], s["il"], s["ilce"])
        d = depo_toplam.setdefault(anahtar, {"hacim_tl": 0.0, "miktar_kg": 0.0, "islem_sayisi": 0, "urunler": set()})
        d["hacim_tl"] += s["hacim_tl"]
        d["miktar_kg"] += s["miktar_kg"] or 0
        d["islem_sayisi"] += 1
        d["urunler"].add(s["urun"])

    depo_siralama = sorted(depo_toplam.items(), key=lambda kv: -kv[1]["hacim_tl"])
    with open(KOK / "depo_hacim_siralamasi.csv", "w", encoding="utf-8") as f:
        f.write("lidas,il,ilce,toplam_hacim_tl,toplam_miktar_ton,islem_sayisi,urun_cesidi\n")
        for (lidas, il, ilce), d in depo_siralama:
            f.write(f'"{lidas}",{il},{ilce},{d["hacim_tl"]:.0f},{d["miktar_kg"]/1000:.1f},{d["islem_sayisi"]},{len(d["urunler"])}\n')
    print(f"\nEn yuksek hacimli 10 depo:")
    for (lidas, il, ilce), d in depo_siralama[:10]:
        print(f"  {lidas} ({il}/{ilce}): {d['hacim_tl']:,.0f} TL, {d['miktar_kg']/1000:,.1f} ton, {d['islem_sayisi']} islem")

    # --- 2) Urun+depo bazinda agirlikli ortalama fiyat (donem geneli) ---
    urun_depo = {}
    for s in satirlar:
        if not s["lidas"] or s["ort_fiyat"] is None or not s["miktar_kg"]:
            continue
        anahtar = (s["urun"], s["lidas"], s["il"], s["ilce"])
        d = urun_depo.setdefault(anahtar, {"agirlikli_toplam": 0.0, "miktar_kg": 0.0, "hacim_tl": 0.0})
        d["agirlikli_toplam"] += s["ort_fiyat"] * s["miktar_kg"]
        d["miktar_kg"] += s["miktar_kg"]
        d["hacim_tl"] += s["hacim_tl"] or 0

    urun_depo_liste = []
    for (urun, lidas, il, ilce), d in urun_depo.items():
        if d["hacim_tl"] < MIN_HACIM_TL:
            continue  # dusuk likidite - fiyat guvenilir degil
        koor = koordinatlar.get(f"{il}|{ilce}") or koordinatlar.get(f"{il}|None")
        if not koor:
            continue
        urun_depo_liste.append({
            "urun": urun, "lidas": lidas, "il": il, "ilce": ilce,
            "ort_fiyat_tl_ton": d["agirlikli_toplam"] / d["miktar_kg"] * 1000,  # TL/kg -> TL/ton
            "hacim_tl": d["hacim_tl"], "lat": koor["lat"], "lon": koor["lon"],
        })

    # --- 3) Ayni urun icin depo ciftleri arasinda navlun-ayarli arbitraj ---
    firsatlar = []
    from collections import defaultdict
    urune_gore = defaultdict(list)
    for kayit in urun_depo_liste:
        urune_gore[kayit["urun"]].append(kayit)

    for urun, depolar in urune_gore.items():
        for i in range(len(depolar)):
            for j in range(len(depolar)):
                if i == j:
                    continue
                ucuz, pahali = depolar[i], depolar[j]
                if pahali["ort_fiyat_tl_ton"] <= ucuz["ort_fiyat_tl_ton"]:
                    continue
                km = haversine_km(ucuz["lat"], ucuz["lon"], pahali["lat"], pahali["lon"]) * YOL_DUZELTME_KATSAYISI
                navlun = navlun_breakdown(km)
                fiyat_farki = pahali["ort_fiyat_tl_ton"] - ucuz["ort_fiyat_tl_ton"]
                net_marj = fiyat_farki - navlun["toplam_tl_ton"]
                if net_marj >= MIN_NET_MARJ_TL_TON:
                    firsatlar.append({
                        "urun": urun,
                        "al_depo": ucuz["lidas"], "al_yer": f'{ucuz["il"]}/{ucuz["ilce"]}', "al_fiyat": ucuz["ort_fiyat_tl_ton"],
                        "sat_depo": pahali["lidas"], "sat_yer": f'{pahali["il"]}/{pahali["ilce"]}', "sat_fiyat": pahali["ort_fiyat_tl_ton"],
                        "mesafe_km": km,
                        "navlun_sabit_tl_ton": navlun["sabit_tl_ton"],
                        "navlun_degisken_tl_ton": navlun["degisken_tl_ton"],
                        "navlun_toplam_tl_ton": navlun["toplam_tl_ton"],
                        "fiyat_farki_tl_ton": fiyat_farki, "net_marj_tl_ton": net_marj,
                    })

    firsatlar.sort(key=lambda x: -x["net_marj_tl_ton"])
    with open(KOK / "arbitraj_firsatlari.csv", "w", encoding="utf-8") as f:
        f.write("urun,al_depo,al_yer,al_fiyat_tl_ton,sat_depo,sat_yer,sat_fiyat_tl_ton,mesafe_km,"
                 "navlun_sabit_tl_ton,navlun_degisken_tl_ton,navlun_toplam_tl_ton,fiyat_farki_tl_ton,net_marj_tl_ton\n")
        for x in firsatlar:
            f.write(f'"{x["urun"]}","{x["al_depo"]}",{x["al_yer"]},{x["al_fiyat"]:.0f},'
                    f'"{x["sat_depo"]}",{x["sat_yer"]},{x["sat_fiyat"]:.0f},{x["mesafe_km"]:.0f},'
                    f'{x["navlun_sabit_tl_ton"]:.0f},{x["navlun_degisken_tl_ton"]:.0f},{x["navlun_toplam_tl_ton"]:.0f},'
                    f'{x["fiyat_farki_tl_ton"]:.0f},{x["net_marj_tl_ton"]:.0f}\n')

    print(f"\nToplam arbitraj firsati (net marj >= {MIN_NET_MARJ_TL_TON} TL/ton): {len(firsatlar)}")
    print("En iyi 10 firsat (navlun = sabit + degisken breakdown):")
    for x in firsatlar[:10]:
        print(f'  {x["urun"]}: {x["al_depo"]} ({x["al_yer"]}, {x["al_fiyat"]:.0f}) -> '
              f'{x["sat_depo"]} ({x["sat_yer"]}, {x["sat_fiyat"]:.0f}) | {x["mesafe_km"]:.0f}km, '
              f'navlun {x["navlun_sabit_tl_ton"]:.0f}(sabit)+{x["navlun_degisken_tl_ton"]:.0f}(degisken)='
              f'{x["navlun_toplam_tl_ton"]:.0f} | NET {x["net_marj_tl_ton"]:.0f} TL/ton')


if __name__ == "__main__":
    main()
