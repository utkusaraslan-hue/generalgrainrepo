# TÜRİB Ücret/Fire Hesaplama Kuralları ve Prosedürleri (Metinsel Özet)

Sayısal tarife tabloları `turib_ucret_tarifeleri_ve_veriler.xlsx` dosyasında.
Bu dosya, o rakamların **nasıl hesaplandığını ve hangi kurala göre uygulandığını** anlatır.

## 1. Lisanslı Depo Ücreti (depo kirası)

- Ürün depoda kaldığı süre kadar **satıcı** tarafından depo işletmesine ödenir.
- ELÜS TÜRİB'de el değiştirdiğinde **satıcıdan**, ürün iade/teslim aşamasında (ELÜS iptali) **alıcıdan** tahsil edilir.
- Tarife Ticaret Bakanlığı onayı ile Türkiye Ticaret Sicil Gazetesi'nde (TTSG) yayımlanır; yayım tarihinde yürürlüğe girer.
- Her yıl Ocak ayında TÜİK'in yıllık ÜFE+TÜFE ortalaması oranında güncellenir (Bakanlık bu oranı yarıya kadar azaltabilir; hububat/baklagil/yağlı tohum dışındaki ürünlerde farklı oran uygulayabilir).
- **Formül:**
  ```
  Depo Ücreti = (ELÜS Miktarı) × (Yönetmelik Yürürlük Tarihine Kadarki Depo Gün) × (Teslim Tarihindeki Tarife)
              + (ELÜS Miktarı) × (Yürürlükten Satışa Kadarki Depo Gün) × (Güncel Tarife)
  ```
  (parçalı hesaplama - birden fazla tarife dönemi varsa her biri ayrı hesaplanır)
- KDV: 10.07.2023'e kadar %18, sonrasında %20.
- Ödeme: Takasbank tarafından satış bedelinden mahsup edilip depo işletmesinin Takasbank hesabına aktarılır.

## 2. Kira Desteği (devlet desteği, depo ücretinin bir kısmını devlet karşılıyor)

- 24.08.2024 tarih 32647 sayılı RG, 8859 sayılı CB Kararı.
- Buğday/Arpa/Yulaf/Çavdar/Mısır/Çeltik-Pirinç + diğer listelenen ürünler: Bakanlık kira tarifesinin **%75'i** (2025-2027 dönemi).
- Koşul: ÇKS'ye kayıtlı üreticiler, üretici birlikleri (5200 sayılı Kanun), tarım kredi kooperatifleri (1581 sayılı Kanun), kooperatifler (1163 sayılı Kanun), tarım satış kooperatifleri (4572 sayılı Kanun).
- Süre: en fazla **6 ay**, 2025/2026/2027 üretim yılı ürünleri için.
- ÖNCEKİ DÖNEM (2024 duyurusu): oran %60 idi, ürüne göre 4-5,5 kat artışla bu seviyeye çıkarıldı.

## 3. Fire (ağırlık kaybı) Kesintisi

- Ürün depoda tutulurken doğal olarak ağırlık kaybeder (iklim, tür, süre vb.); bu kayıp Bakanlık'ın belirlediği fire tarifesine göre **işlem bazında** kesilir.
- Fiziki teslim sırasında, önceden mahsup edilmemiş fire miktarı üründen düşülerek teslim yapılır.
- **Hububat/Baklagil/Yağlı Tohum:** 365 güne kadar fire oranı %0,35 (günlük katsayı 0,000009589041). Süre, ilgili ISIN için oluşturulan ilk ELÜS ihraç tarihinden itibaren işler.
- **Fındık:** 730 güne kadar fire oranı %1 (günlük katsayı 0,00001369863).
- **Formül:** `Fire Ücreti = ELÜS Miktarı × İşlem Fiyatı × Fire Oranı × Fire Gün / (365 veya 730)`
  eşdeğer: `= ELÜS Miktarı × İşlem Fiyatı × Fire Gün × Günlük Fire Katsayısı`
- `Fire Miktarı (teslimde düşülecek) = Günlük Fire Katsayısı × Fire Gün × Ürün Miktarı`
- Ödeme: Takasbank tarafından satış bedelinden mahsup edilir.
- **Fire sınırı aşılırsa** (bozulma, zayi, nitelik kaybı, sigorta kapsamı dışıysa): mudi yazılı başvurur, depo işletmesi **en geç 7 iş günü içinde** aynı nitelik/miktarda ürünü temin edip teslim eder YA DA son 5 işlem gününün (yoksa son 30 günün) ağırlıklı ortalama fiyatının **%5 fazlasını** öder. Bu durumda ürün senedi iptal edilir, ürün depodan çıkarılır.

## 4. ELÜS İşlem Ücretleri (TÜRİB'de alım-satımda kesilen komisyonlar)

Her ELÜS işleminde, takasın gerçekleştiği anda, **işlemin HER İKİ TARAFINDAN** (alıcı ve satıcı ayrı ayrı), işlem tutarı üzerinden:

