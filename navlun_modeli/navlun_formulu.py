"""
Genel ic nakliye (navlun) maliyet formulu - km VE ton hassasiyetli.

Her zaman SABIT + DEGISKEN olarak ayri raporlanir, tek bir harmanlanmis
TL/ton/km rakamina indirgenmez (proje kurali).

VERI KAYNAKLARI (3 farkli yuk olcegi, 3 ayri kalibrasyon):

1) PARSIYEL / LCL (0-2 ton) - ~/Desktop/agents/skill.md (NORA Global,
   truck_pricing.rtfd arsivi, n~=9 gercek teklif). Adanmis kucuk arac/kamyonet,
   agirlik etkisi bu bantta ihmal edilebilir, fiyat mesafeye bagli.
   Referans: Ambarli->Gebze 55km 3.500TL, Ambarli->Arnavutkoy 30km 4.500-5.500TL,
   Ambarli->Bagcilar 35km 8.450TL, Mersin->Adana 210km 6.000TL,
   Ambarli->Kayseri SB 700km 1195kg teminatli arac 55.000TL (bu son nokta
   teminatli arac primi nedeniyle olagan K katsayisina dahil edilmedi).

2) TAM YUK / DORSE (20-27 ton, dokme hububat) - 9 referans (7'si NORA
   skill.md'deki konteyner/liman drenaj tekliflerinden, 2'si Cem Yoluk'un
   (NORA Global, cem.yoluk@noraglobal.com) 2026 mail zincirinden: Ankara/
   Sincan->Izmit Korfezi 30.450 TL, ve Aliaga Limani->ESBAS 19.500 TL - bu
   ikincisi teminatli arac primi nedeniyle regresyondan cikarildi).
   Lineer regresyon: SABIT_TL=4.416, DEGISKEN_TL_KM=81,79
   (bkz. ~/yine-bi-agent/turib_temmuz_agustos_2026/depo_analiz.py)

3) ORTA OLCEK / KISMI DORSE (2-20 ton) - DOGRUDAN GERCEK VERI YOK.
   Bant-1 ile Bant-2 arasinda tonaja gore DOGRUSAL INTERPOLASYON ile
   tahmin edilir. Bu bant icin sonuclar "kaba tahmin" olarak isaretlenmelidir,
   gercek teklif toplandikca guncellenmelidir.

Kullanim:
    from navlun_formulu import navlun_hesapla
    navlun_hesapla(km=150, ton=27)
    -> {"km":150, "ton":27, "yuk_bandi":"tam_yuk", "guven":"gercek_veri",
        "sabit_tl_sevkiyat":4416, "degisken_tl_sevkiyat":12268, "toplam_tl_sevkiyat":16684,
        "sabit_tl_ton":163.6, "degisken_tl_ton":454.4, "toplam_tl_ton":618.1}
"""

from __future__ import annotations

# --- Bant 1: Parsiyel/LCL (<=2 ton) ---
LCL_SABIT_TL = 4000.0  # skill.md'de kisa mesafede gozlenen 4.000-8.500 TL taban araligin ortasi


def _lcl_degisken_katsayi(km: float) -> float:
    """K (TL/km), skill.md'deki 3 km bandina gore."""
    if km <= 100:
        return 95.0
    if km <= 250:
        return 65.0
    return 52.0


# --- Bant 2: Tam yuk / Dorse (20-27 ton, dokme hububat) ---
FTL_SABIT_TL = 4416.0
FTL_DEGISKEN_TL_KM = 81.79

# Interpolasyon sinirlari (ton)
LCL_UST_SINIR_TON = 2.0
FTL_ALT_SINIR_TON = 20.0
FTL_UST_SINIR_TON = 27.0  # dorse tam kapasite varsayimi (bugday)


def navlun_hesapla(km: float, ton: float) -> dict:
    """Navlun maliyetini km VE ton'a duyarli sekilde, HER ZAMAN sabit+degisken
    ayri olarak dondurur. `guven` alani veri kalitesini belirtir:
    'gercek_veri' (Bant 1 veya Bant 2) / 'interpolasyon' (Bant 3, tahmini)."""
    if ton <= 0:
        raise ValueError("ton > 0 olmali")

    lcl_k = _lcl_degisken_katsayi(km)

    if ton <= LCL_UST_SINIR_TON:
        yuk_bandi = "parsiyel_lcl"
        guven = "gercek_veri"
        sabit_sevkiyat = LCL_SABIT_TL
        degisken_katsayi = lcl_k
    elif ton >= FTL_ALT_SINIR_TON:
        yuk_bandi = "tam_yuk"
        guven = "gercek_veri"
        sabit_sevkiyat = FTL_SABIT_TL
        degisken_katsayi = FTL_DEGISKEN_TL_KM
    else:
        yuk_bandi = "orta_olcek_kismi_yuk"
        guven = "interpolasyon"
        oran = (ton - LCL_UST_SINIR_TON) / (FTL_ALT_SINIR_TON - LCL_UST_SINIR_TON)
        sabit_sevkiyat = LCL_SABIT_TL + oran * (FTL_SABIT_TL - LCL_SABIT_TL)
        degisken_katsayi = lcl_k + oran * (FTL_DEGISKEN_TL_KM - lcl_k)

    degisken_sevkiyat = degisken_katsayi * km
    toplam_sevkiyat = sabit_sevkiyat + degisken_sevkiyat

    # ton > 27 ise: birden fazla dorse gerekir, tam-yuk maliyetini kac araca
    # bolunecegine gore olceklendir (asagi yuvarlama yok, taban maliyet garanti)
    arac_sayisi = 1.0
    if ton > FTL_UST_SINIR_TON:
        import math
        arac_sayisi = math.ceil(ton / FTL_UST_SINIR_TON)
        sabit_sevkiyat *= arac_sayisi
        degisken_sevkiyat *= arac_sayisi
        toplam_sevkiyat = sabit_sevkiyat + degisken_sevkiyat

    return {
        "km": km,
        "ton": ton,
        "yuk_bandi": yuk_bandi,
        "guven": guven,
        "arac_sayisi": arac_sayisi,
        "sabit_tl_sevkiyat": round(sabit_sevkiyat, 0),
        "degisken_tl_sevkiyat": round(degisken_sevkiyat, 0),
        "toplam_tl_sevkiyat": round(toplam_sevkiyat, 0),
        "sabit_tl_ton": round(sabit_sevkiyat / ton, 1),
        "degisken_tl_ton": round(degisken_sevkiyat / ton, 1),
        "toplam_tl_ton": round(toplam_sevkiyat / ton, 1),
    }


if __name__ == "__main__":
    for km in (25, 55, 100, 150, 210, 300, 500):
        for ton in (0.5, 1, 2, 5, 10, 15, 20, 27, 40):
            r = navlun_hesapla(km, ton)
            print(f'{km:>4}km {ton:>5}ton [{r["yuk_bandi"]:<22} {r["guven"]:<12}] '
                  f'sabit={r["sabit_tl_sevkiyat"]:>8.0f} degisken={r["degisken_tl_sevkiyat"]:>8.0f} '
                  f'toplam={r["toplam_tl_sevkiyat"]:>9.0f} TL  ({r["toplam_tl_ton"]:>7.1f} TL/ton)')
