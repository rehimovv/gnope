# Gnope: Proje Tanımı ve Plan

> Durum: **Taslak, onay bekliyor.** Bu belge onaylanana kadar kod yazılmayacak.

---

## BÖLÜM 1: Ne yapmak istiyorum? (Detaylı proje tanımı / prompt)

### 1.1 Kim, neden?
Ben GNOME'a gönüllü olarak çeviri desteği veren bir çevirmenim. GNOME çevirileri
Damned Lies (l10n.gnome.org) üzerinden `.po` dosyalarıyla yapılıyor. Bu iş şu an
bilgisayara Gtranslator veya Poedit gibi bir program kurmayı gerektiriyor. Bu da
yeni gönüllülerin katılmasını zorlaştırıyor, telefondan ise çeviri yapmak neredeyse
imkânsız.

Bu yüzden **dünyadaki herkesin ücretsiz kullanabileceği**, **açık kaynak** bir
Telegram botu yapmak istiyorum. Bot, GNOME'u ve diğer açık kaynak projelerin
çeviri topluluklarını desteklemek amacıyla üretildiğini açıkça belirtecek.

### 1.2 Botun temel mantığı (basit ama iş gören)
Bot üç adımdan ibaret olacak:

1. **Dosyayı gönder:** Kullanıcı `.po` (veya `.pot`) dosyasını Telegram'dan bota gönderir.
2. **Çevir:** Bot çevrilecek metinleri Gtranslator/Poedit mantığıyla **tek tek**
   gösterir, kullanıcı her birinin çevirisini yazar.
3. **İndir:** Kullanıcı "Kaydet" dediğinde bot, çevirileri işlenmiş ve **başlığı
   (header) düzeltilmiş** `.po` dosyasını geri gönderir. Kullanıcı bu dosyayı
   doğrudan Damned Lies'a veya projeye yükleyebilir.

**Kesinlikle olmayacaklar:**
- Damned Lies'tan ya da başka bir yerden otomatik dosya çekme (API, link vb.) yok.
- Damned Lies'a otomatik yükleme yok. Bot hiçbir şifre veya hesap bilgisi istemez.
- Karmaşık ayarlar yok. Bot herkesin ilk denemede anlayacağı kadar sade olacak.

### 1.3 İlk karşılama ve dil seçimi
- Bot ilk açıldığında (`/start`) kullanıcıyı **İngilizce** karşılar.
- Hemen arayüz dilini sorar. Üç dil var:
  - 🇬🇧 English
  - 🇹🇷 Türkçe
  - 🇦🇿 Azərbaycanca
- Seçilen dil hatırlanır. Bundan sonra botun tüm mesajları ve butonları o dilde olur.
- Kullanıcı dili istediği zaman `/language` ile değiştirebilir.
- Karşılama mesajı botun **GNOME çeviri topluluğunu desteklemek için gönüllü
  olarak üretildiğini** söyler.

### 1.4 Kısa profil (bir kez sorulur)
Çevrilmiş dosyanın başlığına çevirmenin bilgisi yazılmalı (GNOME bunu bekliyor).
Bu yüzden ilk kullanımda bot şunları sorar:
- **Ad Soyad:** `Last-Translator` alanı için
- **E-posta:** `Last-Translator` alanı için (GNOME geleneği)
- **Çeviri dili:** Çevirilerin yapılacağı dil (ör. `az`, `tr`, `de`). Bu, arayüz
  dilinden ayrıdır. Arayüzü İngilizce kullanıp Almancaya çeviri yapmak mümkün olmalı.

Bu bilgiler `/profile` ile değiştirilebilir.

### 1.5 Dosya gönderildiğinde
- Bot dosyayı okur ve geçerli bir PO dosyası olup olmadığını kontrol eder. Değilse
  anlaşılır bir hata mesajı verir.
- Kısa bir özet gösterir:
  `gnome-calculator.master.az.po` → Toplam 412 · ✅ 350 çevrilmiş · 🟡 22 fuzzy · ⬜ 40 çevrilmemiş
