# Otomatik AI YouTube Shorts Fabrikası (ASMR) — Plan

> n8n'in yaptığı işi **sadece Python + Claude Code** ile yapan, her gün belirlenen
> saatlerde ASMR YouTube Shorts üreten bir otomasyon. **Günde 5 farklı YouTube
> hesabına, her birine BİRBİRİNDEN FARKLI bir video** yayınlar (aynı video 5 yere
> kopyalanmaz; her hesap kendi ayrı fikir → ayrı klip → ayrı kurgu zincirini
> üretir). Video YouTube'a yüklenmeden önce **mutlaka kullanıcıdan onay** alınır.

---

## 1. Verilen Kararlar

| Konu | Karar |
|---|---|
| Dil / Runtime | **Python 3.11+** |
| Metin üretimi (fikir + sahne promptları) | **Claude (Anthropic API)** — `claude-opus-4-8` / `claude-haiku-4-5` |
| Video üretimi | **Wavespeed AI** — ByteDance Seedance (text-to-video) |
| Ses üretimi + birleştirme | **Fal AI** — `mmaudio-v2` (ses) + `ffmpeg-api/compose` (kurgu) |
| Zamanlama | **Claude Code `/schedule`** (cron tabanlı bulut routine) |
| İçerik teması | **ASMR** (kinetik kum, dilimleme/kaşıklama vb.) |
| İçerik dili | **İngilizce** (başlık, açıklama, hashtag) |
| Loglama | **Google Sheets** |
| Bildirim | **E-posta (Gmail)** |
| Yükleme onayı | **Her videoda kullanıcı onayı zorunlu** |
| Hedef hesap sayısı | **Günde 5 farklı YouTube hesabı** |
| Video–hesap eşlemesi | **Her hesaba 1 ADET FARKLI video** → günde toplam 5 benzersiz video (aynı içerik tekrarlanmaz) |

---

## 2. İş Akışı (Pipeline)

n8n workflow'unun birebir Python karşılığı. 4 aşama.

> 🔁 **Çoklu hesap döngüsü**: Aşağıdaki 4 aşama her gün **5 hesabın her biri için
> ayrı ayrı** çalışır. Pipeline `accounts.json` listesindeki hesaplar üzerinde
> döner; her hesap kendi **temasını**, OAuth token'ını, Sheets sekmesini ve yayın
> saatini kullanır. Her hesap Aşama 1'de **kendi temasına göre ayrı bir fikir**
> ürettiği için çıktı doğal olarak benzersizdir: günde **5 BİRBİRİNDEN FARKLI
> video** üretilir ve 5 ayrı kanala yüklenir. **Aynı video birden çok hesaba
> kopyalanmaz.** Üretilen fikirler Sheets'teki geçmişe karşı kontrol edilerek
> (dedupe) gün içinde ve günler arası tekrar engellenir.

### Aşama 1 — Fikir Üretimi (Claude)
1. **Trend fikir üret**: Claude'dan tek satırlık, viral, basit bir ASMR konsepti
   iste (< 10 kelime).
2. **Fikri prodüksiyon planına çevir**: Claude ikinci çağrıda fikri yapılandırılmış
   JSON'a genişletir:
   ```json
   {
     "Caption": "... 1 emoji + 12 hashtag ...",
     "Idea": "(renk/stil) (nesne) being (aksiyon)",
     "Environment": "< 20 kelime sahne tanımı",
     "Sound": "< 15 kelime ses tanımı",
     "Status": "for production"
   }
   ```
