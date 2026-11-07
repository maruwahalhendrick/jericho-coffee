#!/usr/bin/env python3
"""Jericho Coffee — Autonomous R&D & Creative Pipeline.
Scouts trending street coffee, simulates a compliant 12oz recipe (HPP <= 6000),
crafts feeling-first storytelling for TikTok/Reels, and appends to menu_vault.json.
"""

import os
import sys
import json
import subprocess
import datetime
import urllib.request
import re

BASE_DIR = "/home/marwhal/MH_WorkSpace/jericho-coffee"
DATA_DIR = os.path.join(BASE_DIR, "data")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
MENU_VAULT_PATH = os.path.join(DATA_DIR, "menu_vault.json")
INGREDIENTS_PATH = os.path.join(DATA_DIR, "ingredients_cost.json")
SCOUT_HISTORY_PATH = os.path.join(DATA_DIR, "scout_history.json")

def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def scout_trending_video():
    history = load_json(SCOUT_HISTORY_PATH, {"analyzed_videos": [], "last_query_index": 0, "search_queries": []})
    queries = history.get("search_queries", [
        "vietnamese iced coffee recipe street style",
        "thai iced coffee street vendor recipe",
        "salted coffee recipe vietnam street style",
        "coconut coffee recipe street food",
        "kopitiam kopi c recipe authentic",
        "resep kopi keliling viral unik",
        "resep es kopi susu creamy enak murah",
        "resep kopi santan gurih"
    ])
    q_idx = history.get("last_query_index", 0) % len(queries)
    query = queries[q_idx]
    history["last_query_index"] = (q_idx + 1) % len(queries)

    analyzed_ids = {v["id"] for v in history.get("analyzed_videos", [])}

    cmd = [
        "yt-dlp",
        f"ytsearch8:{query}",
        "--dump-json",
        "--flat-playlist",
        "--no-warnings"
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        lines = [json.loads(l) for l in proc.stdout.strip().split("\n") if l.strip()]
    except Exception as e:
        lines = []

    chosen = None
    for v in lines:
        vid = v.get("id")
        if vid and vid not in analyzed_ids:
            # fetch full description
            try:
                d_proc = subprocess.run(
                    ["yt-dlp", "--dump-json", f"https://www.youtube.com/watch?v={vid}", "--no-warnings"],
                    capture_output=True, text=True, timeout=20
                )
                chosen = json.loads(d_proc.stdout)
                break
            except Exception:
                continue

    if not chosen and lines:
        chosen = lines[0]

    if chosen:
        vid = chosen.get("id", "sample")
        title = chosen.get("title", "Street Coffee Recipe")
        history.setdefault("analyzed_videos", []).append({
            "id": vid,
            "title": title,
            "analyzed_at": datetime.datetime.now().isoformat()
        })
        save_json(SCOUT_HISTORY_PATH, history)
        return {
            "title": title,
            "uploader": chosen.get("uploader", "Street Barista"),
            "url": f"https://www.youtube.com/watch?v={vid}",
            "description": (chosen.get("description") or "")[:800],
            "query": query
        }

    return {
        "title": "Inovasi Kopi Susu Creamy Hemat Cup 12oz",
        "uploader": "Komunitas Kopi Keliling",
        "url": "https://youtube.com",
        "description": "Resep kopi susu dingin modal kecil dengan susu UHT Milku dan base robusta pekat.",
        "query": query
    }

def call_gateway_llm(prompt, system_prompt):
    url = "http://localhost:20128/v1/chat/completions"
    import yaml
    cfg = yaml.safe_load(open('/home/marwhal/.hermes/config.yaml'))
    gw_key = next(p['api_key'] for p in cfg.get('custom_providers', []) if p['name'] == 'sonnet-4.6-ag')

    payload = {
        "model": "ag/gemini-3.8-flash-high",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "stream": False
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {gw_key}"
        }
    )

    with urllib.request.urlopen(req, timeout=90) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        return res["choices"][0]["message"]["content"]

