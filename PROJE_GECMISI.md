# Proje Geçmişi

Bu dosya, Türkiye tarım ürünü borsa fiyatları takip projesinde yapılan çalışmaların
kronolojik özetidir. (Claude'un kendi konuşma-hafızasından ayrı olarak, repoya
commit'lenen kalıcı bir kayıt tutmak için oluşturuldu.)

## Amaç

TMO/TÜRİB/il borsalarının günlük fiyat bültenlerini tek bir SQLite veritabanında
toplamak, mümkün olduğunca çok ili/borsayı bağlamak, sonra bu verilerle analiz
(arbitraj, tahmin, raporlama) yapmak.

## Mimari

- `veri_kaynagi/` — Python + SQLite pipeline. Tek normalize tablo (`fiyatlar`).
  - `fetchers/` — her kaynak için ayrı modül, ortak sözleşme: `cek(tarih) -> list[dict]`
  - `main.py` — orkestratör, "boşluk doldurma" modu (her kaynağın son tarihinden
    bugüne kadar eksik günleri otomatik tamamlar)
  - `db.py` — idempotent upsert (aynı gün tekrar çekilirse üzerine yazar, çoğalmaz)
- `.github/workflows/gunluk-veri-cek.yml` — GitHub Actions, günde 2 kez
  (**07:00 ve 21:00 TRT**) TÜRİB/Konya/Bandırma/ETB/ETB_AYLIK/Kırklareli/TDAG'ı
  çekip repoya commit'ler.
- `veri_kaynagi/tmo_yerel_calistir.sh` + launchd (`~/Library/LaunchAgents/com.yinebiagent.tmo-veri.plist`)
  — TMO, GitHub Actions'ın bulut IP aralığını (Azure) engellediği için SADECE
  kullanıcının Mac'inde yerel olarak çalışıyor, günde 2 kez (**14:30 ve 20:00
  yerel saat** — TMO bülteni ~13:30 TRT'de yayınlandığı için 07:00'de çalıştırmanın
  anlamı yok, bir önceki günün bayat verisini tekrar çeker).
- `excel_raporlar/borsa_takip_excel_uret.py` — TÜRİB+TMO+4 borsa verisini tek
  Excel'de (sadece buğday/arpa/mısır) raporlayan, kullanıcının elle onayladığı
  tasarım kurallarını uygulayan script.

## Veri Kaynakları

| Kaynak | Kod | Çözünürlük | Backfill | Not |
|---|---|---|---|---|
| TMO | `TMO` | Günlük | Yok (PDF arşivlenmiyor) | Bülten 1 gün gecikmeli, GH Actions'tan engelli, sadece yerel |
| TÜRİB | `TURIB_ENDEKS`, `TURIB_NORMAL_SEANS` | Günlük | Var | Endeks + ISIN/sınıf bazlı işlem detayı |
| Konya | `KONYA` | Günlük | Var | Alpata SPA API |
| Bandırma | `BANDIRMA` | Günlük | Var (tam) | Ayrı ASP.NET/DevExtreme sistem, en iyi kaynak |
| Edirne (canlı) | `ETB` | Sadece "şu an" | Yok | Alpata SPA, tarih param'ı yok sayılıyor |
| Edirne (aylık arşiv) | `ETB_AYLIK` | Aylık | Var (2005-2026) | İlk taramada kaçırılmıştı, kullanıcı PDF örneği verince bulundu |
| Kırklareli | `KIRKLARELI_AYLIK` | Aylık | Yok (eklenebilir) | Sadece PDF, ay bittikten 2-3 hafta sonra yayınlanıyor |
| Tekirdağ | `TDAG` | Günlük | Var (tam) | Gizli PDF URL şeması (gün×10+ay) çözüldü |

## Önemli Teknik Kararlar / Bulgular

1. **Fiyat birimi tutarlılığı**: TÜRİB/TMO/Bandırma/TDAG/ETB(canlı) kaynakları
   ham veride TL/KG kullanıyor; Kırklareli ve ETB_AYLIK PDF'leri TL/TON
   kullanıyor (nokta = bin ayracı, ondalık yok). Fetcher'larda 1000'e bölünerek
   hepsi TL/KG'ye normalize edildi (2026-09-05'te bulunan bug, kullanıcı fark etti).