- Ne çevrileceğini sorar: **[⬜ Çevrilmemişler] [🟡 Fuzzy'ler] [⬜+🟡 İkisi birden] [📜 Hepsi]**
- Kullanıcının yarım kalmış bir dosyası varken yeni dosya gönderirse bot sorar:
  "Önceki dosyaya devam mı, yeni dosyaya geçilsin mi?"

### 1.6 Çeviri ekranı (mobilde rahat kullanılabilir olmalı)
Her girdi tek bir mesaj kartı olarak gösterilir:

```
#37 / 62  ·  🟡 fuzzy  ·  c-format
📍 src/math-window.vala:214
💬 Not: Button label
🔤 Bağlam: menu

🇬🇧 Kaynak:
_Undo %s            ← dokununca kopyalanır (monospace)

✏️ Mevcut çeviri:
_Geri al %s

Çeviriyi yazıp gönderin 👇
[⬅ Geri] [⏭ Atla] [✅ Onayla]
[📋 Kaynağı kopyala] [💾 Kaydet] [✖ Bitir]
```

- Kullanıcı sadece çeviriyi yazıp gönderir, bot otomatik olarak sonrakine geçer.
- **✅ Onayla:** Fuzzy girdide mevcut çeviri doğruysa fuzzy işaretini kaldırır.
- **⏭ Atla:** Girdiyi olduğu gibi bırakır.
- **⬅ Geri:** Önceki girdiye döner, düzeltme yapılabilir.
- **Çoğul (plural) metinler:** Dilin kurallarına göre her form ayrı ayrı sorulur
  ("Tekil form", "Çoğul form"…).
- Görünmez karakterler görünür yapılır: satır sonu `↵`, baştaki/sondaki boşluk `·`.
  Böylece çevirmen bunları kaçırmaz.
- Telefonda kaynak metni kopyalamak kolay olmalı (monospace metne dokunulunca kopyalanır).

### 1.7 Çeviri kontrolleri (hatalı dosya teslim edilmesin)
Her çeviri kaydedilmeden önce kontrol edilir. Sorun varsa bot uyarır ve
**[Düzelt] [Yine de kaydet]** seçeneklerini sunar:
- Format belirteçleri aynı mı: `%s`, `%d`, `%1$s`, `%(name)s`, `{name}`
- Kısayol harfi (`_`) korunmuş mu
- Sondaki satır sonu (`\n`) tutarlı mı
- Etiketler (`<b>`, `<a href="…">`) korunmuş mu
- Çoğul formların hepsi dolu mu

### 1.8 Kaydet ve indir
Kullanıcı **💾 Kaydet** dediğinde (veya bütün girdiler bittiğinde) bot:
- Çevirileri dosyaya işler. Dosyadaki diğer her şey (yorumlar, eski girdiler,
  sıralama) **olduğu gibi korunur**.
- Başlığı günceller:
  - `PO-Revision-Date:` şu anki tarih ve saat
  - `Last-Translator: Ad Soyad <e-posta>`
  - `Language-Team:`, `Language:`
  - `Plural-Forms:` (dile göre doğru kural)
  - `Content-Type: text/plain; charset=UTF-8`
  - `X-Generator: Gnope 1.0`
- `.pot` dosyası gönderildiyse başlığı sıfırdan kurar.
- Dosyayı **orijinal adıyla** geri gönderir (ör. `gnome-calculator.master.az.po`)
  ve son istatistiği yazar.
- Kullanıcı isterse çevirmeye devam edebilir, kaydetmek oturumu kapatmaz.

### 1.9 Yarıda bırakma ve devam etme
- Her çeviri anında kaydedilir. Telefon kapansa da, Telegram kapansa da iş kaybolmaz.
- Kullanıcı `/continue` yazınca kaldığı girdiden devam eder.
- Dosyalar belli bir süre (ör. 14 gün) işlem görmezse otomatik silinir. Kullanıcı
  bundan önceden haberdar edilir.

### 1.10 Komutlar
| Komut | İşlev |
|---|---|
| `/start` | Karşılama, dil seçimi |
| `/language` | Arayüz dilini değiştir |
| `/profile` | Ad, e-posta, çeviri dili |
| `/continue` | Yarım kalan dosyaya devam |
| `/status` | Aktif dosyanın istatistiği |
| `/save` | Dosyayı kaydet ve indir |
| `/cancel` | Aktif dosyayı kapat ve sil |
| `/help` | Nasıl kullanılır |
| `/about` | Bot hakkında, geliştirici, kaynak kod linki |

### 1.11 Hakkında (`/about`)
- Botun GNOME çeviri topluluğunu desteklemek için gönüllü olarak geliştirildiği
- **Geliştirici: [ADIN SOYADIN]** (+ isteğe bağlı Telegram/GitHub linki)
- Açık kaynak olduğu, lisansı ve kaynak kod linki
- GNOME'un resmi bir ürünü olmadığı (GNOME Foundation'ın marka kuralları gereği
  "GNOME tarafından yapılmıştır" değil, "GNOME'u desteklemek için yapılmıştır" denir)

