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

PDF URETIM YONTEMI: fpdf2 ile elle x/y konumlandirma (cell/multi_cell)
tekrar tekrar sayfa-sonu ve metin-tasma hatalarina yol acti (2026-09-06,
kullanici fark etti). Onun yerine ONCE Word (.docx, python-docx ile -
paragraf tabanli, otomatik satir/sayfa akisi, manuel konumlandirma YOK)
uretiliyor, SONRA LibreOffice'in headless donusturucusu (`soffice
--headless --convert-to pdf`) ile PDF'e ceviriyor. Bu sayede hem sayfa/
satir kirilma sorunlari Word'un/LO'nun kendi motoruna devrediliyor, hem
de (docx2pdf/MS Word GUI otomasyonunun aksine - macOS Automation izni
gerektirip gunluk launchd gorevinde takilabiliyordu) tamamen sessiz ve
izinsiz calisiyor.
"""
import argparse
import json
import shutil
import sqlite3
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.shared import Pt, RGBColor

SOFFICE_YOLU = shutil.which("soffice") or "/opt/homebrew/bin/soffice"

REPO_KOKU = Path(__file__).parent.parent
DB_PATH = REPO_KOKU / "veri_kaynagi" / "borsa_verileri.db"
BIZIM_BULTEN_KOKU = Path.home() / "Desktop" / "bizim-gunluk-bulten"
FONT_ADI = "Arial"
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


CANLI_EMIR_MIN_ADET = 10000  # bu esigin altindaki adetler (kg) anlamli hacim sayilmaz


def _canli_emir_sinif_bul(urun_adi: str) -> str | None:
    ad = (urun_adi or "").upper()
    if "BUĞDAY" in ad:
        taban = "BUĞDAY"
    elif "ARPA" in ad:
        taban = "ARPA"
    elif "MISIR" in ad:
        taban = "MISIR"
    else:
        return None
    sinif = "?"
    for s in ["1.SINIF", "2.SINIF", "3.SINIF", "DÜŞÜK VASIFLI"]:
        if s.replace(" ", "") in ad.replace(" ", ""):
            sinif = s
            break
    renk = "KIRMIZI" if "KIRMIZI" in ad else ("BEYAZ" if "BEYAZ" in ad else "")
    return " ".join(p for p in [taban, renk, sinif] if p)


def _canli_emir_yer_bul(urun_adi: str) -> str:
    parcalar = (urun_adi or "").split()
    return " ".join(parcalar[-2:]) if len(parcalar) >= 2 else (urun_adi or "")


def canli_emirler_firsat_tara(klasor: Path) -> list[dict]:
    """Kullanicinin gunluk klasore manuel ekledigi canli emir defteri Excel'ini
    (TURIB'in kendi TL/KG bazli 'Data' sayfasi: ISIN/Urun Adi/.../Alis Fiyati/
    Satis Fiyati/Alis Adedi/Satis Adedi kolonlari) bulup, her urun sinifi icin
    (yeterli hacimli) en ucuz satis emri ile en pahali alis (bid) emri
    arasindaki spread'i hesaplar - navlun/mesafe DAHIL DEGIL, sadece ham
    fiyat farki. Dosya yoksa bos liste doner."""
    adaylar = [f for f in klasor.glob("*.xlsx") if not f.name.startswith("gunluk_veri_")]
    sonuc = []
    for dosya in adaylar:
        try:
            df = pd.read_excel(dosya, sheet_name="Data")
        except Exception:
            continue
        gerekli = {"Ürün Adı", "Alış Fiyatı", "Satış Fiyatı", "Alış Adedi", "Satış Adedi"}
        if not gerekli.issubset(df.columns):
            continue
        df["sinif"] = df["Ürün Adı"].apply(_canli_emir_sinif_bul)
        df["yer"] = df["Ürün Adı"].apply(_canli_emir_yer_bul)
        for sinif, grp in df.groupby("sinif"):
            if sinif is None:
                continue
            asklar = grp[grp["Satış Adedi"] >= CANLI_EMIR_MIN_ADET]
            bidler = grp[grp["Alış Adedi"] >= CANLI_EMIR_MIN_ADET]
            if asklar.empty or bidler.empty:
                continue
            ucuz = asklar.loc[asklar["Satış Fiyatı"].idxmin()]
            pahali = bidler.loc[bidler["Alış Fiyatı"].idxmax()]
            spread = float(pahali["Alış Fiyatı"] - ucuz["Satış Fiyatı"])
            if spread <= 0:
                continue
            sonuc.append({
                "sinif": sinif,
                "ucuz_fiyat": float(ucuz["Satış Fiyatı"]), "ucuz_yer": ucuz["yer"], "ucuz_adet": int(ucuz["Satış Adedi"]),
                "pahali_fiyat": float(pahali["Alış Fiyatı"]), "pahali_yer": pahali["yer"], "pahali_adet": int(pahali["Alış Adedi"]),
                "spread_ton": spread * 1000,
                "hacim_kg": int(min(ucuz["Satış Adedi"], pahali["Alış Adedi"])),
                "kaynak_dosya": dosya.name,
            })
    sonuc.sort(key=lambda x: x["spread_ton"], reverse=True)
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


def _run_fontunu_zorla(run, ad: str):
    """run.font.name = ad tek basina yetmiyor - Word/LibreOffice docx'teki
    'theme font' (rFonts asciiTheme=minorHAnsi vb.) referansini oncelikli
    sayip Verdana yerine tema fontunu (genelde bir serif/varsayilan) kullanmaya
    devam edebiliyor. Butun rFonts alt-ozniteliklerini (ascii/hAnsi/eastAsia/cs)
    dogrudan XML uzerinden yazip tema referansini gecersiz kiliyoruz."""
    run.font.name = ad
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = OxmlElement("w:rFonts")
        rPr.append(rFonts)
    for oznitelik in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        rFonts.set(qn(oznitelik), ad)
    # tema referanslarini kaldir ki yukaridaki acik isimler ezilmesin
    for tema_ozniteligi in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
        if rFonts.get(qn(tema_ozniteligi)) is not None:
            del rFonts.attrib[qn(tema_ozniteligi)]


def _stil_ayarla(doc: Document):
    normal = doc.styles["Normal"]
    normal.font.name = FONT_ADI
    normal.font.size = Pt(FONT_BOYUTU)
    rPr = normal.element.get_or_add_rPr()
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = OxmlElement("w:rFonts")
        rPr.append(rFonts)
    for oznitelik in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        rFonts.set(qn(oznitelik), FONT_ADI)


def _paragraf(doc, metin="", boyut=None, kalin=False, renk=None, girinti=None, sonrakiyle_tut=False):
    p = doc.add_paragraph()
    if girinti is not None:
        p.paragraph_format.left_indent = Pt(girinti)
    p.paragraph_format.space_after = Pt(2)
    if sonrakiyle_tut:
        # Word/LO'ya bu paragrafi bir sonrakinden AYRI SAYFAYA BOLME diyor -
        # boylece orn. 'ARPA 1.SINIF' basligi sayfa sonunda yalniz kalip
        # Ucuz/Pahali satirlari bir sonraki sayfaya kaymiyor (manuel sayfa
        # hesabi yerine Word'un kendi 'keep with next' mekanizmasi).
        p.paragraph_format.keep_with_next = True
    run = p.add_run(metin)
    _run_fontunu_zorla(run, FONT_ADI)
    run.font.size = Pt(boyut or FONT_BOYUTU)
    run.font.bold = kalin
    if renk:
        run.font.color.rgb = RGBColor(*renk)
    return p


def docx_uret(hedef_tarih: date, klasor: Path, ad: str, ozet: dict) -> Path:
    B = FONT_BOYUTU
    doc = Document()
    _stil_ayarla(doc)

    _paragraf(doc, f"Günlük Borsa Özeti - {ad}", boyut=B + 6, kalin=True)
    _paragraf(doc, f"Üretim zamanı: {datetime.now().strftime('%d.%m.%Y %H:%M')}")

    _paragraf(doc, "Kaynak Durumu", boyut=B + 2, kalin=True)
    bugun = hedef_tarih
    for sheet_adi, bilgi in ozet.items():
        if bilgi["son_tarih"] is None:
            _paragraf(doc, f"- {sheet_adi}: VERİ YOK")
            continue
        son = date.fromisoformat(bilgi["son_tarih"])
        gecikme = (bugun - son).days
        uyari = ""
        if gecikme > 4:
            uyari = f"  [UYARI] {gecikme} gündür güncellenmemiş, kontrol et"
        elif gecikme > 1:
            uyari = f"  ({gecikme} gün önce - hafta sonu/tatil olabilir)"
        _paragraf(doc, f"- {sheet_adi}: son veri {son.strftime('%d.%m.%Y')}, {bilgi['satir']} kayıt{uyari}")

    conn = sqlite3.connect(DB_PATH)

    # ---- TÜRİB: 12 sinif, en ucuz/en pahali LİDAŞ ----
    turib_sonuc = turib_en_ucuz_pahali(hedef_tarih)
    _paragraf(doc, f"TÜRİB - En Ucuz / En Pahalı LİDAŞ ({hedef_tarih.strftime('%d.%m.%Y')})", boyut=B + 2, kalin=True)
    if not turib_sonuc:
        _paragraf(doc, "Bu tarih için TÜRİB arşiv verisi bulunamadı.")
    for cls in TURIB_SINIFLAR:
        s = turib_sonuc.get(cls)
        if not s:
            continue
        u, p = s["ucuz"], s["pahali"]
        _paragraf(doc, cls, kalin=True, sonrakiyle_tut=True)
        _paragraf(doc, f"Ucuz : {u['fiyat']:.2f} TL/kg - {u['lidas']} ({u['il']}/{u['ilce']})", girinti=12, sonrakiyle_tut=True)
        _paragraf(doc, f"Pahalı: {p['fiyat']:.2f} TL/kg - {p['lidas']} ({p['il']}/{p['ilce']})", girinti=12)

    # ---- TMO: en ucuz/en pahali IL ----
    tmo_sonuc, tmo_tarih = tmo_en_ucuz_pahali(conn)
    baslik_tarih = f" ({date.fromisoformat(tmo_tarih).strftime('%d.%m.%Y')})" if tmo_tarih else ""
    _paragraf(doc, f"TMO - En Ucuz / En Pahalı İl{baslik_tarih}", boyut=B + 2, kalin=True)
    if not tmo_sonuc:
        _paragraf(doc, "TMO verisi bulunamadı.")
    for urun, s in tmo_sonuc.items():
        u, p = s["ucuz"], s["pahali"]
        _paragraf(doc, urun, kalin=True, sonrakiyle_tut=True)
        _paragraf(doc, f"Ucuz : {u['fiyat']:.0f} TL/ton - {u['il']}", girinti=12, sonrakiyle_tut=True)
        _paragraf(doc, f"Pahalı: {p['fiyat']:.0f} TL/ton - {p['il']}", girinti=12)

    # ---- TB'ler: 4 borsa arasi en ucuz/en pahali ----
    tb_sonuc = tb_en_ucuz_pahali(conn)
    _paragraf(doc, "Ticaret Borsaları - En Ucuz / En Pahalı (Bandırma/Edirne/Kırklareli/Tekirdağ)", boyut=B + 2, kalin=True)
    if not tb_sonuc:
        _paragraf(doc, "TB verisi bulunamadı.")
    for grup, s in tb_sonuc.items():
        u, p = s["ucuz"], s["pahali"]
        _paragraf(doc, grup, kalin=True, sonrakiyle_tut=True)
        _paragraf(doc, f"Ucuz : {u['fiyat']:.2f} TL/kg - {u['borsa']} ({date.fromisoformat(u['tarih']).strftime('%d.%m.%Y')})", girinti=12, sonrakiyle_tut=True)
        _paragraf(doc, f"Pahalı: {p['fiyat']:.2f} TL/kg - {p['borsa']} ({date.fromisoformat(p['tarih']).strftime('%d.%m.%Y')})", girinti=12)

    conn.close()

    canli_firsatlar = canli_emirler_firsat_tara(klasor)
    if canli_firsatlar:
        _paragraf(doc, "Canlı Emir Defteri - Fırsat Taraması", boyut=B + 2, kalin=True)
        _paragraf(doc, f"(min. {CANLI_EMIR_MIN_ADET:,} kg hacimli en iyi alış/satış emirleri arası fark, "
                        "navlun HARİÇ - taşıma öncesi netleştirilmeli)".replace(",", "."),
                  boyut=B - 2, renk=(120, 120, 120))
        for f in canli_firsatlar:
            _paragraf(doc, f"{f['sinif']} — spread {f['spread_ton']:,.0f} TL/ton".replace(",", "."),
                      kalin=True, sonrakiyle_tut=True)
            _paragraf(doc, f"Satış: {f['ucuz_fiyat']:.2f} TL/kg - {f['ucuz_yer']} ({f['ucuz_adet']:,} kg)".replace(",", "."),
                      girinti=12, sonrakiyle_tut=True)
            _paragraf(doc, f"Alış : {f['pahali_fiyat']:.2f} TL/kg - {f['pahali_yer']} ({f['pahali_adet']:,} kg)".replace(",", "."),
                      girinti=12)

    _paragraf(doc, "Not: Gösterilen veri o günün değil, her kaynağın veritabanındaki EN GÜNCEL "
                    "kaydına ait. Hafta sonu/resmi tatilde borsalar işlem yapmadığı için "
                    "bir önceki iş gününün verisi görünür, bu normaldir.",
              boyut=B - 2, renk=(120, 120, 120))

    docx_yolu = klasor / f"gunluk_ozet_{ad}.docx"
    doc.save(str(docx_yolu))
    print(f"Word yazildi: {docx_yolu}")
    return docx_yolu


def pdf_uret(hedef_tarih: date, klasor: Path, ad: str, ozet: dict):
    docx_yolu = docx_uret(hedef_tarih, klasor, ad, ozet)
    pdf_yolu = klasor / f"gunluk_ozet_{ad}.pdf"
    subprocess.run(
        [SOFFICE_YOLU, "--headless", "--convert-to", "pdf", "--outdir", str(klasor), str(docx_yolu)],
        check=True, capture_output=True, timeout=120,
    )
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
