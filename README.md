# Telegram Video Stream Server & Web Player 🎬

ប្រព័ន្ធបង្កើត **Direct Stream Link (.mp4)** ពី Telegram សម្រាប់យកទៅចាក់លើ **Web Player (HTML5 `<video>`, Plyr, Video.js, VLC)** ដោយផ្ទាល់ជាមួយ **HTTP 206 Partial Content (Seek ទៅមុខ-ថយក្រោយបានរលូន)** និងមិនស៊ីទំហំ Hard disk (Passthrough Stream)។

---

## 🌟 លក្ខណៈពិសេស (Features)

1. **Direct Passthrough Streaming**: Server មិនចាំបាច់ Download វីដេអូទុកក្នុង Hard disk ឡើយ (Memory footprint ទាប និងល្បឿនលឿន)។
2. **Full Range Seek Support (HTTP 206)**: អ្នកទស្សនាអាចអូស Seek ទៅមុខ ឬថយក្រោយលើ Web Player បានភ្លាមៗដូច YouTube/Netflix។
3. **Multi-Format Support**: គាំទ្រ `.mp4`, `.mkv`, `.webm`, `.mov` និង Media Document ទាំងអស់ក្នុង Telegram។
4. **Modern Built-in Web Player**:
   - រចនាបទ Premium Dark Theme ជាមួយ **Plyr.js**
   - គាំទ្រ Speed control (0.5x, 1x, 1.5x, 2x), Picture-in-Picture (PiP), Fullscreen
   - Keyboard shortcuts (Space: Play/Pause, M: Mute, F: Fullscreen, ព្រួញឆ្វេង/ស្ដាំ: Seek)
5. **Ready-to-use Embeds**: ផ្ដល់ជូនភ្លាមៗនូវ Direct URL, HTML5 `<video>` tag, និង `<iframe>` embed code។
6. **Telegram Bot Integration**: គ្រាន់តែ Upload ឬ Forward វីដេអូទៅកាន់ Bot នោះ Bot នឹង reply ផ្ដល់ Link មកវិញភ្លាមៗ។

---

## 🚀 របៀបដំឡើង និងដំណើរការ (Quick Start Guide)

### ជំហានទី ១៖ យក Telegram Credentials

1. **API_ID & API_HASH**:
   - ចូលទៅកាន់ [https://my.telegram.org](https://my.telegram.org)
   - Login លេខទូរសព្ទ Telegram របស់អ្នក រួចចូលទៅកាន់ **API Development Tools**
   - បង្កើត App មួយ ដើម្បីទទួលបាន `App api_id` និង `App api_hash`។
2. **BOT_TOKEN**:
   - បើក Telegram រួចស្វែងរក [@BotFather](https://t.me/BotFather)
   - ផ្ញើពាក្យ `/newbot` រួចធ្វើតាមការណែនាំ ដើម្បីទទួលបាន `Bot Token` (ឧ. `123456789:ABCdefGhIJK...`)។
3. **BIN_CHANNEL (Channel សម្រាប់ផ្ទុក Media)**:
   - បង្កើត Telegram Channel ថ្មីមួយ (Private ឬ Public)
   - **សំខាន់៖** Add Bot ដែលទើបបង្កើតនោះ ជា **Administrator** ក្នុង Channel នោះ
   - យក Channel ID (ជាទូទៅផ្ដើមដោយ `-100` ដូចជា `-1002345678901`)។
     *(គន្លឹះ៖ អ្នកអាច Forward សារមួយពី Channel នោះទៅកាន់ bot ឈ្មោះ `@userinfobot` ឬ `@JsonDumpBot` ដើម្បីមើល ID)*

---

### ជំហានទី ២៖ បង្កើត File `.env`

ចម្លង file `.env.example` ទៅជា `.env`៖
```bash
copy .env.example .env
```

បើក file `.env` រួចបំពេញព័ត៌មានរបស់អ្នក៖
```env
API_ID=12345678
API_HASH=0123456789abcdef0123456789abcdef
BOT_TOKEN=1234567890:ABCdefGhIJKlmNoPQRstuVWXyz
BIN_CHANNEL=-1001234567890
PORT=8080
FQDN=http://localhost:8080
```
> [!TIP]
> ប្រសិនបើអ្នកដាក់លើ VPS ឬប្រើ Domain ផ្ទាល់ខ្លួន (ឧទាហរណ៍ `https://stream.yourdomain.com`) សូមប្ដូរ `FQDN` ទៅតាម Domain នោះ។

---

### ជំហានទី ៣៖ ដំណើរការ Server

អ្នកអាចដំណើរការតាមរយៈ៖
* **វិធីទី ១ (Double-Click):** ចុចលើ file `run.bat`
* **វិធីទី ២ (Terminal):**
  ```bash
  python server.py
  ```

---

## 💻 របៀបប្រើប្រាស់ (Usage)

1. បើក Telegram រួចចូលទៅកាន់ Bot របស់អ្នក ចុច `/start`
2. **Forward** ឬ **Upload** វីដេអូណាមួយទៅកាន់ Bot
3. Bot នឹងផ្ញើសារត្រឡប់មកវិញភ្លាមៗនូវ៖
   - 🔗 **Direct Stream URL**: `http://localhost:8080/stream/{id}.mp4`
   - 🎬 **Web Player URL**: `http://localhost:8080/watch/{id}`
   - ⬇️ **Download Link**: `http://localhost:8080/stream/{id}.mp4?download=1`

---

## 🌐 របៀបយកទៅបង្កប់លើគេហទំព័រ (Embedding on Web)

### ១. ប្រើប្រាស់ជាមួយ HTML5 `<video>` Tag
```html
<video controls width="100%" preload="metadata">
    <source src="http://localhost:8080/stream/123.mp4" type="video/mp4">
    Your browser does not support the video tag.
</video>
```

### ២. ប្រើប្រាស់ជាមួយ iframe Embed
```html
<iframe 
    src="http://localhost:8080/embed/123" 
    width="100%" 
    height="450" 
    frameborder="0" 
    allowfullscreen>
</iframe>
```

### ៣. ប្រើជាមួយ Video.js ឬ Plyr.js
```javascript
const player = new Plyr('#player');
// ឬ Video.js
videojs('my-video', {
    sources: [{
        src: 'http://localhost:8080/stream/123.mp4',
        type: 'video/mp4'
    }]
});
```

---

## 📡 API Endpoints Reference

| Method | Endpoint | មុខងារ |
| :--- | :--- | :--- |
| `GET` | `/` | Web Dashboard & Instant Stream Tester |
| `GET / HEAD` | `/stream/{id}.mp4` | Direct HTTP 206 Video Stream |
| `GET` | `/watch/{id}` | Full Web Player UI ជាមួយ Controls & Metadata |
| `GET` | `/embed/{id}` | Minimalist Player សម្រាប់ iframe |
| `GET` | `/api/info/{id}` | JSON Metadata (file name, size, mime type, etc.) |