### 1.12 Genel ilkeler
- **Ücretsiz:** Kullanıcıdan hiçbir ücret alınmaz, reklam yok.
- **Açık kaynak:** Kaynak kod GitHub'da GPL-3.0 lisansıyla yayınlanır. Herkes
  inceleyebilir, katkı verebilir, kendi sunucusunda çalıştırabilir.
- **7/24 çalışır:** Benim mevcut web sitemin cPanel hostinginde çalışır.
- **Gizlilik:** Çeviri içerikleri loglanmaz, dosyalar süre dolunca silinir,
  bot token'ı koda yazılmaz.
- **Mobil öncelikli:** Her şey telefondan rahatça yapılabilmeli.

---

## BÖLÜM 2: Araştırma: cPanel'de 7/24 çalışır mı?

### 2.1 Kısa cevap: **Evet, "webhook" yöntemiyle çalışır.**

Telegram botları iki şekilde çalışabilir:

| Yöntem | Nasıl çalışır | cPanel'de |
|---|---|---|
| **Long polling** | Bot sürekli açık kalan bir program olarak Telegram'a "yeni mesaj var mı?" diye sorar | ❌ **Olmaz.** Paylaşımlı hostingde (CloudLinux/LVE) uzun süre çalışan arka plan işlemleri kaynak limitleri yüzünden öldürülür. Bot sık sık kapanır. |
| **Webhook** | Bot normal bir web sayfası gibidir. Kullanıcı mesaj attığında **Telegram, sitemizdeki bir adrese** (ör. `https://bot.siten.com/webhook`) istek gönderir. Sunucu işi birkaç saniyede yapar ve kapanır. | ✅ **Olur.** Site 7/24 açık olduğu sürece bot da 7/24 çalışır. Sunucuda sürekli çalışan bir işlem gerekmez. |

Yani bot **sitenin bir parçası gibi** çalışacak. Kimse mesaj atmadığında hiç kaynak
harcamaz, mesaj geldiğinde uyanır.

### 2.2 Gereksinimler (hostingde kontrol etmen gerekenler)
1. **cPanel'de "Setup Python App" menüsü** (CloudLinux + Passenger). Her pakette
   bulunmuyor. Varsa bot Python ile yazılır.
   - **Yoksa:** Bot **PHP** ile yazılır. PHP her cPanel'de var. Tasarım aynı kalır,
     sadece dil değişir.
