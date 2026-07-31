import os
import csv
import random
import requests
import ftplib
import subprocess
import html
from PIL import Image, ImageDraw, ImageFont

# ========================================================
# CONFIGURACIÓ I RUTES
# ========================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, 'posts.csv')
LOGO_PATH = os.path.join(BASE_DIR, 'logo.png')
SLIDES_DIR = os.path.join(BASE_DIR, 'public_slides')
FONT_BOLD_PATH = os.path.join(BASE_DIR, 'Poppins-Bold.ttf')
FONT_REG_PATH = os.path.join(BASE_DIR, 'Poppins-Regular.ttf')

FONT_BOLD_URL = "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Bold.ttf"
FONT_REG_URL = "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Regular.ttf"

BUFFER_ACCESS_TOKEN = os.getenv("BUFFER_ACCESS_TOKEN")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
IMGBB_API_KEY = os.getenv("IMGBB_API_KEY")

FTP_HOST = os.getenv("FTP_HOST")
FTP_USER = os.getenv("FTP_USER")
FTP_PASS = os.getenv("FTP_PASS")

def find_file_case_insensitive(filename):
    """Cerca un fitxer a BASE_DIR independentment de majúscules o extensió (.png, .PNG, .jpg, .JPG)"""
    base_name, _ = os.path.splitext(filename)
    possible_extensions = ['.png', '.PNG', '.jpg', '.JPG', '.jpeg', '.JPEG']
    for ext in possible_extensions:
        path = os.path.join(BASE_DIR, base_name + ext)
        if os.path.exists(path):
            return path
        path_cap = os.path.join(BASE_DIR, base_name.capitalize() + ext)
        if os.path.exists(path_cap):
            return path_cap
    return None

def download_font(url, save_path):
    if not os.path.exists(save_path):
        print(f"Downloading font from {url}...")
        response = requests.get(url)
        with open(save_path, 'wb') as f:
            f.write(response.content)

