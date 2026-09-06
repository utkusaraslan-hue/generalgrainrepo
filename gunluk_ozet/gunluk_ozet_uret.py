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
FONT_YOLU = "/System/Library/Fonts/Supplemental/Verdana.ttf"
FONT_YOLU_BOLD = "/System/Library/Fonts/Supplemental/Verdana Bold.ttf"
FONT_BOYUTU = 10  # excel_raporlar/borsa_takip_excel_uret.py'deki VERI_FONT ile ayni (Verdana 10pt)

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

TURIB_GUNLUK_ARSIV = Path.home() / "Desktop" / "4-09-2026-turib" / "gunluk-bulten"

TURIB_SINIFLAR = [
    "BUĞDAY EKMEKLİK KIRMIZI 1.SINIF", "BUĞDAY EKMEKLİK KIRMIZI 2.SINIF",
    "BUĞDAY EKMEKLİK KIRMIZI 3.SINIF", "BUĞDAY EKMEKLİK KIRMIZI DÜŞÜK VASIFLI",
    "BUĞDAY EKMEKLİK BEYAZ 1.SINIF", "BUĞDAY EKMEKLİK BEYAZ 2.SINIF",
    "BUĞDAY EKMEKLİK BEYAZ 3.SINIF", "BUĞDAY EKMEKLİK BEYAZ DÜŞÜK VASIFLI",
    "ARPA 1.SINIF", "ARPA 2.SINIF", "MISIR 1.SINIF", "MISIR 2.SINIF",
]


def tr_sayi(s):
    if s is None or s == "":
        return None
    return float(str(s).replace(".", "").replace(",", "."))


def urun_grubu_genel(cls: str) -> str | None:
    c = (cls or "").upper()
    if "BUĞDAY" in c:
        return "BUĞDAY"
    if c.startswith("ARPA"):
        return "ARPA"
    if "MISIR" in c:
        return "MISIR"
    return None


def turib_en_ucuz_pahali(hedef_tarih: date) -> dict:
    """TÜRİB gunluk arsivinden (Masaustu, tam gecmis) o gunun normal_seans
    verisiyle her sinif icin en ucuz/en pahali LİDAŞ'i bulur. Fiyat yoksa
    (sadece anlasmali islem varsa) o sinif atlanir."""
    dosya = TURIB_GUNLUK_ARSIV / f"{hedef_tarih.isoformat()}.json"
    sonuc = {}
    if not dosya.exists():
        return sonuc
    veri = json.loads(dosya.read_text(encoding="utf-8"))
    satirlar_by_sinif = {}
    for row in veri.get("normal_seans", []):
        cls = row.get("Enstrüman Sınıfı")
        if cls not in TURIB_SINIFLAR:
            continue
        fiyat = tr_sayi(row.get("Ağırlıklı Ortalama Fiyat")) or tr_sayi(row.get("Kapanış Fiyatı"))
        if fiyat is None:
            continue
        satirlar_by_sinif.setdefault(cls, []).append({
            "fiyat": fiyat, "il": row.get("İl"), "ilce": row.get("İlçe"),
            "lidas": row.get("LİDAŞ Adı"),
        })
    for cls, satirlar in satirlar_by_sinif.items():
        ucuz = min(satirlar, key=lambda x: x["fiyat"])
        pahali = max(satirlar, key=lambda x: x["fiyat"])
        sonuc[cls] = {"ucuz": ucuz, "pahali": pahali, "n": len(satirlar)}
    return sonuc


def tmo_en_ucuz_pahali(conn) -> dict:
    """TMO'nun kendi urun kategorilerinde en ucuz/en pahali IL'i bulur
    (DB'deki TMO'nun EN SON tarihli verisinden)."""
    son_tarih = conn.execute("SELECT MAX(tarih) FROM fiyatlar WHERE kaynak='TMO'").fetchone()[0]
    sonuc = {}
    if not son_tarih:
        return sonuc, None
    rows = conn.execute(
        "SELECT il, urun, ort_fiyat FROM fiyatlar WHERE kaynak='TMO' AND tarih=? AND ort_fiyat IS NOT NULL AND ort_fiyat > 0",
        (son_tarih,),
    ).fetchall()
    by_urun = {}
    for il, urun, fiyat in rows:
        if urun_grubu_genel(urun) is None:
            continue  # sadece bugday/arpa/misir (Yulaf, Soya Fasulyesi vb disarida)
        by_urun.setdefault(urun, []).append({"il": il, "fiyat": fiyat})
    for urun, satirlar in by_urun.items():
        ucuz = min(satirlar, key=lambda x: x["fiyat"])
        pahali = max(satirlar, key=lambda x: x["fiyat"])
        sonuc[urun] = {"ucuz": ucuz, "pahali": pahali, "n": len(satirlar)}
    return sonuc, son_tarih


