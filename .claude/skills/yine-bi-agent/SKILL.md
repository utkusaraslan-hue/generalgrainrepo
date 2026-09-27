---
name: yine-bi-agent
description: Türkiye tahıl borsası (TÜRİB/TMO/il borsaları) fiyat takip pipeline'ı ve Sarıaslan Ticaret'in mali/finansman araçları için operasyonel rehber — durum kontrolü, git güvenlik kuralları, Excel/artifact konumları
---

# Yine Bi Agent — Operasyonel Rehber

Bu skill, `~/yine-bi-agent` reposundaki tahıl borsası veri pipeline'ı ve
kullanıcının (Sarıaslan Ticaret, tahıl trading) mali takip araçlarıyla
ilgili işlerde referans alınacak özet bilgidir. Tam anlatı/kronoloji için
`PROJE_GECMISI.md`'ye, ince ayrıntılar için Claude'un kendi hafıza dosyalarına
(`[[isim]]` referansları) bak.

## İşe başlarken her zaman yap

1. `cd ~/yine-bi-agent && git pull --rebase origin main` — repo GitHub
   Actions + yerel launchd job'ları tarafından günde birkaç kez commit
   ediliyor, güncel olmayan repo üzerinde çalışma.
2. Pipeline durumu sorulursa: `sqlite3 veri_kaynagi/borsa_verileri.db
   "SELECT kaynak, MAX(tarih) FROM fiyatlar GROUP BY kaynak;"` ve
   `gh run list --workflow=gunluk-veri-cek.yml --limit 5`.

## KRİTİK: git güvenlik kuralı (binary DB)

`veri_kaynagi/borsa_verileri.db` ikili (binary) bir dosya — git bunu
metin gibi merge EDEMEZ. İki bağımsız otomasyon (GitHub Actions cloud +
TMO'nun yerel launchd job'ı) aynı dosyaya düzenli commit atıyor. Kural:
**HER ZAMAN önce `git pull --rebase`, SONRA commit** — asla tersi değil.
Eğer `.git/rebase-merge/` veya `.git/rebase-apply/` yarım kalmış bulursan,
önce `git rebase --abort` ile temizle, ASLA üstüne commit atmaya çalışma.
Çatallanma (iki taraf da benzersiz veri içeriyorsa) çözümü: `git log
A..B` ile hangi commit'lerin nerede benzersiz olduğunu bul, `sqlite3`
ATTACH ile SQL düzeyinde satır bazlı birleştir (git merge değil), sonra
`git reset --hard origin/main` + birleşik db'yi elle yerleştir. Detay:
proje hafızasında `tmo_yerel_git_rebase_kilitlenmesi`.

## Bilinen kalıcı/dış kaynaklı durumlar (rapor etme, sadece bilgilendir)

- **TDAG (Tekirdağ)**: borsa kendi sitesine bülten yüklemezse veri
  gelmiyor — bizim URL formülümüzde (gün×10+ay) sorun yok, doğrulandı.
- **TMO**: bülten 1 iş günü gecikmeli yayınlanıyor, hafta sonu/tatilde
  aynı kalması normal. Sadece yerel Mac'te çekilebiliyor (GH Actions'ın
  bulut IP'leri TMO tarafından engelli).
- **Kırklareli, ETB_AYLIK**: sadece aylık bülten, "son güncel ay" mantığıyla
  çalışıyor, uzun süre aynı tarihte kalması normal olabilir.

## Excel üretirken

`excel_raporlar/borsa_takip_excel_uret.py`'deki `sayfayi_bicimlendir()`
kalıbını kullan: Verdana 10pt, Finansal ₺ format (₺ önek, `_-"₺"*
#,##0.00_-;...` gibi gerçek accounting format — düz `#,##0.00" TL"`
DEĞİL), gerçek tarih tipi (metin değil), AutoFilter, otomatik sütun
genişliği. Kullanıcının elle düzenlediği dosyaların (`~/Desktop/
borsa_takip_arpa_bugday_misir.xlsx` gibi) üzerine sormadan yazma.

## Mali/finansman araçları — konumlar

- `~/Desktop/sariaslanticaret/` — finansman_plani.xlsx, elus_esnaf_erken_
  kapama_hesaplayici.xlsx, mali_tablolar_sablonu.xlsx (5 sayfa: Gelir-Gider/
  Bilanço/Nakit Akışı/Kredi-Mevduat Planı/Günlük Kayıt Defteri).
- **"Mali Takip Sistemi" artifact** (canlı, `db`+`downloads` capability) —
  hesap bazlı (çift-kayıt benzeri) gerçek gelir-gider/bilanço takibi + kredi
  vade takvimi. URL için `Artifact action:list` kullan, kullanıcı Desktop'a
  Excel export de indirmiş olabilir (`mali_takip_*.xlsx`).
- ELÜS kredisi: %75'e kadar, 9 ay, %0 faiz (2018/11188 sayılı BKK, Ziraat/
  Tarım Kredi Kooperatifleri üzerinden) — İş Bankası'nın kendi ticari ELÜS
  ürünüyle (max %80 LTV, oranı teyitsiz) KARIŞTIRMA, ikisi farklı ürün.
- Esnaf Kefalet Kredisi: ~%20/yıl, **3 ayda bir (çeyreklik) taksitli**
  (aylık değil — kullanıcı kesin teyitli), vade 48/60/72 ay (amaca göre).

## TÜRİB tarihsel veri

`turib_2023_2026_tam/cek.py` (arşiv 2019-08-01'den başlıyor, `--bugun`
modu günlük otomasyona bağlı) ve `excel_yillik_karsilastirma.py` (TL+USD,
YoY Değişim % kolonlu) — USD çevirimi için önce `tcmb_kur_cek.py` ile kur
cache'i güncel tarihe kadar genişletilmiş olmalı.

## Derinlemesine araştırma disiplini

Yeni bir borsa/kaynak keşfederken "kaynak yok" demeden önce her linki
gerçekten aç — ETB_AYLIK ilk keşifte kaçırılmıştı, kullanıcı örnek URL
verince bulundu. Bkz proje hafızası: `borsa_kesiflerinde_derinlemesine_arastir`.