def wrap_text(text, draw, font, max_width):
    lines = []
    words = str(text).split(' ')
    if not words:
        return lines
    current_line = words[0]
    for word in words[1:]:
        test_line = current_line + ' ' + word
        bbox = draw.textbbox((0, 0), test_line, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = word
    lines.append(current_line)
    return lines

def send_telegram_notification(message, photo_path=None):
    """Envia la notificació en format HTML a Telegram juntament amb la imatge de portada"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("ℹ️ Telegram no configurat (s'omet la notificació).")
        return
    try:
        if photo_path and os.path.exists(photo_path):
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
            payload = {
                'chat_id': TELEGRAM_CHAT_ID,
                'caption': message,
                'parse_mode': 'HTML'
            }
            with open(photo_path, 'rb') as f:
                requests.post(url, data=payload, files={'photo': f})
        else:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {
                'chat_id': TELEGRAM_CHAT_ID,
                'text': message,
                'parse_mode': 'HTML'
            }
            requests.post(url, data=payload)
        print("📲 Notificació enviada a Telegram!")
    except Exception as e:
        print(f"⚠️ Error enviant notificació a Telegram: {e}")

def upload_via_ftp(file_path):
    if not (FTP_HOST and FTP_USER and FTP_PASS):
        return None

    filename = os.path.basename(file_path)
    try:
        ftp = ftplib.FTP(FTP_HOST, FTP_USER, FTP_PASS, timeout=30)
        try:
            ftp.cwd("public_html")
        except Exception:
            pass

        try:
            ftp.cwd("public_slides")
        except Exception:
            ftp.mkd("public_slides")
            ftp.cwd("public_slides")

        with open(file_path, 'rb') as f:
            ftp.storbinary(f'STOR {filename}', f)
        ftp.quit()

        public_url = f"https://formfriends.com/public_slides/{filename}"
        print(f"  └─ Imatge pujada per FTP a formfriends.com: {public_url}")
        return public_url
    except Exception as e:
        print(f"⚠️ Error pujant per FTP: {e}")
        return None

def upload_to_imgbb(file_path):
    if not IMGBB_API_KEY:
        return None

    url = f"https://api.imgbb.com/1/upload?key={IMGBB_API_KEY}"
    with open(file_path, 'rb') as f:
        resp = requests.post(url, files={'image': f}, timeout=30)
    
    if resp.status_code == 200:
        res_json = resp.json()
        if res_json.get('success'):
            direct_url = res_json['data']['url']
            print(f"  └─ Imatge pujada a ImgBB: {direct_url}")
            return direct_url
    return None

def get_public_image_urls(temp_files):
    if FTP_HOST and FTP_USER and FTP_PASS:
        print("🌐 Pujant imatges al teu propi servidor web (formfriends.com) via FTP...")
        ftp_urls = []
        for f_path in temp_files:
            u = upload_via_ftp(f_path)
            if u:
                ftp_urls.append(u)
        if len(ftp_urls) == len(temp_files):
            return ftp_urls

    if IMGBB_API_KEY:
        print("☁️ Pujant imatges a ImgBB...")
        imgbb_urls = []
        for f_path in temp_files:
            u = upload_to_imgbb(f_path)
            if u:
                imgbb_urls.append(u)
        if len(imgbb_urls) == len(temp_files):
            return imgbb_urls

    repo = os.getenv("GITHUB_REPOSITORY")
    branch = os.getenv("GITHUB_REF_NAME", "main")
    if repo:
        try:
            print("📦 Guardant imatges al repositori de GitHub...")
            subprocess.run(["git", "config", "user.name", "github-actions[bot]"], check=True)
            subprocess.run(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"], check=True)
            subprocess.run(["git", "add", "public_slides/"], check=True)
            subprocess.run(["git", "commit", "-m", "upload: add slide images for Buffer"], check=False)
            subprocess.run(["git", "push"], check=False)
        except Exception:
            pass

        raw_urls = []
        for f_path in temp_files:
            fname = os.path.basename(f_path)
            raw_url = f"https://raw.githubusercontent.com/{repo}/{branch}/public_slides/{fname}"
            raw_urls.append(raw_url)
        return raw_urls

    raise Exception("❌ No s'ha pogut obtenir cap URL pública.")

def post_to_buffer(token, image_urls, caption):
    buffer_url = "https://api.buffer.com"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    org_query = """
    query GetOrganizations {
      account {
        organizations {
          id
          name
        }
      }
    }
    """
    resp = requests.post(buffer_url, headers=headers, json={"query": org_query})
    if resp.status_code != 200:
        return False

    res_json = resp.json()
    if "errors" in res_json:
        return False

    organizations = res_json.get("data", {}).get("account", {}).get("organizations", [])
    if not organizations:
        return False

    channels_query = """
    query GetChannels($input: ChannelsInput!) {
      channels(input: $input) {
        id
        name
        displayName
        service
      }
    }
    """

    channels = []
    for org in organizations:
        org_id = org["id"]
        c_resp = requests.post(buffer_url, headers=headers, json={
            "query": channels_query,
            "variables": {"input": {"organizationId": org_id}}
        })
        if c_resp.status_code == 200:
            c_data = c_resp.json()
            if "data" in c_data and "channels" in c_data["data"]:
                channels.extend(c_data["data"]["channels"] or [])

    if not channels:
        return False

    channel_list_str = [f"{c.get('displayName') or c.get('name')} ({c.get('service')})" for c in channels]
    print(f"📡 Canals trobats a Buffer ({len(channels)}): {channel_list_str}")

    assets = [{"image": {"url": url}} for url in image_urls]

    mutation = """
    mutation CreatePost($input: CreatePostInput!) {
      createPost(input: $input) {
        ... on PostActionSuccess {
          post {
            id
            text
          }
        }
        ... on MutationError {
          message
        }
        ... on InvalidInputError {
          message
        }
        ... on UnauthorizedError {
          message
        }
      }
    }
    """

    all_success = True
    for channel in channels:
        channel_id = channel["id"]
        service_name = str(channel.get("service", "")).lower()
        channel_display_name = channel.get('displayName') or channel.get('name') or channel_id

        # EXCLUSIÓ: Ignorem els canals de YouTube per a la publicació d'imatges estàtiques
        if "youtube" in service_name:
            print(f"ℹ️ Ometent el canal {channel_display_name} ({service_name}) ja que és un carrousel d'imatges estàtiques.")
            continue

        channel_input = {
            "channelId": channel_id,
            "text": caption,
            "schedulingType": "automatic",
            "mode": "shareNow",
            "assets": assets
        }

        if "instagram" in service_name:
            channel_input["metadata"] = {
                "instagram": {
                    "type": "post",
                    "shouldShareToFeed": True
                }
            }

        variables = {"input": channel_input}

        post_resp = requests.post(buffer_url, headers=headers, json={"query": mutation, "variables": variables})
        if post_resp.status_code == 200:
            res_payload = post_resp.json()
            if "errors" in res_payload:
                print(f"❌ Error al canal {channel_display_name} ({service_name}): {res_payload['errors']}")
                all_success = False
            else:
                post_data = res_payload.get("data", {}).get("createPost", {})
                if "post" in post_data:
                    print(f"✅ Carrousel publicat amb èxit al canal {channel_display_name} ({service_name})!")
                else:
                    error_msg = post_data.get("message", "Error desconegut")
                    print(f"❌ Error al canal {channel_display_name} ({service_name}): {error_msg}")
                    all_success = False
        else:
            print(f"❌ Error HTTP al canal {channel_display_name}: {post_resp.text}")
            all_success = False

    return all_success

def main():
    download_font(FONT_BOLD_URL, FONT_BOLD_PATH)
    download_font(FONT_REG_URL, FONT_REG_PATH)

    os.makedirs(SLIDES_DIR, exist_ok=True)

    if not os.path.exists(CSV_PATH):
        print(f"❌ Error: CSV file not found at {CSV_PATH}")
        return

    rows = []
    headers = []
    with open(CSV_PATH, mode='r', encoding='utf-8') as f:
        reader = csv.reader(f)
        try:
            headers = next(reader)
        except StopIteration:
            print("❌ Error: CSV file is empty")
            return
        for r in reader:
            rows.append(r)

    if 'Status' not in headers:
        headers.append('Status')
        for r in rows:
            r.append('')

    status_col_idx = headers.index('Status')

    current_row_idx = None
    post_data = None
    for idx, r in enumerate(rows):
        while len(r) < len(headers):
            r.append('')
        status_val = r[status_col_idx].strip().lower()
        if status_val != 'done':
            current_row_idx = idx
            post_data = dict(zip(headers, r))
            break

    if current_row_idx is None:
        print("🎉 Tot el CSV està completat!")
        send_telegram_notification("🎉 <b>Tots els posts del CSV s'han publicat!</b>")
        return

    post_id = post_data.get('Post_ID', f"Post_{current_row_idx + 1}")
    print(f"🚀 Generant imatges i caption per {post_id}...")

    width, height = 1080, 1080
    dark_backgrounds = ['#101520', '#161F2B', '#121824', '#1A2A30', '#181A1B', '#4A0E17', '#34050B']
    bg_color = random.choice(dark_backgrounds)

    cta_pool = [
        "Find out who knows you best. Link in bio",
        "Get your custom story link and let your friends vote. Link in bio",
        "Discover your group's unfiltered opinions. Link in bio",
        "Put your friendship to the test. Link in bio"
    ]
    selected_cta = random.choice(cta_pool)

    slides = [
        {"type": "title", "text": post_data.get('Slide_1_Title', '')},
        {"type": "question", "text": post_data.get('Slide_2_Question', '')},
        {"type": "question", "text": post_data.get('Slide_3_Question', '')},
        {"type": "question", "text": post_data.get('Slide_4_Question', '')},
        {"type": "question", "text": post_data.get('Slide_5_Question', '')},
        {"type": "question", "text": post_data.get('Slide_6_Question', '')},
        {"type": "cta", "text": selected_cta}
    ]

    try:
        font_title = ImageFont.truetype(FONT_BOLD_PATH, 54)
        font_text = ImageFont.truetype(FONT_REG_PATH, 44)
    except Exception:
        font_title = ImageFont.load_default()
        font_text = ImageFont.load_default()

    mockup_path = find_file_case_insensitive('mockup.png')
    logo_path_found = find_file_case_insensitive('logo.png')

    logo_img = None
    if logo_path_found:
        try:
            logo_img = Image.open(logo_path_found).convert('RGBA')
            max_logo_height = 120
            w_percent = (max_logo_height / float(logo_img.size[1]))
            max_logo_width = int((float(logo_img.size[0]) * float(w_percent)))
            logo_img = logo_img.resize((max_logo_width, max_logo_height), Image.Resampling.LANCZOS)
        except Exception:
            pass

    temp_files = []

    for i, slide in enumerate(slides):
        bg = Image.new('RGBA', (width, height), color=bg_color)
        card_layer = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        draw_card = ImageDraw.Draw(card_layer)

        card_margin = 80
        draw_card.rounded_rectangle(
            [(card_margin, card_margin), (width - card_margin, height - card_margin)],
            radius=40, fill=(255, 255, 255, 25), outline=(255, 255, 255, 90), width=2
        )

        img = Image.alpha_composite(bg, card_layer).convert('RGB')
        draw = ImageDraw.Draw(img)

        if i > 0 and slide["type"] == "question":
            pb_x_start = card_margin + 60
            pb_x_end = width - card_margin - 60
            pb_y = card_margin + 60
            pb_width = pb_x_end - pb_x_start
            pb_height = 8

            draw.rounded_rectangle([(pb_x_start, pb_y), (pb_x_end, pb_y + pb_height)], radius=4, fill=(255, 255, 255, 255))
            num_questions = 5
            progress_percent = i / float(num_questions)
            cover_x_start = int(pb_x_start + (pb_width * progress_percent))

            if cover_x_start < pb_x_end:
                draw.rounded_rectangle([(cover_x_start, pb_y - 1), (pb_x_end + 1, pb_y + pb_height + 1)], radius=4, fill=bg_color)

        current_font = font_title if slide["type"] in ["title", "cta"] else font_text
        max_text_width = width - (card_margin * 4)
        wrapped_lines = wrap_text(slide["text"], draw, current_font, max_text_width)

        line_heights = [draw.textbbox((0, 0), l, font=current_font)[3] - draw.textbbox((0, 0), l, font=current_font)[1] for l in wrapped_lines]
        total_text_height = sum(line_heights) + (20 * (len(wrapped_lines) - 1))

        current_y = card_margin + 60 if slide["type"] == "cta" else (height - total_text_height) / 2

        for line in wrapped_lines:
            bbox = draw.textbbox((0, 0), line, font=current_font)
            text_w = bbox[2] - bbox[0]
            current_x = (width - text_w) / 2
            draw.text((current_x, current_y), line, fill='#FFFFFF', font=current_font)
            current_y += (bbox[3] - bbox[1]) + 20

        if logo_img and slide["type"] != "cta":
            logo_x = int((width - logo_img.size[0]) / 2)
            logo_y = height - 235
            img.paste(logo_img, (logo_x, logo_y), logo_img)

        # Enganxar el Mockup (mida ajustada 550px, Y = 390 per deixar aire sota del text)
        if slide["type"] == "cta" and mockup_path:
            try:
                mockup_img = Image.open(mockup_path).convert('RGBA')
                
                # 1. Eliminar espais buits transparents del fitxer
                bbox = mockup_img.getbbox()
                if bbox:
                    mockup_img = mockup_img.crop(bbox)
                
                w_orig, h_orig = mockup_img.size
                
                # 2. Retallem al 70% per incloure Spicy Questions i Ultimate Roast
                mockup_img = mockup_img.crop((0, 0, w_orig, int(h_orig * 0.70)))
                
                # 3. Reescalem l'amplada a 550px (mida mitjana fi i elegant)
                target_width = 550
                w_percent = (target_width / float(mockup_img.size[0]))
                target_height = int((float(mockup_img.size[1]) * float(w_percent)))
                mockup_img = mockup_img.resize((target_width, target_height), Image.Resampling.LANCZOS)
                
                # 4. Posicionem a Y = 390px per deixar espai sota de "Link in bio"
                mockup_x = int((width - target_width) / 2)
                mockup_y = 390
                
                img.paste(mockup_img, (mockup_x, mockup_y), mockup_img)
                print(f"Pasted well-proportioned mockup ({os.path.basename(mockup_path)}) onto CTA slide.")
            except Exception as e:
                print(f"⚠️ Error processant mockup: {e}")

        file_name = os.path.join(SLIDES_DIR, f"{post_id}_slide_{i+1}.jpg")
        img.save(file_name, "JPEG", quality=95)
        temp_files.append(file_name)

    print("Generated 7 slide images in JPEG format.")

    hashtag_pool = ['#friendforms', '#socialexperiment', '#perspective', '#humanconnection', '#mindset', '#deepconversations', '#socialgame', '#connection']
    chosen_hashtags = random.sample(hashtag_pool, 4)
    chosen_hashtags.append('#questions')
    tags_string = " ".join(chosen_hashtags)

    captions = [
        f"Decks like this are meant to expose what we usually leave unsaid.\n\nSwipe through, process the prompts, and let us know your take.\n\n👇 Which slide hit closest to home?\n\n—\n{tags_string}",
        f"A simple card can spark the most unexpected conversations.\n\n📌 Tag that one friend who needs to answer Slide 6.\n\n—\n{tags_string}"
    ]
    selected_caption = random.choice(captions)

    if not BUFFER_ACCESS_TOKEN:
        print("⚠️ Warning: BUFFER_ACCESS_TOKEN no està configurat als Secrets de GitHub.")
        return

    public_urls = get_public_image_urls(temp_files)

    print("📤 Enviant el carrousel a Buffer via GraphQL API...")
    success = post_to_buffer(BUFFER_ACCESS_TOKEN, public_urls, selected_caption)

    if success:
        title_text = html.escape(post_data.get('Slide_1_Title', ''))
        telegram_msg = (
            f"🚀 <b>{post_id} publicat amb èxit!</b>\n\n"
            f"📱 <b>Destí:</b> Instagram &amp; TikTok\n"
            f"📖 <b>Portada:</b> {title_text}\n"
            f"🏷️ <b>Hashtags:</b> {tags_string}"
        )
        send_telegram_notification(telegram_msg, photo_path=temp_files[0])

        rows[current_row_idx][status_col_idx] = 'Done'
        with open(CSV_PATH, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)
        print(f"📝 CSV actualitzat! Fila {current_row_idx + 1} ({post_id}) marcada com a 'Done'.")
    else:
        send_telegram_notification(f"❌ <b>Error en publicar {post_id} a Buffer.</b>")

if __name__ == "__main__":
    main()