2. **Navlun modeli**: `TL/sevkiyat = 4.416 (sabit) + 81,79 × km (değişken)`,
   27 ton (dorse) varsayımıyla `navlun_modeli/navlun_formulu.py`'de genelleştirildi
   (km + ton hassasiyetli, 3 yük bandı).

3. **TÜRİB fiyat tahmini**: SARIMA (haftalık, m=52 mevsimsellik aranarak) ile
   buğday/mısır/arpa/hububat endeksleri için Mayıs 2027'ye kadar tahmin +
   backtest ile kalibre edilmiş güven aralıkları üretildi
   (`~/Desktop/turib_fiyat_tahmini_2027_mayis.xlsx`,
   `~/Desktop/turib_enstruman_tahmini_2027_mayis.xlsx` — enstrüman bazlı).
   Arpa ve Mısır 1.Sınıf'ta backtest güvenilirliği düşük çıktı (bkz Excel'deki
   "Özet ve Risk" sayfası).

4. **Satış şekli kısaltmaları**: TOBB'un merkezi resmi listesi
   (`borsa.tobb.org.tr/islem_turu.php`) + ETB'nin kendi yayınladığı legend
   (`etb.org.tr/aylikbulten/aylik-bulten`) bulundu, geri kalan borsaya-özgü
   kısaltmalar (TS, GMS, vb.) bağlamdan tahmin edildi ve "güvenilirlik" etiketiyle
   işaretlendi (`excel_raporlar/borsa_takip_excel_uret.py` içindeki
   `SATIS_SEKLI_ACIKLAMA` sözlüğü).

5. **TMO'nun TÜRİB kimliği**: TMO kendi adına değil "TMO TOBB Tarım Ürünleri
   Lisanslı Depoculuk Sanayi ve Ticaret A.Ş." LİDAŞ adı altında işlem yapıyor,
   8 depo kodu (XFW, XHB, XHN, XFV, XED, XGY, TTD, XEE).

6. **KZ ISIN kısıtlaması** (henüz çözülmedi): TMO'nun TÜRİB serbest satışından
   çıkan bazı ISIN'ler borsada tekrar satılamıyor (ÜPAK'tan sözlü teyitli, resmi
   kaynakta yok). Depo değişikliğinin bunu çözüp çözmediği belirsiz.

## Excel Rapor Tasarım Kuralları (2026-09-05'te kullanıcı onaylı)

- Her "veri" sayfasında AutoFilter açık, referans/açıklama sayfalarında kapalı
- Başlık satırı: Verdana, bold, ortalı, ince kenarlık, mavi dolgu (`4472C4`)
- Veri satırları: Verdana, 10pt
- Fiyat sütunları: Finansal (Muhasebe) biçimi, **₺ sembolü önek** olarak
  (düz "TL" yazısı değil — Excel/Numbers'ın "Finansal" kategorisine düşmesi için)
- Tutar (TL) sütunu: Finansal biçim + "TL" son eki
- Miktar/Hacim/İşlem Sayısı: Finansal tam sayı biçimi (ondalık yok)
- Tarih sütunu: GERÇEK tarih tipi (metin değil) — `dd.mm.yyyy` görünümlü,
  böylece kronolojik sıralama/filtre doğru çalışıyor
- Sütun genişlikleri içeriğe göre otomatik
- Sadece buğday/arpa/mısır ürünleri (kanola/ayçiçek/saman vb. hariç)

Uygulama: `excel_raporlar/borsa_takip_excel_uret.py`. **Kullanıcının elle
düzenlediği `~/Desktop/borsa_takip_arpa_bugday_misir.xlsx` dosyası ÜZERİNE
otomatik yazılmıyor** — üstüne yazmadan önce mutlaka sorulmalı, çünkü kullanıcı
o dosyada elle ek düzenlemeler yapmış olabilir.

## Bilinen Açık Sorular

- TDAG'in gizli günlük PDF URL formülü (gün×10+ay) Ekim-Aralık (2 haneli ay)
  için henüz doğrulanmadı.
- Yeni eklenen 4 borsa (Bandırma/ETB/ETB_AYLIK/Kırklareli/TDAG) fetcher'ları
  GitHub Actions'ın bulut IP'lerinden henüz test edilmedi — TMO gibi
  engellenebilirler, ilk birkaç otomatik çalıştırma kontrol edilmeli.
- TS/GMS/TBOA/TBOS gibi bazı satış şekli kısaltmalarının kesin açılımı
  hâlâ teyit edilemedi.
