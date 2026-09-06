"""Bu haftaki (gunluk_veri/*.json) TURIB islemlerinden TMO-TOBB Tarim Urunleri
Lisansli Depoculuk A.S. (TMO'nun TURIB'deki LIDAS'i) tarafindan islem goren
ISIN'leri ozetler ve Excel'e doker."""
import glob
import json
from collections import defaultdict
from pathlib import Path

import openpyxl
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

KOK = Path(__file__).parent
GUNLUK_VERI_DIZINI = Path.home() / "Desktop" / "4-09-2026-turib" / "gunluk-bulten"  # agir veri, git disi (bkz PROJE_GECMISI.md)
HEDEF = Path("/Users/utkus/Desktop/tmo_turib_bu_hafta.xlsx")


def sayi(s):
    return float(s.replace(".", "").replace(",", "."))


def main():
    dosyalar = sorted(glob.glob(str(GUNLUK_VERI_DIZINI / "2026-09-0[1-5].json")))
    ozet = defaultdict(lambda: {"miktar_kg": 0.0, "islem": 0, "tur": set(), "fiyatlar": []})
    detay_satirlar = []

    for f in dosyalar:
        d = json.load(open(f, encoding="utf-8"))
        tarih = d["tarih"]
        for grup in ("normal_seans", "anlasmali"):
            for s in d[grup]:
                if "TMO" not in s.get("LİDAŞ Adı", ""):
                    continue
                isin = s["ISIN Kodu"]
                miktar = sayi(s["İşlem Miktarı [KG]"])
                fiyat = sayi(s["Ağırlıklı Ortalama Fiyat"]) if grup == "normal_seans" else None
                k = ozet[isin]
                k["enstruman"] = s["Enstrüman Sınıfı"]
                k["il"], k["ilce"] = s["İl"], s["İlçe"]
                k["miktar_kg"] += miktar
                k["islem"] += 1
                k["tur"].add(grup)
                if fiyat is not None:
                    k["fiyatlar"].append(fiyat)
                detay_satirlar.append({
                    "tarih": tarih, "tur": grup, "isin": isin,
                    "enstruman": s["Enstrüman Sınıfı"], "il": s["İl"], "ilce": s["İlçe"],
                    "miktar_kg": miktar, "fiyat_tl_kg": fiyat,
                    "hacim_tl": round(fiyat * miktar, 2) if fiyat else None,
                    "islem_kodu": s["İşlem Kodu"],
                })

    wb = openpyxl.Workbook()
    ws1 = wb.active
    ws1.title = "ISIN Özet (hafta)"
    basliklar = ["isin", "enstruman", "il", "ilce", "toplam_kg", "toplam_ton", "islem_sayisi",
                 "tur", "agirlikli_ort_fiyat_tl_kg_normal_seans"]
    ws1.append(basliklar)
    for c in ws1[1]:
        c.font = Font(bold=True)
    for isin, k in sorted(ozet.items(), key=lambda x: -x[1]["miktar_kg"]):
        ort_fiyat = round(sum(k["fiyatlar"]) / len(k["fiyatlar"]), 4) if k["fiyatlar"] else None
        ws1.append([isin, k["enstruman"], k["il"], k["ilce"], k["miktar_kg"], round(k["miktar_kg"] / 1000, 2),
                    k["islem"], "+".join(sorted(k["tur"])), ort_fiyat])
    for i in range(1, len(basliklar) + 1):
        ws1.column_dimensions[get_column_letter(i)].width = 22

    ws2 = wb.create_sheet("Günlük Detay")
    basliklar2 = ["tarih", "tur", "isin", "enstruman", "il", "ilce", "miktar_kg",
                  "fiyat_tl_kg", "hacim_tl", "islem_kodu"]
    ws2.append(basliklar2)
    for c in ws2[1]:
        c.font = Font(bold=True)
    for s in detay_satirlar:
        ws2.append([s[b] for b in basliklar2])
    for i in range(1, len(basliklar2) + 1):
        ws2.column_dimensions[get_column_letter(i)].width = 20

    wb.save(HEDEF)
    print(f"Kaydedildi: {HEDEF}")
    print(f"{len(ozet)} farklı ISIN, toplam {sum(k['miktar_kg'] for k in ozet.values()):,.0f} kg")


if __name__ == "__main__":
    main()
