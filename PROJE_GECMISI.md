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

## 2026-09-07 – 2026-09-26 Arası Yapılanlar

### Otomasyon sağlığı / kritik hata düzeltmeleri
- **TMO yerel git kilitlenmesi (4 gün veri kaybı)**: `tmo_yerel_calistir.sh` ve
  `gunluk_ozet_yerel_calistir.sh` "commit → pull --rebase → push" sırasıyla
  çalışıyordu; `borsa_verileri.db` ikili dosya olduğu için GitHub Actions'la
  çakışan rebase, script'i yarım kalmış rebase halinde bırakıyordu (09-04→09-07
  arası TMO verisi commit edilemedi). Düzeltme: her iki script de artık ÖNCE
  pull, SONRA commit yapıyor; yarım kalmış rebase varsa otomatik abort ediyor.
  Detay: bkz [[tmo_yerel_git_rebase_kilitlenmesi]] (Claude hafızası).
- **TÜRİB günlük arşiv otomasyon boşluğu**: `turib_2023_2026_tam/cek.py`
  (LİDAŞ bazlı zenginleştirilmiş Masaüstü JSON arşivini dolduran script)
  otomatik pipeline'dan bağımsızdı, günlerce çalışmadı, `gunluk_ozet` PDF'inin
  "TÜRİB En Ucuz/En Pahalı LİDAŞ" bölümü boş çıkıyordu. `cek.py`'a hızlı
  `--bugun` modu eklendi, `gunluk_ozet_yerel_calistir.sh` her çalışmada bunu
  tetikliyor artık.
- **TDAG (Tekirdağ) dış kaynaklı sessizlik**: 2026-09-03'ten (sonra tekrar
  2026-09-18'den) beri veri yok. URL formülümüz (gün×10+ay) doğrulandı, sorun
  yok — borsa kendi sitesine yeni günlük bülten yüklemiyor. Bizim tarafımızda
  yapılacak bir şey yok.