3. **Google Sheets'e yeni satır ekle**: `idea, caption, environment_prompt,
   sound_prompt, production=In Progress`.

### Aşama 2 — Asset Üretimi
4. **3 sahne promptu üret** (Claude): Idea + Environment + Sound girdisinden,
   her biri 1000–2000 karakter, kameralı, hareketli sahne açıklamaları.
5. **Video klipleri üret** (Wavespeed Seedance): her sahne için ayrı klip,
   `aspect_ratio: 9:16`, `duration: 10`. Asenkron: gönder → request id → poll.
6. **Sesleri üret** (Fal mmaudio-v2): üretilen video + Sound prompt'tan ASMR sesi.
   Asenkron: queue.fal.run → request_id → poll.

### Aşama 3 — Final Kurgu
7. **Klipleri birleştir** (Fal ffmpeg-api/compose): 3 × 10sn = ~30sn tek video.
8. **Final videoyu indir** (lokal `output/` klasörüne `.mp4`).

### Aşama 4 — Dağıtım & Loglama
9. **🔔 ONAY ADIMI**: Pipeline durur, kullanıcıya şu bilgileri gösterir:
   - Başlık, açıklama, hashtag'ler
   - Lokal video dosya yolu (kullanıcı izleyip kontrol edebilir)
   - "Bu videoyu YouTube'a yüklememi onaylıyor musun? (evet/hayır)"
   - Onay yoksa video yüklenmez, Sheets'te durum `Pending Approval` kalır.
10. **YouTube'a yükle** (onay sonrası): başlık, açıklama, tags, `privacyStatus`.
11. **Google Sheets güncelle**: aynı satıra `final_output`, `youtube_url`,
    `production=Done`.
12. **Gmail bildirimi gönder**: "Yeni video yayında" + YouTube linki.

---

## 3. Gerekli API Anahtarları ve Nasıl Alınır

Hiçbiri henüz yok. Sırayla kuracağız. Tümü `.env` dosyasında tutulacak
(asla repoya commit edilmez).

| Servis | Ne için | Nereden alınır | Tahmini maliyet |
|---|---|---|---|
| **Anthropic** | Fikir + sahne promptları | console.anthropic.com → API Keys | Çok düşük (metin) |
| **Wavespeed AI** | Seedance video üretimi | wavespeed.ai → kayıt → API key | Video başına ücret |
| **Fal AI** | Ses (mmaudio) + kurgu (ffmpeg) | fal.ai → kayıt → API key | İşlem başına ücret |
| **Google Cloud** | YouTube + Sheets OAuth | console.cloud.google.com | Ücretsiz (kota dahilinde) |
| **Gmail** | E-posta bildirimi | Google Hesabı → App Password | Ücretsiz |

### Google Cloud kurulumu (en uzun adım) — 5 hesap için
1. console.cloud.google.com'da proje(ler) oluştur. **Kota nedeniyle (aşağıya bak)
   her YouTube hesabı için AYRI bir Google Cloud projesi önerilir → toplam 5 proje.**
2. Her projede **YouTube Data API v3**'ü etkinleştir. (Google Sheets API tek
   projede yeterli — Sheets yazımı kota sorunu yaratmaz.)
3. Her projede OAuth consent screen yapılandır (External; ilgili hesabı test user
   olarak ekle).
4. Her proje için **OAuth 2.0 Client ID** (Desktop app) oluştur →
   `client_secret.json` indir.
5. İlk çalıştırmada her hesap için ayrı tarayıcı izni → **hesaba özel `token.json`**
   üretilir (sonraki çalıştırmalar otomatik). Toplam **5 kez OAuth onayı** verilir.
6. **Google Sheet** oluştur. Her hesap için ya ayrı sekme (tab) ya da `account`
   sütunu ekle. Sütunlar:
   `id | account | idea | caption | production | environment_prompt | sound_prompt | final_output | youtube_url`

### Gmail App Password
- 2 adımlı doğrulamayı aç → Uygulama Şifreleri → 16 haneli şifre oluştur.

> ⚠️ **YouTube kotası (5 hesap için kritik!)**: YouTube Data API kotası
> **Google Cloud projesi başına** günde 10.000 birimdir (hesap başına DEĞİL).
> `videos.insert` çağrısı ~1600 birim harcar → tek projeyle günde sadece ~6 yükleme.
> 5 hesaba tek projeden yüklemek tehlikelidir (kota tükenir, hatalar başlar).
> **Çözüm**: her hesap için ayrı Google Cloud projesi → her birine ayrı 10.000
> kota. Alternatif: tek proje + kota artırımı başvurusu (onay süreci uzun).

---

## 4. Proje Yapısı

```
ytshorts/
├── plan.md                  # bu dosya
├── README.md                # kurulum + kullanım talimatları
├── requirements.txt         # Python bağımlılıkları
├── .env.example             # anahtar şablonu (boş)
├── .env                     # gerçek anahtarlar (gitignore)
├── .gitignore
├── config.py                # ortam değişkenleri + ayarlar
├── accounts.json            # 5 hesabın ayarı (tema, token yolu, saat, sekme)
├── credentials/             # hesap bazlı OAuth (gitignore)
│   ├── account1/            #   client_secret.json + token.json
│   ├── account2/
│   ├── account3/
│   ├── account4/
│   └── account5/
├── output/                  # üretilen .mp4 dosyaları (hesap bazlı alt klasör)
├── logs/                    # çalışma logları
└── src/
    ├── ideate.py            # Claude: fikir + plan üretimi
    ├── prompts.py           # Claude: 3 sahne promptu
    ├── video.py             # Wavespeed Seedance entegrasyonu
    ├── audio.py             # Fal mmaudio entegrasyonu
    ├── compose.py           # Fal ffmpeg birleştirme + indirme
    ├── sheets.py            # Google Sheets okuma/yazma
    ├── youtube.py           # YouTube yükleme (OAuth)
    ├── notify.py            # Gmail bildirimi
    └── pipeline.py          # tüm adımları sırayla çalıştıran ana akış
