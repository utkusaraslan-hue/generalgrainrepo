"""2023-2026 TURIB gunluk_veri JSON'larindaki eski format satirlarinda (2023'ten
2026 baslarina kadar) 'Il'/'Ilce'/'LIDAS Adi' alanlari hic yok - sadece
'Islem Kodu' var. Bu script Islem Kodu'ndan depo kodunu cikarip
depo_isin_kod_listesi.csv (turib_site_incelemesi/) ile eslestirerek eksik
alanlari DOLDURUR, mevcut alanlari asla EZMEZ.

Islem Kodu formati (hep 9 parca, '_' ile ayrik):
    E_{urun_kodu}_MN_{tip}_{il_kisa}_{ilce_kisa}_{depo_kodu}_{yil}_{ISIN}
orn: E_TURHBTARPARPSN1_MN_IAB_KYS_TLS_RUT_2022_TRXRUTA12212
     -> depo_kodu=RUT -> depo_isin_kod_listesi.csv'de RUT=KAYSERI/MERKEZ

depo_kodu'nun COGU (348'de 337) tek bir il/ilceye karsilik geliyor - dogrudan
kullanilir. 11 tanesi (ATT, ATU, XEN, KTU, MLD, MYS, XGB, TYT, TOP, TET, ...)
BIRDEN FAZLA il/ilceye karsilik geliyor - bunlar icin il_kisa/ilce_kisa
kodlarinin anlamini (TURIB'in kendi ic kisaltmasi, sabit bir kural yok, orn.
KAYSERI->KYS, DIYARBAKIR->DYR, AKSARAY->AKS) veri icinden OGRENEREK
(unambiguous depo kodlarindaki gercek il/ilce ile il_kisa/ilce_kisa'yi
eslestirerek) coziyoruz.
"""
import csv
import glob
import json
from collections import Counter, defaultdict
from pathlib import Path

REPO_KOKU = Path(__file__).parent.parent
DEPO_LISTESI = REPO_KOKU / "turib_site_incelemesi" / "depo_isin_kod_listesi.csv"
GUNLUK_VERI_DIZINI = Path.home() / "Desktop" / "4-09-2026-turib" / "gunluk-bulten"  # agir veri, git disi (bkz PROJE_GECMISI.md)


def depo_listesini_yukle():
    rows = list(csv.DictReader(open(DEPO_LISTESI, encoding="utf-8")))
    by_kod = defaultdict(list)
    for r in rows:
        by_kod[r["ihrac_kodu"]].append({
            "il": r["il"].strip(),
            "ilce": r["ilce_lokasyon"].strip(),
            "lidas": r["lidas_unvani"].strip(),
        })
    return by_kod


def islem_kodu_parcala(kod: str):
    parcalar = kod.split("_")
    if len(parcalar) != 9:
        return None
    return {
        "il_kisa": parcalar[4],
        "ilce_kisa": parcalar[5],
        "depo_kodu": parcalar[6],
    }


def tum_dosyalari_bul():
    return sorted(glob.glob(str(GUNLUK_VERI_DIZINI / "*.json")))


def il_ilce_kisaltma_haritalarini_ogren(depo_by_kod):
    """Tek adayli (belirsiz olmayan) depo kodlarindaki gercek satirlardan
    il_kisa -> il ve (il_kisa, ilce_kisa) -> ilce haritalarini ogrenir."""
    il_kisa_sayaci = defaultdict(Counter)
    ilce_kisa_sayaci = defaultdict(Counter)

    for dosya in tum_dosyalari_bul():
        d = json.load(open(dosya, encoding="utf-8"))
        for section in ("normal_seans", "anlasmali"):
            for row in d.get(section, []):
                if row.get("İl"):
                    continue
                info = islem_kodu_parcala(row.get("İşlem Kodu", ""))
                if not info:
                    continue
                adaylar = depo_by_kod.get(info["depo_kodu"])
                if not adaylar or len(adaylar) != 1:
                    continue
                aday = adaylar[0]
                il_kisa_sayaci[info["il_kisa"]][aday["il"]] += 1
                ilce_kisa_sayaci[(info["il_kisa"], info["ilce_kisa"])][aday["ilce"]] += 1

    il_kisa_harita = {k: c.most_common(1)[0][0] for k, c in il_kisa_sayaci.items()}
    ilce_kisa_harita = {k: c.most_common(1)[0][0] for k, c in ilce_kisa_sayaci.items()}
    return il_kisa_harita, ilce_kisa_harita


