# 📘 ការណែនាំដំឡើង Telegram Video Stream Server (A ដល់ Z)
> ការណែនាំនេះរៀបចំឡើងសម្រាប់យកទៅដំឡើង ឬបង្រៀនអតិថិជន (Clients) ឱ្យចេះដំឡើង Bot និង Server ផ្ទាល់ខ្លួន សម្រាប់ចាក់ Video Stream (.mp4) លើវេបសាយភាពយន្ត ដោយឥតគិតថ្លៃទំហំផ្ទុក។

---

## 📋 តម្រូវការជាមុន (Prerequisites)
1. **គណនី Telegram** (សម្រាប់បង្កើត Bot និង Channel)
2. **Domain ផ្ទាល់ខ្លួន** (ឧទាហរណ៍: `nexkh.top` ឬ `yourdomain.com` ភ្ជាប់ជាមួយ Cloudflare)
3. **VPS Server (Ubuntu 22.04 ឬ 24.04)** (ណែនាំទីតាំង **Singapore** ដូចជា DigitalOcean, Linode, ឬ Hetzner តម្លៃត្រឹមតែ $4 - $6/ខែ)

---

## ជំហានទី ១៖ បង្កើត Bot និង Bin Channel លើ Telegram

### ១.១ បង្កើត Telegram Bot
1. ចូលទៅ Telegram ស្វែងរក Bot ឈ្មោះ **[@BotFather](https://t.me/BotFather)**
2. ផ្ញើពាក្យ `/newbot`
3. ដាក់ឈ្មោះ Bot (ឧទាហរណ៍: `My Movie Streamer`)
4. ដាក់ Username Bot ដែលបញ្ចប់ដោយពាក្យ `bot` (ឧទាហរណ៍: `mymoviestream_bot`)
5. BotFather នឹងផ្ដល់ជូន **`HTTP API Token`** (ហៅថា `BOT_TOKEN`)៖
   > ឧទាហរណ៍: `8445405147:AAH51CWfNzBADynBFcGV1yHb5gcraKCnlfY`  
   *(សូមកត់ទុកវា)*

### ១.២ យក API_ID និង API_HASH (Telegram Developer Keys)
1. ចូលទៅកាន់វេបសាយផ្លូវការ Telegram: [my.telegram.org](https://my.telegram.org)
2. វាយបញ្ចូលលេខទូរស័ព្ទ Telegram របស់បង -> វាយលេខកូដសម្ងាត់ដែលផ្ញើចូល Telegram
3. ចុចលើពាក្យ **API development tools**
4. បំពេញឈ្មោះ App ណាមួយក៏បាន (ឧ. `VideoStream`) រួចចុច Submit
5. បងនឹងទទួលបាន៖
   * **`App api_id`** (ជាលេខ ឧ. `38606693`)
   * **`App api_hash`** (ជាអក្សរ និងលេខវែង ឧ. `4784d8963ea114bcd26dd59d84f997ad`)  
   *(សូមកត់ទុកវា)*

### ១.៣ បង្កើត Channel ផ្ទុកវីដេអូ (Bin Channel)
1. បង្កើត **New Channel** មួយលើ Telegram (ដាក់ឈ្មោះអ្វីក៏បាន)
2. ជ្រើសរើសប្រភេទ Channel ជា **« Private Channel »** (ដាច់ខាតកុំដាក់ Public)
3. ចុច Add Member -> ស្វែងរក Username Bot របស់បង រួច Add វាចូល Channel
4. ផ្ដល់សិទ្ធិឱ្យ Bot នោះជា **Administrator (Admin)** ដោយបើកសិទ្ធិទាំងអស់ (Post, Edit, Delete)
5. យក **Channel ID** (លេខសម្គាល់ Channel)៖
   * Forward សារមួយពី Channel នោះទៅកាន់ bot [@userinfobot](https://t.me/userinfobot) ឬ [@JsonDumpBot](https://t.me/JsonDumpBot)
   * បងនឹងឃើញលេខសម្គាល់ Channel ដែលចាប់ផ្ដើមដោយ `-100` (ឧ. `-1003909046470`)

### ១.៤ យក Telegram User ID (សម្រាប់ចាក់សោសុវត្ថិភាព ឱ្យតែម្ចាស់ទើបប្រើបាន)
1. ចូលទៅ Chat ជាមួយ Bot **[@userinfobot](https://t.me/userinfobot)**
2. ចុច **Start** ឬផ្ញើសារណាមួយ នោះវានឹងបង្ហាញ **`Id: 1060072076`**
3. *(សូមកត់ទុកលេខ ID នេះ ដើម្បីយកទៅចាក់សោ Bot)*

---

## ជំហានទី ២៖ ទិញ និងបង្កើត VPS (Singapore)

1. ចុះឈ្មោះ ឬចូលទៅកាន់ [DigitalOcean](https://www.digitalocean.com) (ឬ Cloud Provider ផ្សេងទៀត)
2. ចុច **Create** -> **Droplets** (VPS)
3. ជ្រើសរើស៖
   * **Region (ទីតាំង):** **Singapore 🇸🇬** (ដើម្បីឱ្យល្បឿនមកកម្ពុជាលឿនបំផុត ~40ms)
   * **OS (ប្រព័ន្ធប្រតិបត្តិការ):** **Ubuntu 24.04 LTS** (ឬ 22.04)
   * **Size (កម្លាំងម៉ាស៊ីន):** Regular CPU - **1GB RAM / 1 vCPU ($6/ខែ)** ឬ 512MB RAM ($4/ខែ)
   * **Authentication:** Password (ដាក់ Password ខ្លាំងមួយសម្រាប់ Login ម៉ាស៊ីន)
4. ចុច **Create Droplet** រួចរង់ចាំប្រហែល ១ នាទី បងនឹងទទួលបាន **IPv4 Address** (ឧ. `157.245.201.238`)

---

## ជំហានទី ៣៖ ចង្អុល Domain ក្នុង Cloudflare (សំខាន់បំផុត ⚡)

1. ចូលទៅកាន់ **[Cloudflare Dashboard](https://dash.cloudflare.com)** -> ជ្រើសរើស Domain របស់បង (ឧ. `nexkh.top`)
2. ចូលទៅ Menu **DNS** -> **Records** -> ចុច **Add record**
3. បំពេញដូចខាងក្រោម៖
   * **Type:** `A`
   * **Name:** `stream` (នោះ Domain នឹងទៅជា `stream.yourdomain.com`)
   * **IPv4 address:** ដាក់លេខ **IP របស់ VPS** ដែលទើបទិញបាន (ឧ. `157.245.201.238`)
   * **Proxy status:** ចុចបិទឱ្យចេញ **ពពកពណ៌ប្រផេះ (« DNS only »)**  
     *(⚠️ ចំណាំ៖ ដាច់ខាតកុំបើកពពកពណ៌ទឹកក្រូច Proxied ព្រោះ Cloudflare នឹងបន្ថយល្បឿនវីដេអូ)*
   * **TTL:** Auto
4. ចុច **Save**

---

## ជំហានទី ៤៖ ដំឡើងប្រព័ន្ធលើ VPS ដោយស្វ័យប្រវត្តិ (1-Click Install)

1. ចូលទៅកាន់ Terminal របស់ VPS (អាចចុច **Console** លើវេបសាយ DigitalOcean ដោយផ្ទាល់)
2. Copy Command ខាងក្រោមនេះ យកទៅបិទភ្ជាប់ (Paste) រួចចុច **Enter**៖

```bash
curl -sSL -O https://raw.githubusercontent.com/sensoky25/tg-stream-player/main/setup_vps.sh && bash setup_vps.sh
```

3. ប្រព័ន្ធនឹងសួរសំណួរ (សូមវាយបញ្ចូលព័ត៌មានដែលបានកត់ទុកនៅជំហានទី ១ និង ៣)៖
   * `1. បញ្ចូល Domain/Subdomain`: (ឧទាហរណ៍ `stream.yourdomain.com`)
   * `2. បញ្ចូល Telegram BOT_TOKEN`: (ពី @BotFather)
   * `3. បញ្ចូល API_ID`: (ពី my.telegram.org)
   * `4. បញ្ចូល API_HASH`: (ពី my.telegram.org)
   * `5. បញ្ចូល Bin Channel ID`: (ឧទាហរណ៍ `-1003909046470`)
   * `6. បញ្ចូល Email សម្រាប់ SSL`: (ឧទាហរណ៍ Email របស់បង សម្រាប់ចុះឈ្មោះ Let's Encrypt)
   * `7. បញ្ចូល Telegram User ID របស់ម្ចាស់`: (លេខ ID ដែលបានពី @userinfobot សម្រាប់ចាក់សោសុវត្ថិភាព)

4. **រួចរាល់!** ប្រព័ន្ធនឹងដំណើរការដំឡើង Python, Nginx, Let's Encrypt SSL, មុខងារពន្លឿនវីដេអូ និងបើកឱ្យ Bot ដំណើរការ ២៤ ម៉ោងដោយស្វ័យប្រវត្តិ។

---

## ជំហានទី ៥៖ របៀបប្រើប្រាស់ និងយក Link ទៅដាក់លើ Web Player

1. ចូលទៅកាន់ Telegram -> បើកផ្ទាំង Chat ជាមួយ **Bot របស់បង**
2. ផ្ញើពាក្យ `/start`
3. ធ្វើការ **Forward វីដេអូរឿង (.mp4)** ណាមួយពី Channel ផ្សេង ឬ Upload ពីកុំព្យូទ័រផ្ញើទៅកាន់ Bot
4. Bot នឹងឆ្លើយតបមកវិញភ្លាមៗជាមួយនឹង **Direct Stream Link**៖
   ```text
   🎬 វីដេអូត្រូវបានបង្កើត Stream Link រួចរាល់!

   📁 ឈ្មោះ: Movie_Title.mp4
   📦 ទំហំ: 1.50 GB

   🔗 Direct Stream (.mp4):
   https://stream.yourdomain.com/stream/145.mp4
   ```
5. **ការយកទៅប្រើលើ WordPress (VooMov / DooPlay / Player ផ្សេងៗ)៖**
   * យក Link ខាងលើ (ឧ. `https://stream.yourdomain.com/stream/145.mp4`) ទៅ Paste ក្នុងប្រឡោះ **MP4 URL / Direct Video URL** នៃ Post ភាពយន្តរបស់បង។
   * ឬប្រើប្រាស់ជា iFrame Embed:
     ```html
     <iframe src="https://stream.yourdomain.com/embed/145" width="100%" height="500" frameborder="0" allowfullscreen></iframe>
     ```

---

## ជំហានទី ៦៖ របៀបបើក និងប្រើប្រាស់ Telegram Mini App គ្រប់គ្រងរឿង 🎬

ឥឡូវនេះ បងអាចរៀបចំកាតាឡុករឿង, បង្កើតរឿងភាគ/រឿងដុំ, បញ្ចូលភាគ, និង Copy Link ឬ Post បានយ៉ាងងាយស្រួលដោយផ្ទាល់លើ Telegram Mini App!

### ៦.១ បើក Mini App ក្នុង Telegram
1. ចូលទៅ Chat ជាមួយ Bot របស់អ្នក រួចផ្ញើពាក្យ `/start` ឬ `/app`
2. ចុចលើប៊ូតុង **« 🎬 បើកគ្រប់គ្រងរឿង (Mini App) »** នោះផ្ទាំង Mini App ដ៏ទំនើបនឹងបើកឡើងភ្លាមៗលើ Telegram!
3. ឬអាចចូលមើលតាម Browser ដោយផ្ទាល់តាម Link: `https://yourdomain.com/app`

### ៦.២ កំណត់ប៊ូតុង Menu ជាប់រហូតលើ Telegram (Persistent Menu Button)
ដើម្បីឱ្យមានប៊ូតុង Menu «🎬 គ្រប់គ្រងរឿង» នៅជ្រុងខាងក្រោមឆ្វេងដៃនៃផ្ទាំង Chat របស់ Bot ជានិច្ច៖
1. ចូលទៅកាន់ Telegram ស្វែងរក Bot **[@BotFather](https://t.me/BotFather)**
2. ផ្ញើពាក្យ `/setmenubutton`
3. ជ្រើសរើស Bot របស់អ្នក
4. ផ្ញើតំណភ្ជាប់ Mini App របស់អ្នក: `https://yourdomain.com/app` (ឧ. `https://stream.nexkh.top/app`)
5. ដាក់ឈ្មោះប៊ូតុង: `🎬 គ្រប់គ្រងរឿង`
6. រួចរាល់! ពេលនេះ Bot របស់អ្នកមានប៊ូតុង Mini App ជាប់រហូត។

---

## 🛠 ការគ្រប់គ្រង និងថែទាំ Server (Useful Commands)

* **ពិនិត្យមើលដំណើរការ Bot (Status):**
  ```bash
  systemctl status tgstream
  ```
* **Restart Bot ឡើងវិញ:**
  ```bash
  systemctl restart tgstream
  ```
* **ទាញយក Code ថ្មីបំផុត (Update Code):**
  ```bash
  cd /root/tg-stream-player && git pull && systemctl restart tgstream
  ```
* **មើល Log ពេលមានបញ្ហា:**
  ```bash
  journalctl -u tgstream -f
  ```
* **បើកដំណើរការ Nginx Video Slice Cache (ការពារ Rate Limit & Slow Video):**
  ```bash
  cd /root/tg-stream-player && git pull && bash enable_nginx_cache.sh
  ```
* **ពិនិត្យទំហំ Cache វីដេអូដែលបានរក្សាទុកលើ SSD VPS:**
  ```bash
  du -sh /var/cache/nginx/tgstream
  ```
* **សម្អាត Cache វីដេអូចោល (បើតម្រូវការ):**
  ```bash
  rm -rf /var/cache/nginx/tgstream/* && systemctl reload nginx
  ```

