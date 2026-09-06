"""Temmuz+Agustos 2026 gunluk bultenlerini (Normal Seans, Endeks, Anlasmali)
tarih sirasina gore tek bir Excel dosyasinda (ayri sekmeler halinde) birlestirir.
"""
import glob
import json
from pathlib import Path

import openpyxl
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

KOK = Path(__file__).parent
VERI_KOK = Path.home() / "Desktop" / "4-09-2026-turib" / "temmuz-agustos-2026-arsiv"  # agir veri, git disi
HEDEF = Path("/Users/utkus/Desktop/turib_gunluk_bultenler_temmuz_agustos_2026.xlsx")


def sayiya_cevir(s):
    if s is None or s == "" or s == "-":
        return None
    s = str(s).strip().replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return s  # sayi degilse oldugu gibi birak (metin alan olabilir)


def sekme_yaz(wb, ad, satirlar, basliklar):
    ws = wb.create_sheet(ad)
    ws.append(basliklar)
    for hucre in ws[1]:
        hucre.font = Font(bold=True)
    for satir in satirlar:
        ws.append([satir.get(b) for b in basliklar])
    for i, b in enumerate(basliklar, start=1):
        genislik = max(10, min(30, len(b) + 2))
        ws.column_dimensions[get_column_letter(i)].width = genislik
    ws.freeze_panes = "A2"


def main():
    dosyalar = sorted(glob.glob(str(VERI_KOK / "gunluk_veri" / "*.json")))  # dosya adlari YYYY-MM-DD -> zaten kronolojik
    print(f"{len(dosyalar)} gunluk bulten dosyasi bulundu")

    normal_seans_tum, endeks_tum, anlasmali_tum = [], [], []
    for f in dosyalar:
        d = json.load(open(f, encoding="utf-8"))
        tarih = d["tarih"]
        for s in d["endeks"]:
            satir = {"tarih": tarih, **s}
            for alan in ("Önceki Kapanış", "En Düşük", "En Yüksek", "Kapanış",
                         "İşlem Miktarı [KG]", "İşlem Hacmi [TL]"):
                if alan in satir:
                    satir[alan] = sayiya_cevir(satir[alan])
            endeks_tum.append(satir)
        for s in d["normal_seans"]:
            satir = {"tarih": tarih, **s}
            for alan in ("Önceki Kapanış Fiyatı", "En Düşük Fiyat", "En Yüksek Fiyat",
                         "Ağırlıklı Ortalama Fiyat", "Kapanış Fiyatı", "İşlem Adedi",
                         "İşlem Miktarı [KG]", "İşlem Hacmi [TL]"):
                if alan in satir:
                    satir[alan] = sayiya_cevir(satir[alan])
            normal_seans_tum.append(satir)
        for s in d["anlasmali"]:
            satir = {"tarih": tarih, **s}
            anlasmali_tum.append(satir)

    print(f"Normal Seans: {len(normal_seans_tum)} satir, Endeks: {len(endeks_tum)} satir, "
          f"Anlasmali: {len(anlasmali_tum)} satir")

    wb = openpyxl.Workbook()
    wb.remove(wb.active)  # varsayilan bos sekmeyi sil

    if normal_seans_tum:
        basliklar = ["tarih"] + [k for k in normal_seans_tum[0].keys() if k != "tarih"]
        sekme_yaz(wb, "Normal Seans", normal_seans_tum, basliklar)
    if endeks_tum:
        basliklar = ["tarih"] + [k for k in endeks_tum[0].keys() if k != "tarih"]
        sekme_yaz(wb, "Endeks", endeks_tum, basliklar)
    if anlasmali_tum:
        basliklar = ["tarih"] + [k for k in anlasmali_tum[0].keys() if k != "tarih"]
        sekme_yaz(wb, "Anlaşmalı", anlasmali_tum, basliklar)

    wb.save(HEDEF)
    print(f"\nKaydedildi: {HEDEF}")


if __name__ == "__main__":
    main()
