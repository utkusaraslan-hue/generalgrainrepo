"""TURIB Gunluk Bulten: Endeks Verileri + Normal Seans sekmeleri.

Sayfa GET'te bos gelir; tarihi form olarak POST etmek gerekiyor. Sunucu HTML
donuyor (JS/AJAX degil), bu yuzden BeautifulSoup ile tablo parse ediliyor.
"""
from datetime import date

import requests
from bs4 import BeautifulSoup

from ..utils import TARAYICI_BASLIKLARI, simdi_iso, tr_sayi

BULTEN_URL = "https://www.turib.com.tr/gunluk-bulten/"


def _sayfayi_getir(tarih: str) -> str:
    r = requests.post(
        BULTEN_URL,
        data={"getbulletin_date": tarih, "submit": "Listele"},
        timeout=30, verify=False, headers=TARAYICI_BASLIKLARI,
    )
    r.raise_for_status()
    return r.text


def _tabloyu_oku(soup: BeautifulSoup, panel_id: str) -> list[dict]:
    """TURIB'in bulten tablolarinda <tr> etiketleri kapatilmiyor; bu yuzden
    BeautifulSoup satirlari icice yerlestiriyor. Guvenilir yol: <td>'leri
    tbody altindan duz sirayla cekip baslik sayisina gore gruplamak."""
    panel = soup.find(id=panel_id)
    if not panel:
        return []
    tablo = panel.find("table")
    if not tablo:
        return []
    basliklar = [th.get_text(strip=True) for th in tablo.find("thead").find_all("th")]
    hucreler = [td.get_text(strip=True) for td in tablo.find("tbody").find_all("td")]
    n = len(basliklar)
    satirlar = []
    for i in range(0, len(hucreler) - n + 1, n):
        satirlar.append(dict(zip(basliklar, hucreler[i:i + n])))
    return satirlar


def _endeks_kayitlarina_donustur(satirlar: list[dict], tarih: str) -> list[dict]:
    kayitlar = []
    for s in satirlar:
        kayitlar.append({
            "kaynak": "TURIB_ENDEKS",
            "tarih": tarih,
            "il": None, "ilce": None,
            "urun": s.get("Endeks Adı"),
            "detay": s.get("Endeks Kısa Kodu"),
            "min_fiyat": tr_sayi(s.get("En Düşük")),
            "ort_fiyat": None,
            "max_fiyat": tr_sayi(s.get("En Yüksek")),
            "kapanis_fiyat": tr_sayi(s.get("Kapanış")),
            "miktar": tr_sayi(s.get("İşlem Miktarı [KG]")),
            "birim": "KG",
            "ham_veri": s,
            "cekilme_zamani": simdi_iso(),
        })
    return kayitlar


def _normal_seans_kayitlarina_donustur(satirlar: list[dict], tarih: str) -> list[dict]:
    kayitlar = []
    for i, s in enumerate(satirlar):
        # ISIN kodu + Isletme Kodu satir bazinda benzersiz degil, ayni ISIN'de
        # birden fazla islem olabiliyor; benzersizlik icin sira no ekliyoruz.
        detay = f"{s.get('ISIN Kodu')}#{s.get('İşlem Kodu') or i}"
        kayitlar.append({
            "kaynak": "TURIB_NORMAL_SEANS",
            "tarih": tarih,
            "il": s.get("İl"),
            "ilce": s.get("İlçe"),
            "urun": s.get("Enstrüman Sınıfı"),
            "detay": detay,
            "min_fiyat": tr_sayi(s.get("En Düşük Fiyat")),
            "ort_fiyat": tr_sayi(s.get("Ağırlıklı Ortalama Fiyat")),
            "max_fiyat": tr_sayi(s.get("En Yüksek Fiyat")),
            "kapanis_fiyat": tr_sayi(s.get("Kapanış Fiyatı")),
            "miktar": tr_sayi(s.get("İşlem Miktarı [KG]")),
            "birim": "KG",
            "ham_veri": s,
            "cekilme_zamani": simdi_iso(),
        })
    return kayitlar


def cek(tarih: str | None = None) -> list[dict]:
    tarih = tarih or date.today().isoformat()
    tarih_us = tarih  # form YYYY-MM-DD bekliyor
    html = _sayfayi_getir(tarih_us)
    soup = BeautifulSoup(html, "html.parser")

    endeks = _tabloyu_oku(soup, "nav-home2")
    normal_seans = _tabloyu_oku(soup, "nav-home")

    return (_endeks_kayitlarina_donustur(endeks, tarih)
            + _normal_seans_kayitlarina_donustur(normal_seans, tarih))
