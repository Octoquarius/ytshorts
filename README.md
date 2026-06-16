# AI ASMR YouTube Shorts Fabrikası

Günde **5 farklı YouTube hesabına, her birine birbirinden farklı bir ASMR Short**
üreten Python otomasyonu. Her hesap kendi temasından bağımsız bir fikir üretir →
günde 5 benzersiz video. Yükleme öncesi **her videoda kullanıcı onayı** zorunludur.

Ayrıntılı tasarım için bkz. [`plan.md`](plan.md).

## Akış

1. **Fikir** (Claude): hesabın temasına göre tek satırlık konsept + yapılandırılmış plan.
2. **Asset** (Wavespeed Seedance + Fal mmaudio): 3 sahne promptu → 3 klip → ASMR sesi.
3. **Kurgu** (Fal ffmpeg): klipleri ~30sn tek videoda birleştir + indir.
4. **Dağıtım**: onay → YouTube yükleme → Sheets log → Gmail bildirimi.

## Kurulum

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows PowerShell
pip install -r requirements.txt
cp .env.example .env            # ardından .env içini doldur
```

### `.env` anahtarları
`.env.example` dosyasındaki tüm alanları doldur: Anthropic, Wavespeed, Fal,
`GOOGLE_SHEET_ID`, Gmail App Password.

### Hesaplar (`accounts.json`)
5 hesap ve **5 farklı tema** tanımlıdır. Her hesap için kimlik bilgileri:

```
credentials/sheets/client_secret.json    # Sheets (tek proje yeterli)
credentials/account1/client_secret.json  # her YouTube hesabı için AYRI proje
credentials/account2/client_secret.json
...  (account3, account4, account5)
```

> ⚠️ **YouTube kotası**: kota Google Cloud projesi başınadır (günde 10.000 birim,
> `videos.insert` ~1600 birim). 5 hesaba tek projeden yüklemek kotayı tüketir →
> **her hesap için ayrı Google Cloud projesi** kullan.

## Kullanım

```bash
# Tüm hesaplar için video hazırla (her birine farklı video), sonra onay sor:
python -m src.pipeline

# Sadece tek hesap:
python -m src.pipeline --account account1

# Onay sonrası elle yükleme (hazırlık sırasında üretilen manifest ile):
python -m src.pipeline --upload account1 output/account1/2026-06-16_ab12cd34.manifest.json

# Onaysız tam otomatik (dikkatli kullan):
python -m src.pipeline --auto-upload
```

İlk çalıştırmada her hesap + Sheets için tarayıcıda OAuth izni istenir; token'lar
`credentials/.../token.json` olarak saklanır (sonraki çalıştırmalar otomatik).

## Modül modül test

```bash
python -m src.ideate      # fikir + plan üretimi (Anthropic anahtarı gerekir)
python -m src.prompts     # 3 sahne promptu
```

## Zamanlama

Video hazırlama kısmını günlük tetiklemek için Claude Code `/schedule` kullanılır;
hazır videolar onay için bekler, onay sonrası yükleme tetiklenir.