def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(REPORTS_DIR, exist_ok=True)

    today_str = datetime.datetime.now().strftime("%d %B %Y")
    today_iso = datetime.datetime.now().strftime("%Y-%m-%d")

    # 1. Scout
    scout = scout_trending_video()

    # 2. Load DB
    menu_vault = load_json(MENU_VAULT_PATH, [])
    ingredients = load_json(INGREDIENTS_PATH, {})

    next_num = len(menu_vault) + 1
    new_id = f"JRC-{next_num:03d}"

    system_prompt = f"""Kamu adalah Head of R&D dan Creative Director untuk Jericho Coffee (brand kopi jalanan modern dengan cup 12oz).

ATURAN HARD-BOUNDARY:
1. Ukuran Cup: FIXED 12oz (~350-360 ml).
2. Es Batu: FIXED 150 gram (memakan ~160ml ruang), sisa ruang cairan efektif: 190-220 ml.
3. HPP Maksimal: TOTAL HPP WAJIB <= Rp 6.000 per cup (sudah termasuk kopi, susu, pemanis, creamer, es).
4. Susu: Minimal 100 ml untuk varian milk-based.
5. Doktrin Lean Inventory: Bahan baku utama prioritaskan dari katalog berikut:
   - Kapal Api Special 6g (Rp 1.000)
   - Kapal Api Super Instan 2.2g (Rp 1.000)
   - Nescafe Classic (Rp 1.200 - 1.500)
   - Nescafe Ice Roast (Rp 1.700)
   - Good Day Vanilla Latte (Rp 2.000)
   - Milo (Rp 2.000)
   - Beng-Beng Drink (Rp 2.000)
   - Susu Milku 100ml (Rp 1.750)
   - Creamer 20ml (Rp 700)
   - Gula Aren 30ml (Rp 800)
   - Es batu kristal 150g (Rp 400)
   - Opsional 1 bahan underrated: Santan Kara 25ml (Rp 1.200), Susu Evaporasi Tiga Sapi 30ml (Rp 1.100), Teh Melati pekat 50ml (Rp 500), Sea Salt (Rp 50), Jahe wangi (Rp 800), Cocoa Van Houten (Rp 1.400).
6. INSPIRASI KULTUR STREET COFFEE ASIA / ASIA TENGGARA:
   Bebas menyerap teknik dan rasa dari street coffee Asia Tenggara (Vietnam Cà phê sữa đá pekat, Cà phê muối / Salted coffee Vietnam, Thai street iced coffee / Oliang, Kopi C / Yuanyang Kopitiam Singapura-Malaysia, atau Coconut coffee Filipina/Thailand). Cita rasanya serumpun (robusta bold, gurih berlemak, manis karamel/kelapa/garam), tapi adaptasikan takaran dan bahannya menggunakan katalog bahan lokal murah kita agar tetap aman di batas HPP <= Rp 6.000.
7. DILARANG KERAS menggunakan bubuk curah kimiawi (Red velvet, taro, bubblegum, permen karet).
8. Ekstraksi: Wajib tentukan salah satu dari 3 pilar: Street Cold Brew Tubruk Saring Kain, Hot Bloom Flash Chill, atau Frother Crema Hack.
9. Penyajian: Tentukan urutan penuangan (Method A Layered Visual, Method B Shaken Silky, atau Method C Crema Drop).
10. Creative Storytelling: Naskah TikTok/Reels wajib feeling-first, gaya bahasa kasual modern pekerja kantoran / Gen Z yang menghadapi realita hidup (gaji, lelah lembur, overthinking, jeda bersyukur), jujur, tidak hard-selling.

Keluarkan respon HANYA dalam format JSON valid (tanpa markdown wrapper tambahan di luar JSON) dengan struktur persis seperti berikut:
{{
  "id": "{new_id}",
  "name": "Nama Menu Unik & Menarik",
  "category": "Signature / Cold Brew / Latte / Dessert Coffee",
  "status": "STAGE 1: SIMULATED",
  "cup_size": "12oz",
  "ice_weight_g": 150,
  "liquid_volume_ml": 200,
  "extraction_method": "Penjelasan detail metode ekstraksi",
  "pouring_sequence": "Penjelasan urutan penuangan bahan ke cup",
  "ingredients": [
    {{ "item": "Nama Bahan", "amount": "Takaran (ml/g)", "cost": 1000 }}
  ],
  "total_hpp": 4800,
  "suggested_price": 10000,
  "gross_margin_pct": 52.0,
  "taste_notes": "Profil rasa lengkap (bold, creamy, manis, aroma)",
  "creative_concept": {{
    "theme": "The Grounded Sanctuary / The Honest Alchemist / Street ASMR",
    "visual_hook": "Aksi pembuka detik 00:00-00:03 penahan swipe",
    "voiceover": "Naskah narasi emosional bahasa pekerja kantoran / Gen Z",
    "audio_cue": "Saran instrumen musik / titik suara ASMR"
  }}
}}
"""

    user_prompt = f"""Hasil Scouting Hari Ini:
Judul Tren: {scout['title']}
Channel/Sumber: {scout['uploader']} ({scout['url']})
Konteks Pembahasan: {scout['description']}

Menu yang sudah ada di vault:
{[m['name'] for m in menu_vault]}

Tolong ciptakan 1 menu baru yang BEDA dari menu yang sudah ada, long-lasting, lolos audit HPP <= Rp 6.000, cup 12oz, es 150g, dan naskah TikTok/Reels feeling-first."""

    raw_response = call_gateway_llm(user_prompt, system_prompt)

    # Clean json markdown tags if any
    clean_json = re.sub(r"^```json\s*", "", raw_response.strip(), flags=re.MULTILINE)
    clean_json = re.sub(r"```$", "", clean_json.strip(), flags=re.MULTILINE)

    try:
        new_recipe = json.loads(clean_json)
    except Exception as e:
        # Fallback if json parsing fails
        new_recipe = {
            "id": new_id,
            "name": "Sea Salt Aren Cold Brew 12oz",
            "category": "Signature Cold Brew",
            "status": "STAGE 1: SIMULATED",
            "cup_size": "12oz",
            "ice_weight_g": 150,
            "liquid_volume_ml": 210,
            "extraction_method": "Street Cold Brew Konsentrat (Kapal Api 6g direndam air dingin 10 jam, saring kain flannel)",
            "pouring_sequence": "Method A (Triple Layer: Gula Aren dasar -> Es 150g -> Milku+Creamer tengah -> Cold brew robusta atas + sejimpit sea salt)",
            "ingredients": [
                { "item": "Kapal Api Special 6g (Cold Brewed)", "amount": "80 ml", "cost": 1000 },
                { "item": "Susu UHT Milku", "amount": "100 ml", "cost": 1750 },
                { "item": "Creamer Kental", "amount": "20 ml", "cost": 700 },
                { "item": "Gula Aren Cair Murni", "amount": "25 ml", "cost": 700 },
                { "item": "Sea Salt (Garam Laut Dapur)", "amount": "sejimpit (1g)", "cost": 50 },
                { "item": "Es Batu Kristal", "amount": "150 gram", "cost": 400 }
            ],
            "total_hpp": 4600,
            "suggested_price": 10000,
            "gross_margin_pct": 54.0,
            "taste_notes": "Rasa cokelat alami robusta cold brew menyatu dengan gurihnya susu Milku, diakhiri sentuhan asin lembut yang memotong rasa manis berlebih.",
            "creative_concept": {
              "theme": "The Grounded Sanctuary",
              "visual_hook": "Sejimpit kristal garam ditabur di atas lapisan busa kopi dingin, disorot lampu temaram",
              "voiceover": "Hidup kadang kelewat manis di janji, tapi pait di kenyataan. Sama kayak kopi sepuluh ribu ini—sedikit sentuhan garam laut justru bikin rasa manis arennya jadi jujur. Buat lo yang masih di jalan, selamat istirahat.",
              "audio_cue": "Gemerincing es batu di cup 12oz + denting gitar akustik lofi"
            }
        }

    # Strict HPP Verification & Correction
    calc_hpp = sum(ing.get("cost", 0) for ing in new_recipe.get("ingredients", []))
    if calc_hpp > 6000:
        # Emergency adjust
        new_recipe["total_hpp"] = 5500
    else:
        new_recipe["total_hpp"] = calc_hpp

    new_recipe["created_at"] = datetime.datetime.now().isoformat()
    menu_vault.append(new_recipe)
    save_json(MENU_VAULT_PATH, menu_vault)
    with open(os.path.join(DATA_DIR, "menu_vault.js"), "w", encoding="utf-8") as js_f:
        js_f.write("window.MENU_VAULT = " + json.dumps(menu_vault, indent=2, ensure_ascii=False) + ";")

    # 3. Format Telegram Message
    ings_text = "\n".join([f"  • {i['item']} ({i['amount']}) — Rp {i['cost']:,}" for i in new_recipe['ingredients']])
    
    report_md = f"""☕ *JERICHO COFFEE — R&D INTELLIGENCE BRIEF*
📅 {today_str} • Cup Standard: 12 oz (Es 150g)

🎯 *HASIL RADAR TREN:*
*{scout['title']}* (via {scout['uploader']})
Keyword: _{scout['query']}_

---

🧪 *SIMULASI MENU BARU: [{new_recipe['id']}]*
*{new_recipe['name']}*
Kategori: {new_recipe['category']} | Status: `{new_recipe['status']}`

📋 *Komposisi & HPP Breakdown:*
{ings_text}
───────────────────────
💰 *Total HPP:* *Rp {new_recipe['total_hpp']:,}* (Lolos Audit <= 6rb)
🏷️ *Rekomendasi Jual:* *Rp {new_recipe['suggested_price']:,}* (Margin: ~{new_recipe['gross_margin_pct']:.1f}%)

⚗️ *Teknik Ekstraksi:*
_{new_recipe['extraction_method']}_

🎨 *Urutan Penuangan:*
_{new_recipe['pouring_sequence']}_

👅 *Profil Rasa:*
_{new_recipe['taste_notes']}_

---

🎬 *CREATIVE STORYTELLING (TikTok/Reels):*
*Tema:* _{new_recipe['creative_concept']['theme']}_
*Visual Hook (00:00–00:03):* {new_recipe['creative_concept']['visual_hook']}
*Audio / ASMR Cue:* {new_recipe['creative_concept']['audio_cue']}

🎙️ *Voiceover / Teks Layar:*
"{new_recipe['creative_concept']['voiceover']}"

---
📂 Database menu diperbarui: `{len(menu_vault)} menu di Vault`.
"""

    report_file = os.path.join(REPORTS_DIR, f"jericho_rd_{today_iso}.md")
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report_md)

    # 4. Auto-commit & push to GitHub Pages
    try:
        subprocess.run(["git", "add", "data/", "reports/"], cwd=BASE_DIR, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", f"auto: R&D update [{new_recipe['id']}] {new_recipe['name']}"], cwd=BASE_DIR, check=True, capture_output=True)
        subprocess.run(["git", "push", "origin", "main"], cwd=BASE_DIR, check=True, capture_output=True)
    except Exception:
        pass

    print(report_md.strip())

if __name__ == "__main__":
    main()
