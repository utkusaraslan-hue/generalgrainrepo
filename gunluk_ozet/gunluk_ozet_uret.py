"""Her gün icin ~/Desktop/bizim-gunluk-bulten/{DD-MM-YYYY}/ altina:
  1) gunluk_veri_{DD-MM-YYYY}.xlsx  - TMO + TURIB + 4 ticaret borsasinin
     borsa_verileri.db'deki EN GUNCEL (her kaynak kendi son tarihi) verisi
  2) gunluk_ozet_{DD-MM-YYYY}.pdf   - kisa metin ozeti (kaynak durumu +
     bugday/arpa/misir fiyat seviyeleri + gecikmis/bayat kaynak uyarisi)

Kullanim:
    python3 -m gunluk_ozet.gunluk_ozet_uret                # bugun icin
    python3 -m gunluk_ozet.gunluk_ozet_uret 2026-09-07     # belirli tarih icin

NOT: Excel'deki veri illa o gune ait degil - her kaynagin DB'deki EN SON
kaydi kullanilir (hafta sonu/tatilde yeni veri gelmez, o zaman bir onceki
is gununun verisi gosterilir - bu PDF'te acikca belirtilir).
"""
import argparse
import json
import sqlite3
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
from fpdf import FPDF

REPO_KOKU = Path(__file__).parent.parent
DB_PATH = REPO_KOKU / "veri_kaynagi" / "borsa_verileri.db"
BIZIM_BULTEN_KOKU = Path.home() / "Desktop" / "bizim-gunluk-bulten"
FONT_YOLU = "/Library/Fonts/Arial Unicode.ttf"

sys.path.insert(0, str(REPO_KOKU / "excel_raporlar"))
from borsa_takip_excel_uret import sayfayi_bicimlendir, ilgili_urun  # noqa: E402

KAYNAK_GRUPLARI = [
    (["TMO"], "TMO"),
    (["TURIB_ENDEKS"], "TÜRİB Endeks"),
    (["TURIB_NORMAL_SEANS"], "TÜRİB Normal Seans"),
    (["KONYA"], "Konya"),
    (["BANDIRMA"], "Bandırma"),
    (["ETB", "ETB_AYLIK"], "Edirne"),
    (["KIRKLARELI_AYLIK"], "Kırklareli"),
    (["TDAG"], "Tekirdağ"),
]


def gun_klasoru(hedef_tarih: date) -> Path:
    ad = hedef_tarih.strftime("%-d-%m-%Y") if sys.platform != "win32" else hedef_tarih.strftime("%d-%m-%Y").lstrip("0")
    klasor = BIZIM_BULTEN_KOKU / ad
    klasor.mkdir(parents=True, exist_ok=True)
    return klasor, ad


def kaynak_son_veri(conn, kaynak_kodlari: list[str]) -> pd.DataFrame:
    """Bu kaynak grubunun DB'deki EN SON tarihine ait tum satirlarini doner."""
    yer_tutucu = ",".join("?" * len(kaynak_kodlari))
    son_tarih_row = conn.execute(
        f"SELECT MAX(tarih) FROM fiyatlar WHERE kaynak IN ({yer_tutucu})", kaynak_kodlari
    ).fetchone()
    son_tarih = son_tarih_row[0]
    if not son_tarih:
        return pd.DataFrame(), None
    rows = conn.execute(
        f"SELECT * FROM fiyatlar WHERE kaynak IN ({yer_tutucu}) AND tarih = ?",
        kaynak_kodlari + [son_tarih],
    ).fetchall()
    cols = [d[0] for d in conn.execute("SELECT * FROM fiyatlar LIMIT 0").description]
    df = pd.DataFrame(rows, columns=cols)
    return df, son_tarih


def ham_alan(ham_json: str, *anahtarlar):
    if not ham_json:
        return None
    try:
        d = json.loads(ham_json)
    except Exception:
        return None
    for a in anahtarlar:
        if a in d and d[a] is not None:
            return d[a]
    return None


