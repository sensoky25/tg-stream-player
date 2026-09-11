# របៀបដាក់ Telegram Stream Server លើ Hugging Face Spaces (Free 24/7 🚀)

ការដាក់ដំណើរការលើ **Hugging Face Spaces** គឺ **ឥតគិតថ្លៃ 100%**, មិនបាច់ដាក់កាតធនាគារ, ផ្ដល់កម្លាំង **2 vCPU, 16GB RAM** និងដំណើរការ **24/7** ទោះបីអ្នកបិទកុំព្យូទ័រក៏ដោយ!

---

### ជំហានទី ១៖ បង្កើត Space ថ្មីលើ Hugging Face

1. ចូលទៅកាន់គេហទំព័រ [https://huggingface.co](https://huggingface.co)
   *(ប្រសិនបើមិនទាន់មាន Account ទេ សូមចុច Sign Up ចុះឈ្មោះដោយឥតគិតថ្លៃ)*
2. បន្ទាប់មកចូលទៅកាន់ Link នេះដើម្បីបង្កើត Space ថ្មី៖
   👉 [https://huggingface.co/new-space](https://huggingface.co/new-space)
3. បំពេញព័ត៌មានដូចខាងក្រោម៖
   * **Space name:** `tg-video-stream` *(ឬឈ្មោះអ្វីក៏បាន)*
   * **License:** ជ្រើសរើស `mit` ឬ `apache-2.0`
   * **Space SDK:** 👉 **ជ្រើសរើសយក "Docker"** -> រួចយក **"Blank"**
   * **Space hardware:** យក **"CPU basic • 2 vCPU • 16 GB • Free"** (ឥតគិតថ្លៃ)
   * **Visibility:** យក **Public**
4. ចុចប៊ូតុង **"Create Space"**

---

### ជំហានទី ២៖ Upload កូដចូលក្នុង Space

1. នៅក្នុង Space ដែលទើបបង្កើតរួច សូមចុចលើផ្ទាំង **"Files"** (នៅខាងលើជាប់ App)
2. ចុចប៊ូតុង **"Add file"** -> ជ្រើសរើស **"Upload files"**
3. ចូលទៅកាន់ Folder លើកុំព្យូទ័ររបស់អ្នក៖
   `c:\Users\ASUS\Downloads\Telegram Desktop\tg-stream-player`
   រួចអូសទម្លាក់ (Drag & Drop) ឯកសារទាំងនេះចូល៖
   - `Dockerfile`
   - `requirements.txt`
   - `server.py`
   - `config.py`
   - Folder `templates` (ដែលមាន `index.html`, `player.html`, `embed.html`)
4. នៅផ្នែកខាងក្រោម ចុចប៊ូតុងពណ៌ទឹកក្រូច **"Commit changes to main"**

---

### ជំហានទី ៣៖ បំពេញ Variables & Secrets (សំខាន់បំផុត 🔑)

1. ចុចលើផ្ទាំង **"Settings"** នៃ Space នោះ (នៅជិតផ្ទាំង Files)
2. អូសចុះក្រោមបន្តិច រកពាក្យ **"Variables and secrets"**
3. នៅត្រង់ **Variables** ចុចប៊ូតុង **"New variable"** រួចបញ្ចូលម្ដងមួយៗដូចខាងក្រោម៖

| Name | Value |
| :--- | :--- |
| `API_ID` | `38606693` |
| `API_HASH` | `4784d8963ea114bcd26dd59d84f997ad` |
| `BOT_TOKEN` | `8445405147:AAH51CWfNzBADynBFcGV1yHb5gcraKCnlfY` |
| `BIN_CHANNEL` | `-1003909046470` |
| `PORT` | `7860` |
| `FQDN` | URL នៃ Space របស់អ្នក (ឧ. `https://yourname-tg-video-stream.hf.space`) |

*(ចំណាំ៖ URL នៃ Space របស់អ្នក អាចមើលបានដោយចុចលើសញ្ញា **Dots (⋮)** នៅជ្រុងលើខាងស្ដាំ នៃ Space រួចយក **Embed this Space** ឬ **Direct URL**)*

---

### ជំហានទី ៤៖ រួចរាល់! 🎉
* Hugging Face នឹងចាប់ផ្ដើម Build Docker ប្រហែល ១ ទៅ ២ នាទី។
* នៅពេលវាលោតអក្សរពណ៌បៃតង **"Running"** មានន័យថា Server និង Bot របស់អ្នកដំណើរការ 24/7 ដោយជោគជ័យហើយ!
* អ្នកអាចបិទកុំព្យូទ័ររបស់អ្នកចោលបានដោយសុវត្ថិភាព វីដេអូទាំងអស់នៅតែបន្តចាក់លើគេហទំព័រ WordPress របស់អ្នកជានិច្ច!