- **TÜRİB arşivi 2019 kuruluşuna genişletildi**: `cek.py`'nin `BASLANGIC`'i
  2023-01-01'den TÜRİB'in kuruluş tarihi olan 2019-08-01'e çekildi, 856 yeni
  gün geri dolduruldu (74 tatil, 0 hata). `turib_2023_2026_tam/excel_yillik_karsilastirma.py`
  eklendi: tüm arşivi (Normal Seans/Endeks/Anlaşmalı) hem TL hem TCMB kuruyla
  USD'ye çevrilmiş iki Excel'de birleştirir, her satıra (İl+İlçe+LİDAŞ+Sınıf
  bazında) bir önceki yılın aynı takvim gününe göre **YoY Değişim (%)** kolonu
  ekler. Çıktı: `~/Desktop/turib-tarihi/` (kullanıcı sonradan `4-09-2026-turib/`
  içine taşımış olabilir, tam yol için Desktop'ı kontrol et).
- **Canlı emir defteri fırsat taraması**: Kullanıcının gün klasörüne manuel
  eklediği "İşlemGörenler_*.xlsx" (TÜRİB'in canlı alış/satış emir defteri
  exportu) `gunluk_ozet`'e otomatik entegre edildi — min. 10.000 kg hacimli
  en ucuz satış/en pahalı alış emri arasındaki ham spread'i (navlun hariç)
  PDF'e ekliyor.

### Finansman araştırması ve araçları
- **Esnaf Kefalet Kredisi**: Hazine destekli, ~%20/yıl (aylık ~%1,67), EKK
  üyeliği + Halkbank istihbaratı gerekiyor. Vade: işletme kredisi 48 ay,
  işyeri edindirme 72 ay, araç alımı 60 ay. **Kesin: 3 ayda bir (çeyreklik)
  taksitli**, aylık değil (kullanıcı teyitli). Erken kapamada resmi bir ceza
  yok, kalan vadenin faizi düşüyor (sadece kalan anapara + o ana kadar
  tahakkuk eden faiz ödeniyor).
- **ELÜS Karşılığı Kredi**: bkz [[elus_kredisi_faiz_destegi]] (Claude
  hafızası) — 2018/11188 sayılı BKK kapsamında Ziraat Bankası/Tarım Kredi
  Kooperatifleri üzerinden senet tutarının **%75'ine kadar, azami 9 ay
  vadeli, %100 faiz indirimli (efektif %0)**, **vade sonunda tek seferde
  (spot)** geri ödeniyor. İş Bankası'nın kendi ticari ELÜS ürünü ayrı bir
  şey (max %80 LTV, faiz oranı teyit edilmedi) — ikisi karıştırılmamalı.
- **Hesaplayıcılar** (`~/Desktop/sariaslanticaret/` altına taşınmış):
  - `finansman_plani.xlsx` — ELÜS(%75,spot,%0) + Esnaf(%25,çeyreklik) 4 vade
    senaryosu karşılaştırması + Temmuz başlangıçlı 12 aylık ödeme takvimi.
  - `elus_esnaf_erken_kapama_hesaplayici.xlsx` — tek girdili (anapara) canlı
    formül şablonu, erken kapama senaryosu (amortisman tablosu + toplam
    faiz) otomatik hesaplıyor.
  - `mali_tablolar_sablonu.xlsx` — 5 sayfa: Gelir-Gider Tablosu (aylık),
    Bilanço (Aktif=Pasif kontrolü ile), Nakit Akışı Tablosu (aylık zincirleme),
    Kredi ve Mevduat Planı (Esnaf 1,5mn + İşbank ELÜS 1,2mn + mevduat 48
    aylık takvim), Günlük Kayıt Defteri.
  - **"Mali Takip Sistemi" artifact** (canlı web uygulaması, `db`+`downloads`
    capability) — basit gelir-gider yerine gerçek hesap bazlı sistem: 12
    işlem şablonu (Kredi Çekildi, Kredi Taksidi, Ürün Satışı/Alımı,
    Mevduat hareketleri, vb.) her biri otomatik olarak 2 hesabı (Kasa,
    Kredi Borcu, Satış Geliri...) birlikte hareket ettiriyor — kullanıcı
    çift-kayıt mantığını bilmeden gerçekçi bilanço/gelir-gider tutabiliyor.
    "Kredi Tanımları ve Ödeme Takvimi" paneli, tanımlanan kredi parametrelerinden
    (tutar/faiz/vade) otomatik amortisman takvimi çıkarıp gerçek ödemelerle
    eşleştiriyor (kaç taksit ödendi, sıradaki ne zaman). Excel'e Aktar butonu
    3 sekmeli (Bilanço/Gelir-Gider/İşlem Kayıtları) gerçek `.xlsx` üretiyor.
    URL kullanıcıda kayıtlı, gerekirse `Artifact action:list` ile bulunabilir.

### Analiz
- **"Dolar Bazlı Tahıl Seyri" artifact**: TÜRİB'in 4 ana endeksinin (Hububat/
  Buğday/Arpa/Mısır) 2019-2026 dolar bazlı (TCMB kuruyla arındırılmış) seyri.
  Bulgular: toplam %22-44 arası reel artış (yıllık bileşik %2,9-5,3); üç ortak
  makro dönüm noktası (2020-04 Kovid dibi, 2021-12 ve 2023-06 kur şoku kaynaklı
  ~%25-26 ani düşüşler, 2022-05/07 Ukrayna savaşı zirvesi); mevsimsellik
  buğday/arpa'da Temmuz-Ağustos dip/Kasım-Aralık zirve, Mısır'da TAM TERSİ
  (Kasım-Ocak dip/Nisan-Haziran zirve) — hasat takvimi farkından (~3 ay kayma).
- Bu mevsimsel pencereler (Buğday: Temmuz al→Kasım sat, Mısır: Ocak al→Mayıs
  sat) üzerinden kötü/olası/iyi kâr marjı senaryoları çıkarıldı (±1 std bandı).

## Bilinen Açık Sorular

- TDAG'in gizli günlük PDF URL formülü (gün×10+ay) Ekim-Aralık (2 haneli ay)
  için henüz doğrulanmadı.
- Yeni eklenen 4 borsa (Bandırma/ETB/ETB_AYLIK/Kırklareli/TDAG) fetcher'ları
  GitHub Actions'ın bulut IP'lerinden henüz test edilmedi — TMO gibi
  engellenebilirler, ilk birkaç otomatik çalıştırma kontrol edilmeli.
- TS/GMS/TBOA/TBOS gibi bazı satış şekli kısaltmalarının kesin açılımı
  hâlâ teyit edilemedi.