2. **HTTPS (SSL):** Telegram webhook için zorunlu. cPanel'deki **AutoSSL**
   (Let's Encrypt) ücretsiz sertifika verir. Port 443 kullanılır.
3. **Tercihen bir alt alan adı:** `bot.siten.com` gibi. Ana siteni etkilemez.
4. **Terminal veya SSH erişimi:** Kurulum için iyi olur. Yoksa cPanel arayüzünden
   de yapılabilir.

### 2.3 Veriler nerede tutulur?
Hepsi **senin hostinginde** durur, üçüncü bir tarafa gitmez:

```
/home/kullanici/
├── public_html/              ← mevcut siten (dokunulmaz)
└── gnome-po-bot/             ← bot (web'den erişilemeyen klasör)
    ├── app/                  ← kaynak kod
    ├── .env                  ← bot token'ı, gizli anahtar (asla GitHub'a gitmez)
    └── data/
        ├── bot.db            ← SQLite veritabanı: kullanıcı profili, dil, oturum, hangi girdide kalındığı
        └── files/<id>/       ← kullanıcıların yüklediği/çevirdiği .po dosyaları
```

- **Veritabanı:** SQLite tek bir dosyadır, kurulum gerektirmez ve yedeklemesi
  kolaydır. (İstenirse cPanel'in MySQL'i de kullanılabilir, ama gerek yok.)
- Klasör `public_html` dışında olduğu için **dışarıdan kimse dosyalara erişemez**.
- **Temizlik:** cPanel'deki **Cron Jobs** ile günde bir kez çalışan küçük bir görev,
  süresi dolan dosyaları siler.

### 2.4 Açık kaynak + ücretsiz nasıl birlikte olur?
- **Kod** GitHub'da herkese açık olur (GPL-3.0). İçinde token veya kişisel bilgi
  **olmaz**. Bunlar sadece sunucudaki `.env` dosyasında durur, repoda `.env.example`
  şablonu bulunur.
- **Çalışan bot** senin hostinginde durur. Hosting parasını zaten site için
  ödüyorsun, Telegram API ücretsiz, SSL ücretsiz. **Ek maliyet sıfır.**
- Başka bir topluluk isterse kodu alıp kendi botunu kurabilir. README'de cPanel
  kurulum rehberi bulunur.

### 2.5 Riskler ve önlemler
| Risk | Önlem |
|---|---|
| Hosting kaynak limiti (CPU/RAM/eşzamanlı işlem) | PO işleme hafif bir iştir. Her istek kısa sürer, dosya boyutu sınırlanır (ör. 5 MB). |
| İlk istekte gecikme (Passenger uyku modundan uyanır) | 1-3 saniyelik gecikme normaldir, kullanıcı fark etmez. |
| Telegram aynı mesajı tekrar gönderebilir | Her `update_id` kaydedilir, aynı mesaj iki kez işlenmez. |
| Sahte istekler (başkası webhook adresine istek atarsa) | Telegram'ın `secret_token` özelliği kullanılır. Her istekte gizli başlık kontrol edilir, eşleşmeyen istek reddedilir. Webhook adresi de tahmin edilemez olur. |
| Aynı anda birçok istek (SQLite kilitlenmesi) | SQLite WAL modu ve kısa işlemler kullanılır. Tüm durum veritabanında tutulur, bellekte değil. |
| Sunucuda `msgfmt` (gettext) olmayabilir | Varsa son kontrolde kullanılır, yoksa botun kendi kontrolleri devreye girer. |
| Barındırma firması bot çalıştırmayı yasaklıyor olabilir | Kullanım koşulları kontrol edilir. Webhook normal web trafiği olduğu için genelde sorun olmaz. |

---

## BÖLÜM 3: Teknik plan

### 3.1 Teknoloji
| Konu | Seçim (Python varsa) | Alternatif (Python yoksa) |
|---|---|---|
| Dil | Python 3.10+ | PHP 8.1+ |
| Web katmanı | Flask (Passenger WSGI uyumlu) | Saf PHP |
| Telegram | Bot API'ye doğrudan, senkron HTTPS istekleri | aynı |
| PO işleme | `polib` | `gettext/gettext` (Composer) |
| Veritabanı | SQLite | SQLite (PDO) |
| Testler | pytest | PHPUnit |

> Not: Önceki plandaki `python-telegram-bot` kütüphanesi kendi sunucusunu açmak
> istediği için cPanel/Passenger'a uygun değil. Onun yerine istek gelince çalışıp
> biten, senkron ve sade bir yapı kuracağız.

### 3.2 Klasör yapısı (Python)
```
gnome-po-bot/
├── passenger_wsgi.py        # cPanel giriş noktası
├── app/
│   ├── web.py               # /webhook endpoint, secret_token kontrolü
│   ├── telegram_api.py      # sendMessage, sendDocument, getFile…
│   ├── router.py            # gelen mesajı/butonu doğru işleyiciye yollar
│   ├── handlers/            # start, language, profile, upload, translate, save, about
│   ├── po/
│   │   ├── loader.py        # güvenli okuma, doğrulama, istatistik
│   │   ├── checks.py        # format/mnemonic/markup/plural kontrolleri
│   │   ├── header.py        # başlık güncelleme
│   │   └── plural_forms.py  # dil kodu → Plural-Forms tablosu
│   ├── storage/             # SQLite: users, sessions, processed_updates
│   ├── ui/                  # kart biçimlendirme, butonlar, HTML escape
│   └── i18n/                # en.po, tr.po, az.po (botun kendi arayüzü!)
├── scripts/
│   ├── set_webhook.py       # webhook'u Telegram'a kaydeder
│   └── cleanup.py           # cron: eski dosyaları siler
├── tests/
├── .env.example
├── README.md                # cPanel kurulum rehberi dahil
└── LICENSE                  # GPL-3.0
```

### 3.3 Bir mesajın yolculuğu
```
Kullanıcı (telefon) ──mesaj──▶ Telegram sunucusu
                                   │ HTTPS POST + secret_token
                                   ▼
                     https://bot.siten.com/webhook   (cPanel / Passenger)
                                   │
                     1. secret_token doğru mu?   → değilse 403
                     2. update_id daha önce işlendi mi? → evetse atla
                     3. Kullanıcının durumu DB'den okunur
                     4. İşleyici çalışır (çeviriyi kaydet, sonraki kartı hazırla)
                     5. Telegram API'ye cevap gönderilir
                     6. 200 OK → istek biter, işlem kapanır
```

### 3.4 Aşamalar
| Faz | İçerik | Bitti sayılır |
|---|---|---|
| **0. Hazırlık** | Hostingde Python/PHP kontrolü, alt alan adı + SSL, BotFather'dan token | Senin yapacağın adımlar, rehberini ben vereceğim |
| **1. Çekirdek** | PO okuma/yazma, başlık güncelleme, kontroller, plural tablosu + testler | "Aç → değiştirme → kaydet" testinde dosya bayt bayt aynı kalıyor |
| **2. Bot akışı** | Webhook, dil seçimi (3 dil), profil, dosya yükleme, tek tek çeviri, geri/atla/onayla, kaydet-indir, devam etme | Bilgisayarda (yerel test) baştan sona bir GNOME dosyası çevrilebiliyor |
| **3. cPanel'e kurulum** | Passenger ayarı, `.env`, webhook kaydı, cron temizliği | Telefondan gerçek bot çalışıyor |
| **4. Açık kaynak yayın** | README (EN/TR/AZ), kurulum rehberi, GitHub'a yükleme, lisans | Başkası rehberle kendi botunu kurabiliyor |

### 3.5 Senden gerekenler (onay sırasında)
1. **cPanel'de "Setup Python App" var mı?** (cPanel ana sayfasında "Software"
   bölümüne bak.) Python mı PHP mi kullanacağımızı bu belirler.
2. **Hakkında bölümünde adın nasıl yazılsın?** (Ad Soyad, isteğe bağlı Telegram
   kullanıcı adı veya GitHub linki)
3. **Bot için alt alan adı:** ör. `bot.siten.com` uygun mu?
4. **Dosya saklama süresi:** 14 gün uygun mu?
5. **Bot adı:** "Gnope" / `@gnope_bot` (BotFather'da müsait
   olup olmadığına sen bakarsın, token'ı sadece sen görürsün).