| Ücret | Oran | KDV |
|---|---|---|
| Borsa Tescil Ücreti | Binde 0,25 | +KDV |
| Borsa Hizmet Ücreti | Binde 1,25 | +KDV |
| Lisanslı Depoculuk Tazmin Fonu Payı | Binde 0,25 | KDV yok |

Toplam oran (tek taraf, KDV hariç): binde 1,75 = %0,175. KDV dahil (tescil+hizmet için %20): efektif ~binde 2,05.
1.000.000 TL'lik bir işlemde TEK TARAF öder: 300 (tescil+KDV) + 250 (tazmin fonu) + 1.500 (hizmet+KDV) = **2.050 TL**.

## 5. Kantar / Seviye Ölçüm Sistemi Ücreti (2026 - YENİ)

- 27/8/2025 tarih 32999 sayılı RG ile Tarım Ürünleri Lisanslı Depoculuk Yönetmeliği md.17 değişti: TÜRİB "Lisanslı Depo Bilgi Sistemi" kuracak, ilk modül "Seviye Ölçüm Sistemi" (hububat/baklagil/yağlı tohum depolarında miktar tespiti).
- Sistemin toplam yazılım+kurulum maliyeti depo işletmelerine paylaştırılıyor: **Lisans Kapasitesi (ton) × 5,31 TL/ton** (vergi dahil).
- Ödeme son tarihi: 27.02.2026 mesai bitimi (bu tarihten sonra izin alacaklar için TÜFE farkı yansıtılır).
- Gecikme zammı: `Gecikme Zammı = Geciken Tutar × (Aylık TÜFE Oranı / Ay Gün Sayısı) × Gecikilen Gün`
- Ölçüm cihazlarının (sensör vb.) kurulumu depo işletmesinin sorumluluğunda; kriterler yürürlüğe girdikten sonra **6 ay içinde** kurulmalı. Ödemeyi yapmayan veya cihazı kurmayan işletmenin **lisansı askıya alınır ve teminatı artırılır**.

## 6. Nakliye ve Analiz Destekleri (çiftçiye devlet desteği)

- Nakliye desteği: Buğday/Arpa/Yulaf/Çavdar/Mısır/Çeltik-Pirinç için **100 TL/ton** (üst sınır 30 ton); diğer ürünler (mercimek, nohut, fasulye, soya, ayçiçeği, pamuk, zeytin, fındık, antep fıstığı, kuru kayısı/üzüm) için **300 TL/ton** (üst sınır 10 ton).
- Analiz desteği: Bakanlık analiz ücret tarifesinin %50'si, sadece ürün girişi analizinde.
- Bu üç destek (kira/nakliye/analiz) 2024'te önemli oranda artırıldı (kira 4-5,5 kat, analiz 1,7-3,3 kat, nakliye 3-4 kat).

## 7. ELÜS'e Yönelik Vergi/Kredi Avantajları

- Lisanslı depoda saklanan ürünlerin alım/satım gelirleri **2028 yıl sonuna kadar** gelir vergisi (zirai kazanç dahil) ve kurumlar vergisinden muaf; ayrıca damga vergisi ve KDV'den istisna.
- Ziraat Bankası: ELÜS tutarının **%75'ine kadar**, azami **9 ay vadeli sıfır faizli kredi**.

## 8. ELÜS ISIN Kod Yapısı (12 haneli)

`TRXABCI11901` örneği: 1-2 ülke kodu (TR), 3 menkul kıymet türü (X=ELÜS), 4-6 depo işletmesi şube kodu, 7 ürün harfi (A=Arpa, B=Buğday...), 8 aynı ihraçtaki sıra no, 9-10 ihraç yılı son 2 hane, 11 ihraç sıra no (Takasbank artırır), 12 kontrol hanesi (otomatik).

ISIN kodu tahsis bedeli: 100 TL+BSMV → 12.02.2020'den itibaren **50 TL+BSMV** olarak indirimli.

## 9. Borsa Üyelik Ücretleri (aracı kurumlar için, 2026)

| Kalem | Tutar (KDV hariç) |
|---|---|
| Üyelik Kayıt Ücreti (ilk giriş) | 812.780 TL |
| Yıllık Üyelik Aidatı | 541.853 TL |
| Üyelik Teminatı | 541.853 TL (2026 sonuna kadar alınmayacak) |

Her yıl Ocak ayında VUK mük. 298/B yeniden değerleme oranında artırılır.

## 10. Veri Yayım Hizmeti Ücretleri (2026, veri dağıtım şirketleri için)

Paket 0/1/2/3 ve TV-Web paketi var; Paket 2 ve 3'te kullanıcı sayısına göre kademeli fiyatlandırma + aşım bedeli. Detaylar Excel'de "Veri Yayim Ucret Tarifesi" sekmesinde. 01.01.2027'den itibaren TÜFE ile güncellenir.

---
**Kaynaklar:** Tüm bilgiler `~/yine-bi-agent/turib_site_incelemesi/sayfa_metinleri/*.json` (ham sayfa metinleri) ve `pdf_arsiv/` (indirilen 310 PDF) içinden doğrudan alınmıştır. Her bölümün kaynak URL'si Excel dosyasındaki ilgili sekmede belirtilmiştir.