def satiri_coz(row, depo_by_kod, il_kisa_harita, ilce_kisa_harita):
    """Basarili olursa (il, ilce, lidas, kesinlik) dondurur, olmazsa None."""
    info = islem_kodu_parcala(row.get("İşlem Kodu", ""))
    if not info:
        return None
    adaylar = depo_by_kod.get(info["depo_kodu"])
    if not adaylar:
        return None

    if len(adaylar) == 1:
        a = adaylar[0]
        return (a["il"], a["ilce"], a["lidas"], "kesin (tek_aday)")

    # birden fazla aday: il_kisa haritasiyla ili daralt
    beklenen_il = il_kisa_harita.get(info["il_kisa"])
    uygun = [a for a in adaylar if a["il"] == beklenen_il] if beklenen_il else adaylar
    if not uygun:
        uygun = adaylar

    if len(uygun) == 1:
        a = uygun[0]
        return (a["il"], a["ilce"], a["lidas"], "kesin (il_kisa_ile_daraltildi)")

    # hala birden fazla: ilce_kisa haritasiyla dene
    beklenen_ilce = ilce_kisa_harita.get((info["il_kisa"], info["ilce_kisa"]))
    if beklenen_ilce:
        uygun2 = [a for a in uygun if a["ilce"] == beklenen_ilce]
        if len(uygun2) == 1:
            a = uygun2[0]
            return (a["il"], a["ilce"], a["lidas"], "kesin (ilce_kisa_ile_daraltildi)")

    # tam cozemedik - YANLIS TAHMIN ETMEK YERINE BOS BIRAKIYORUZ (guvenlik icin).
    # il_kisa/ilce_kisa haritasi bu kombinasyonu hic ogrenememis demektir (bu
    # kombinasyon SADECE belirsiz depo kodlarinda goruluyor, ogrenme fazinda
    # kullanilamiyor) - ilk adayi rastgele secmek yanlis veriye yol acar.
    return None


def main():
    depo_by_kod = depo_listesini_yukle()
    print("Depo kodu -> il/ilce haritasi yuklendi:", len(depo_by_kod), "kod")

    il_kisa_harita, ilce_kisa_harita = il_ilce_kisaltma_haritalarini_ogren(depo_by_kod)
    print("Ogrenilen il_kisa haritasi:", len(il_kisa_harita), "kod")
    print("Ogrenilen ilce_kisa haritasi:", len(ilce_kisa_harita), "kod")

    toplam_eksik = 0
    toplam_dolduruldu = 0
    toplam_belirsiz = 0
    toplam_cozulemedi = 0
    guncellenen_dosya = 0

    for dosya in tum_dosyalari_bul():
        d = json.load(open(dosya, encoding="utf-8"))
        degisti = False
        for section in ("normal_seans", "anlasmali"):
            for row in d.get(section, []):
                if row.get("İl"):
                    continue
                toplam_eksik += 1
                sonuc = satiri_coz(row, depo_by_kod, il_kisa_harita, ilce_kisa_harita)
                if not sonuc:
                    toplam_cozulemedi += 1
                    continue
                il, ilce, lidas, kesinlik = sonuc
                row["İl"] = il
                row["İlçe"] = ilce
                row["LİDAŞ Adı"] = lidas
                row["_il_ilce_kesinlik"] = kesinlik  # seffaflik icin: nasil dolduruldugu izlenebilir kalsin
                degisti = True
                toplam_dolduruldu += 1
                if "BELIRSIZ" in kesinlik:
                    toplam_belirsiz += 1
        if degisti:
            json.dump(d, open(dosya, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            guncellenen_dosya += 1

    print()
    print(f"Toplam eksik satir: {toplam_eksik}")
    print(f"Dolduruldu: {toplam_dolduruldu} (bunun {toplam_belirsiz} tanesi BELIRSIZ isaretli)")
    print(f"Cozulemedi (Islem Kodu formati uymuyor): {toplam_cozulemedi}")
    print(f"Guncellenen dosya sayisi: {guncellenen_dosya}")


if __name__ == "__main__":
    main()