def tb_en_ucuz_pahali(conn) -> dict:
    """4 ticaret borsasi (Bandirma/Edirne/Kirklareli/Tekirdag) arasinda,
    her birinin DB'deki EN SON tarihli verisiyle, BUGDAY/ARPA/MISIR
    genelinde en ucuz/en pahali borsayi bulur (agirlikli ortalama ile)."""
    TB_KAYNAKLARI = [
        (["BANDIRMA"], "Bandırma"),
        (["ETB", "ETB_AYLIK"], "Edirne"),
        (["KIRKLARELI_AYLIK"], "Kırklareli"),
        (["TDAG"], "Tekirdağ"),
    ]
    by_grup = {"BUĞDAY": [], "ARPA": [], "MISIR": []}
    for kaynak_kodlari, ad in TB_KAYNAKLARI:
        df, son_tarih = kaynak_son_veri(conn, kaynak_kodlari)
        if df.empty:
            continue
        for grup in by_grup:
            alt = df[df["urun"].apply(lambda u: urun_grubu_genel(u) == grup)]
            alt = alt.dropna(subset=["ort_fiyat"])
            if len(alt) == 0:
                continue
            if alt["miktar"].sum() > 0:
                import numpy as np
                fiyat = float(np.average(alt["ort_fiyat"], weights=alt["miktar"].fillna(0) + 1e-9))
            else:
                fiyat = float(alt["ort_fiyat"].mean())
            by_grup[grup].append({"borsa": ad, "fiyat": fiyat, "tarih": son_tarih})
    sonuc = {}
    for grup, satirlar in by_grup.items():
        if not satirlar:
            continue
        ucuz = min(satirlar, key=lambda x: x["fiyat"])
        pahali = max(satirlar, key=lambda x: x["fiyat"])
        sonuc[grup] = {"ucuz": ucuz, "pahali": pahali, "n": len(satirlar)}
    return sonuc


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


def _yer_var_mi(pdf, yukseklik: float) -> bool:
    """Verilen yukseklikte bir blok (baslik+ucuz+pahali gibi) mevcut sayfaya
    sigar mi? Sigmazsa cagiran taraf pdf.add_page() ile yeni sayfaya gecmeli -
    boylece bir grup (orn. 'ARPA' basligi + Ucuz/Pahali satirlari) SAYFA
    ORTASINDA BOLUNMUYOR (kullanicinin fark ettigi kayma buydu)."""
    return pdf.get_y() + yukseklik <= pdf.h - pdf.b_margin


