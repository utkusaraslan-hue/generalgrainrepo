"""TURIB sitesinin tam kesfi: sitemap'ten alinan TUM TR sayfa/post URL'lerini
gezer. Statik sayfalar (page-sitemap) icin tam sayfa ekran goruntusu + metin,
duyuru postlari (post-sitemap) icin sadece metin + sayfadaki PDF linkleri
kaydedilir. Sonuc, Claude'un daha sonra okuyup Excel/mevzuat dosyalarina
ayristirmasi icin JSON + PNG olarak diske yaziliyor.
"""
import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

from playwright.sync_api import sync_playwright

KOK = Path(__file__).parent
# Agir veri (PDF/ekran goruntusu arsivi) git'e alinmiyor - Masaustunde
# saklaniyor (bkz PROJE_GECMISI.md, karar 2026-09-06).
VERI_KOK = Path.home() / "Desktop" / "4-09-2026-turib" / "mevzuat-arsiv"
SS_DIZIN = VERI_KOK / "ekran_goruntuleri"
METIN_DIZIN = VERI_KOK / "sayfa_metinleri"
PDF_DIZIN = VERI_KOK / "pdf_arsiv"
METIN_DIZIN.mkdir(parents=True, exist_ok=True)

SAYFALAR = [l.strip() for l in open("/tmp/turib_all_pages.txt") if l.strip() and "/en/" not in l]
POSTLAR = [l.strip() for l in open("/tmp/turib_all_posts.txt") if l.strip() and "/en/" not in l]


def guvenli_dosya_adi(url: str) -> str:
    yol = urlparse(url).path.strip("/") or "anasayfa"
    ad = re.sub(r"[^a-zA-Z0-9_-]", "_", yol)
    return ad[:120]


def sayfayi_isle(sayfa, url: str, ekran_goruntusu_al: bool) -> dict:
    sonuc = {"url": url, "basarili": False}
    try:
        sayfa.goto(url, wait_until="networkidle", timeout=25000)
    except Exception:
        try:
            sayfa.goto(url, wait_until="domcontentloaded", timeout=25000)
        except Exception as e:
            sonuc["hata"] = str(e)
            return sonuc

    ad = guvenli_dosya_adi(url)
    try:
        sonuc["baslik"] = sayfa.title()
        sonuc["metin"] = sayfa.inner_text("body")
    except Exception as e:
        sonuc["hata"] = f"metin alinamadi: {e}"

    # Sayfadaki PDF linklerini topla
    try:
        pdf_linkler = sayfa.eval_on_selector_all(
            "a[href$='.pdf'], a[href*='.pdf?']",
            "els => els.map(e => e.href)"
        )
        sonuc["pdf_linkler"] = sorted(set(pdf_linkler))
    except Exception:
        sonuc["pdf_linkler"] = []

    if ekran_goruntusu_al:
        try:
            sayfa.screenshot(path=str(SS_DIZIN / f"{ad}.png"), full_page=True, timeout=20000)
            sonuc["ekran_goruntusu"] = f"{ad}.png"
        except Exception as e:
            sonuc["ekran_goruntusu_hata"] = str(e)

    (METIN_DIZIN / f"{ad}.json").write_text(
        json.dumps(sonuc, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    sonuc["basarili"] = True
    return sonuc


def main():
    tum_pdfler = set()
    with sync_playwright() as p:
        tarayici = p.chromium.launch()
        sayfa = tarayici.new_page(viewport={"width": 1440, "height": 900})

        print(f"=== STATIK SAYFALAR ({len(SAYFALAR)}) - ekran goruntulu ===")
        for i, url in enumerate(SAYFALAR, 1):
            r = sayfayi_isle(sayfa, url, ekran_goruntusu_al=True)
            tum_pdfler.update(r.get("pdf_linkler", []))
            print(f"[{i}/{len(SAYFALAR)}] {url} -> {'OK' if r['basarili'] else 'HATA: ' + r.get('hata','?')}")
            time.sleep(0.3)

        print(f"\n=== DUYURU POSTLARI ({len(POSTLAR)}) - sadece metin ===")
        for i, url in enumerate(POSTLAR, 1):
            r = sayfayi_isle(sayfa, url, ekran_goruntusu_al=False)
            tum_pdfler.update(r.get("pdf_linkler", []))
            print(f"[{i}/{len(POSTLAR)}] {url} -> {'OK' if r['basarili'] else 'HATA: ' + r.get('hata','?')}")
            time.sleep(0.2)

        tarayici.close()

    (KOK / "tum_pdf_linkleri.json").write_text(
        json.dumps(sorted(tum_pdfler), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nToplam bulunan PDF linki: {len(tum_pdfler)}")


if __name__ == "__main__":
    main()