def excel_uret(hedef_tarih: date, klasor: Path, ad: str) -> dict:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = None
    ozet = {}

    xlsx_yolu = klasor / f"gunluk_veri_{ad}.xlsx"
    with pd.ExcelWriter(xlsx_yolu, engine="openpyxl") as writer:
        for kaynak_kodlari, sheet_adi in KAYNAK_GRUPLARI:
            df, son_tarih = kaynak_son_veri(conn, kaynak_kodlari)
            if df.empty:
                ozet[sheet_adi] = {"son_tarih": None, "satir": 0}
                continue

            gosterim = pd.DataFrame({
                "Tarih": pd.to_datetime(df["tarih"]).dt.date,
                "İl": df["il"], "İlçe": df["ilce"], "Ürün": df["urun"], "Detay": df["detay"],
                "Min Fiyat": df["min_fiyat"], "Ort. Fiyat": df["ort_fiyat"], "Max Fiyat": df["max_fiyat"],
                "Miktar": df["miktar"], "Birim": df["birim"],
            })
            sheet = sheet_adi[:31]
            gosterim.to_excel(writer, sheet_name=sheet, index=False)
            sayfayi_bicimlendir(writer.sheets[sheet], gosterim.columns, sheet)

            ilgili = df[df["urun"].apply(ilgili_urun)]
            ozet[sheet_adi] = {
                "son_tarih": son_tarih, "satir": len(df),
                "bugday_arpa_misir_satir": len(ilgili),
                "ort_fiyat_bugday_arpa_misir": round(ilgili["ort_fiyat"].dropna().mean(), 2) if len(ilgili) and ilgili["ort_fiyat"].notna().any() else None,
            }
    conn.close()
    print(f"Excel yazildi: {xlsx_yolu}")
    return ozet


def pdf_uret(hedef_tarih: date, klasor: Path, ad: str, ozet: dict):
    pdf = FPDF()
    pdf.add_page()
    pdf.add_font("ArialUnicode", "", FONT_YOLU)
    pdf.set_font("ArialUnicode", size=16)
    pdf.cell(0, 10, f"Günlük Borsa Özeti - {ad}", ln=True)
    pdf.set_font("ArialUnicode", size=9)
    pdf.cell(0, 6, f"Üretim zamanı: {datetime.now().strftime('%d.%m.%Y %H:%M')}", ln=True)
    pdf.ln(4)

    pdf.set_font("ArialUnicode", size=12)
    pdf.cell(0, 8, "Kaynak Durumu", ln=True)
    pdf.set_font("ArialUnicode", size=9)

    bugun = hedef_tarih
    for sheet_adi, bilgi in ozet.items():
        if bilgi["son_tarih"] is None:
            pdf.cell(0, 6, f"- {sheet_adi}: VERİ YOK", ln=True)
            continue
        son = date.fromisoformat(bilgi["son_tarih"])
        gecikme = (bugun - son).days
        uyari = ""
        if gecikme > 4:
            uyari = f"  [UYARI] {gecikme} gündür güncellenmemiş, kontrol et"
        elif gecikme > 1:
            uyari = f"  ({gecikme} gün önce - hafta sonu/tatil olabilir)"
        satir = f"- {sheet_adi}: son veri {son.strftime('%d.%m.%Y')}, {bilgi['satir']} kayıt{uyari}"
        pdf.cell(0, 6, satir, ln=True)

    pdf.ln(4)
    pdf.set_font("ArialUnicode", size=12)
    pdf.cell(0, 8, "Buğday/Arpa/Mısır Ortalama Fiyat (TL/kg)", ln=True)
    pdf.set_font("ArialUnicode", size=9)
    for sheet_adi, bilgi in ozet.items():
        ort = bilgi.get("ort_fiyat_bugday_arpa_misir")
        if ort is not None:
            birim = "TL/ton" if sheet_adi == "TMO" else "TL/kg"
            pdf.cell(0, 6, f"- {sheet_adi}: {ort:.2f} {birim} ({bilgi.get('bugday_arpa_misir_satir', 0)} kayıt)", ln=True)

    pdf.ln(4)
    pdf.set_font("ArialUnicode", size=8)
    pdf.set_text_color(120, 120, 120)
    pdf.multi_cell(0, 5, "Not: Gösterilen veri o günün değil, her kaynağın veritabanındaki EN GÜNCEL "
                          "kaydına ait. Hafta sonu/resmi tatilde borsalar işlem yapmadığı için "
                          "bir önceki iş gününün verisi görünür, bu normaldir.")

    pdf_yolu = klasor / f"gunluk_ozet_{ad}.pdf"
    pdf.output(str(pdf_yolu))
    print(f"PDF yazildi: {pdf_yolu}")


def calistir(hedef_tarih_str: str | None = None):
    hedef_tarih = date.fromisoformat(hedef_tarih_str) if hedef_tarih_str else date.today()
    klasor, ad = gun_klasoru(hedef_tarih)
    ozet = excel_uret(hedef_tarih, klasor, ad)
    pdf_uret(hedef_tarih, klasor, ad, ozet)
    print(f"\nTamamlandı: {klasor}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("tarih", nargs="?", default=None, help="YYYY-MM-DD (varsayılan: bugün)")
    args = parser.parse_args()
    calistir(args.tarih)