def pdf_uret(hedef_tarih: date, klasor: Path, ad: str, ozet: dict):
    B = FONT_BOYUTU  # 10 - govde metni (Excel'deki VERI_FONT ile ayni)
    pdf = FPDF()
    pdf.add_page()
    pdf.add_font("Verdana", "", FONT_YOLU)
    pdf.add_font("Verdana", "B", FONT_YOLU_BOLD)
    pdf.set_font("Verdana", "B", B + 6)
    pdf.cell(0, 10, f"Günlük Borsa Özeti - {ad}", ln=True)
    pdf.set_font("Verdana", "", B)
    pdf.cell(0, 6, f"Üretim zamanı: {datetime.now().strftime('%d.%m.%Y %H:%M')}", ln=True)
    pdf.ln(4)

    pdf.set_font("Verdana", "B", B + 2)
    pdf.cell(0, 8, "Kaynak Durumu", ln=True)
    pdf.set_font("Verdana", "", B)

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

    conn = sqlite3.connect(DB_PATH)

    GRUP_YUKSEKLIK = 6 + 5 + 5  # baslik + ucuz + pahali satirlari

    # ---- TÜRİB: 12 sinif, en ucuz/en pahali LİDAŞ ----
    turib_sonuc = turib_en_ucuz_pahali(hedef_tarih)
    pdf.ln(4)
    if not _yer_var_mi(pdf, 8 + GRUP_YUKSEKLIK):
        pdf.add_page()
    pdf.set_font("Verdana", "B", B + 2)
    pdf.cell(0, 8, f"TÜRİB - En Ucuz / En Pahalı LİDAŞ ({hedef_tarih.strftime('%d.%m.%Y')})", ln=True)
    pdf.set_font("Verdana", "", B)
    if not turib_sonuc:
        pdf.cell(0, 6, "Bu tarih için TÜRİB arşiv verisi bulunamadı.", ln=True)
    for cls in TURIB_SINIFLAR:
        s = turib_sonuc.get(cls)
        if not s:
            continue
        u, p = s["ucuz"], s["pahali"]
        if not _yer_var_mi(pdf, GRUP_YUKSEKLIK):
            pdf.add_page()
        pdf.set_font("Verdana", "B", B)
        pdf.cell(0, 6, cls, ln=True)
        pdf.set_font("Verdana", "", B)
        pdf.cell(0, 5, f"   Ucuz : {u['fiyat']:.2f} TL/kg - {u['lidas']} ({u['il']}/{u['ilce']})", ln=True)
        pdf.cell(0, 5, f"   Pahalı: {p['fiyat']:.2f} TL/kg - {p['lidas']} ({p['il']}/{p['ilce']})", ln=True)

    # ---- TMO: en ucuz/en pahali IL ----
    tmo_sonuc, tmo_tarih = tmo_en_ucuz_pahali(conn)
    pdf.ln(3)
    if not _yer_var_mi(pdf, 8 + GRUP_YUKSEKLIK):
        pdf.add_page()
    pdf.set_font("Verdana", "B", B + 2)
    baslik_tarih = f" ({date.fromisoformat(tmo_tarih).strftime('%d.%m.%Y')})" if tmo_tarih else ""
    pdf.cell(0, 8, f"TMO - En Ucuz / En Pahalı İl{baslik_tarih}", ln=True)
    pdf.set_font("Verdana", "", B)
    if not tmo_sonuc:
        pdf.cell(0, 6, "TMO verisi bulunamadı.", ln=True)
    for urun, s in tmo_sonuc.items():
        u, p = s["ucuz"], s["pahali"]
        if not _yer_var_mi(pdf, GRUP_YUKSEKLIK):
            pdf.add_page()
        pdf.set_font("Verdana", "B", B)
        pdf.cell(0, 6, urun, ln=True)
        pdf.set_font("Verdana", "", B)
        pdf.cell(0, 5, f"   Ucuz : {u['fiyat']:.0f} TL/ton - {u['il']}", ln=True)
        pdf.cell(0, 5, f"   Pahalı: {p['fiyat']:.0f} TL/ton - {p['il']}", ln=True)

    # ---- TB'ler: 4 borsa arasi en ucuz/en pahali ----
    tb_sonuc = tb_en_ucuz_pahali(conn)
    pdf.ln(3)
    if not _yer_var_mi(pdf, 8 + GRUP_YUKSEKLIK):
        pdf.add_page()
    pdf.set_font("Verdana", "B", B + 2)
    pdf.cell(0, 8, "Ticaret Borsaları - En Ucuz / En Pahalı (Bandırma/Edirne/Kırklareli/Tekirdağ)", ln=True)
    pdf.set_font("Verdana", "", B)
    if not tb_sonuc:
        pdf.cell(0, 6, "TB verisi bulunamadı.", ln=True)
    for grup, s in tb_sonuc.items():
        u, p = s["ucuz"], s["pahali"]
        if not _yer_var_mi(pdf, GRUP_YUKSEKLIK):
            pdf.add_page()
        pdf.set_font("Verdana", "B", B)
        pdf.cell(0, 6, grup, ln=True)
        pdf.set_font("Verdana", "", B)
        pdf.cell(0, 5, f"   Ucuz : {u['fiyat']:.2f} TL/kg - {u['borsa']} ({date.fromisoformat(u['tarih']).strftime('%d.%m.%Y')})", ln=True)
        pdf.cell(0, 5, f"   Pahalı: {p['fiyat']:.2f} TL/kg - {p['borsa']} ({date.fromisoformat(p['tarih']).strftime('%d.%m.%Y')})", ln=True)

    conn.close()
    pdf.ln(4)
    pdf.set_font("Verdana", "", B - 2)
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