```

### `accounts.json` şeması (5 hesap = 5 farklı tema = 5 farklı video)

Her hesabın **farklı bir `theme` değeri** vardır; bu değer Aşama 1'de Claude'a
verilen fikir promptunu çeşitlendirir, böylece her kanal benzersiz bir video alır.

```json
[
  { "id": "account1", "name": "Kinetic Sand ASMR", "theme": "kinetik kum kesme/ezme",
    "credentials_dir": "credentials/account1", "sheet_tab": "account1",
    "publish_time": "10:00", "privacy_status": "public" },
  { "id": "account2", "name": "Soap Cutting ASMR", "theme": "sabun dilimleme",
    "credentials_dir": "credentials/account2", "sheet_tab": "account2",
    "publish_time": "12:00", "privacy_status": "public" },
  { "id": "account3", "name": "Ice & Glass ASMR", "theme": "cam/buz kırma",
    "credentials_dir": "credentials/account3", "sheet_tab": "account3",
    "publish_time": "14:00", "privacy_status": "public" },
  { "id": "account4", "name": "Slime Squish ASMR", "theme": "slime sıkıştırma",
    "credentials_dir": "credentials/account4", "sheet_tab": "account4",
    "publish_time": "16:00", "privacy_status": "public" },
  { "id": "account5", "name": "Paint Mixing ASMR", "theme": "boya karıştırma",
    "credentials_dir": "credentials/account5", "sheet_tab": "account5",
    "publish_time": "18:00", "privacy_status": "public" }
]
```

| Alan | Açıklama |
|---|---|
| `id` | Hesabın benzersiz kimliği (klasör/sekme adıyla eşleşir) |
| `name` | Kanal/insan-okur etiketi |
| `theme` | **Hesaba özel ASMR teması** → her hesapta farklı video üretiminin kaynağı |
| `credentials_dir` | Hesaba özel `client_secret.json` + `token.json` yolu |
| `sheet_tab` | Bu hesabın Google Sheets sekmesi |
| `publish_time` | Bu hesabın günlük yayın saati (farklı saatler → kota/rate dağıtımı) |
| `privacy_status` | `public` / `unlisted` / `private` |

---

## 5. Bağımlılıklar (`requirements.txt`)

```
anthropic               # Claude API
requests                # HTTP (Wavespeed, Fal)
google-api-python-client
google-auth-oauthlib
google-auth-httplib2
python-dotenv
```

---

## 6. Onay Mekanizması (en kritik istek)

`pipeline.py` iki modda çalışacak:

- **`--auto-upload` YOK (varsayılan)**: Video üretilir, indirilir, sonra DURUR.
  Kullanıcı dosyayı izler ve Claude Code içinde "onaylıyorum" derse `youtube.py`
  çağrılır. `/schedule` ile çalışan otomasyon her gün videoyu hazırlar, onay için
  bekler.
- **`--auto-upload` VAR**: (İleride istenirse) onaysız tam otomatik yükleme.

Varsayılan davranış: **onay olmadan asla yükleme yok.** Senin isteğin bu yönde.

---

## 7. Zamanlama (`/schedule`)

- Pipeline'ın "video hazırlama" kısmı (Aşama 1–3 + indirme) `/schedule` ile günde
  belirlenen saat(ler)de otomatik çalışır.
- Hazır video + bilgi kartı sunulur, **onay beklenir**.
- Onay sonrası yükleme + loglama + e-posta tetiklenir.
- Hangi saatlerde çalışacağını (örn. her gün 10:00 ve 18:00) kurulum sonunda
  birlikte ayarlayacağız.

---

## 8. Uygulama Sırası (Yapılacaklar)

1. [ ] Proje iskeleti + `requirements.txt` + `.env.example` + `.gitignore`
2. [ ] `accounts.json` — 5 hesap, **5 farklı tema** (her hesaba ayrı/benzersiz video)
3. [ ] `config.py` (ortam değişkenleri yükleme)
4. [ ] `ideate.py` — Claude ile fikir + plan (test edilebilir)
5. [ ] `prompts.py` — Claude ile 3 sahne promptu
6. [ ] `video.py` — Wavespeed Seedance (gönder + poll)
7. [ ] `audio.py` — Fal mmaudio (gönder + poll)
8. [ ] `compose.py` — Fal ffmpeg birleştirme + indirme
9. [ ] `sheets.py` — Google Sheets entegrasyonu
10. [ ] `youtube.py` — YouTube OAuth + yükleme
11. [ ] `notify.py` — Gmail bildirimi
12. [ ] `pipeline.py` — tüm hesaplar üzerinde döngü + onay adımı (her hesaba farklı video)
13. [ ] Anahtarları `.env`'e gir, uçtan uca test (önce dry-run)
14. [ ] `/schedule` ile günlük tetikleme kur

---

## 9. Açık Notlar / Riskler

- **Maliyet**: Her video birden çok ücretli API çağrısı (video + ses). Tüm
  dashboard'larda bütçe uyarısı kurulması önerilir.
- **API rate limit**: Wavespeed/Fal sık çağrıda geçici blok yapabilir → poll
  aralıkları ayarlanacak.
- **Seedance/Fal endpoint değişiklikleri**: Entegrasyon yazarken güncel API
  dokümanı doğrulanacak (URL/parametreler değişmiş olabilir).
- **YouTube kota limiti**: Günlük yükleme sayısı buna göre sınırlı.

---

## 10. Sonraki Adım

Bu planı onayladıktan sonra **Adım 1**'den (proje iskeleti) başlayacağız.
İstersen önce hangi API anahtarlarını almaya başlayacağını da söyleyebilirim.
