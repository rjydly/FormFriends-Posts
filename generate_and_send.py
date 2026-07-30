import os
import csv
import random
import requests
from PIL import Image, ImageDraw, ImageFont

# ========================================================
# CONFIGURACIÓ I RUTES
# ========================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, 'posts.csv')
LOGO_PATH = os.path.join(BASE_DIR, 'logo.png')
MOCKUP_PATH = os.path.join(BASE_DIR, 'mockup.png')
FONT_BOLD_PATH = os.path.join(BASE_DIR, 'Poppins-Bold.ttf')
FONT_REG_PATH = os.path.join(BASE_DIR, 'Poppins-Regular.ttf')

FONT_BOLD_URL = "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Bold.ttf"
FONT_REG_URL = "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Regular.ttf"

BUFFER_ACCESS_TOKEN = os.getenv("BUFFER_ACCESS_TOKEN")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

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
    """Envia un missatge/notificació al teu Telegram de confirmació"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("ℹ️ Telegram no configurat (s'omet la notificació).")
        return
    try:
        if photo_path and os.path.exists(photo_path):
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
            with open(photo_path, 'rb') as f:
                requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'caption': message}, files={'photo': f})
        else:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'text': message})
        print("📲 Notificació enviada a Telegram!")
    except Exception as e:
        print(f"⚠️ Error enviant notificació a Telegram: {e}")

def upload_image_to_temp_host(file_path):
    """Puja una imatge a tmpfiles.org per obtenir una URL pública temporal"""
    url = "https://tmpfiles.org/api/v1/upload"
    with open(file_path, 'rb') as f:
        response = requests.post(url, files={'file': f})
    if response.status_code == 200:
        res_json = response.json()
        raw_url = res_json['data']['url']
        direct_url = raw_url.replace("tmpfiles.org/", "tmpfiles.org/dl/")
        return direct_url
    else:
        raise Exception(f"Failed to upload image: {response.text}")

def post_to_buffer(token, image_urls, caption):
    """Envia el carrousel a tots els canals utilitzant la GraphQL API oficial de Buffer"""
    buffer_url = "https://api.buffer.com"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # 1. Pas 1: Obtenir l'ID de l'organització
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
        print(f"❌ Error HTTP consultant Buffer: {resp.status_code} - {resp.text}")
        return False

    res_json = resp.json()
    if "errors" in res_json:
        print(f"❌ Error obtenint organitzacions de Buffer: {res_json['errors']}")
        return False

    organizations = res_json.get("data", {}).get("account", {}).get("organizations", [])
    if not organizations:
        print("❌ No s'han trobat organitzacions al teu compte de Buffer.")
        return False

    # 2. Pas 2: Obtenir els canals de cada organització
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
        print("❌ No s'han trobat canals connectats a Buffer.")
        return False

    print(f"📡 Canals trobats a Buffer ({len(channels)}): {[c.get('displayName') or c.get('name') or c.get('service') for c in channels]}")

    # Preparem la llista d'assets d'imatges per al carrousel
    assets = [{"image": {"url": url}} for url in image_urls]

    # 3. Pas 3: Crear la publicació a cada canal
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
      }
    }
    """

    all_success = True
    for channel in channels:
        channel_id = channel["id"]
        variables = {
            "input": {
                "channelId": channel_id,
                "text": caption,
                "schedulingType": "automatic",
                "mode": "shareNow",  # O "addToQueue" si prefereixes afegir a la cua
                "assets": assets
            }
        }

        post_resp = requests.post(buffer_url, headers=headers, json={"query": mutation, "variables": variables})
        if post_resp.status_code == 200:
            post_data = post_resp.json().get("data", {}).get("createPost", {})
            if "post" in post_data:
                print(f"✅ Carrousel publicat amb èxit al canal {channel.get('displayName') or channel.get('name', channel_id)}!")
            else:
                error_msg = post_data.get("message", "Error desconegut")
                print(f"❌ Error al canal {channel.get('name', channel_id)}: {error_msg}")
                all_success = False
        else:
            print(f"❌ Error HTTP al canal {channel_id}: {post_resp.text}")
            all_success = False

    return all_success

def main():
    download_font(FONT_BOLD_URL, FONT_BOLD_PATH)
    download_font(FONT_REG_URL, FONT_REG_PATH)

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
        send_telegram_notification("🎉 Tots els posts del CSV s'han publicat!")
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

    logo_img = None
    if os.path.exists(LOGO_PATH):
        try:
            logo_img = Image.open(LOGO_PATH).convert('RGBA')
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

        if slide["type"] == "cta" and os.path.exists(MOCKUP_PATH):
            try:
                mockup_img = Image.open(MOCKUP_PATH).convert('RGBA')
                w_orig, h_orig = mockup_img.size
                mockup_img = mockup_img.crop((0, 0, w_orig, int(h_orig * 0.69)))
                max_m_height = 790
                w_percent = (max_m_height / float(mockup_img.size[1]))
                max_m_width = int((float(mockup_img.size[0]) * float(w_percent)))
                mockup_img = mockup_img.resize((max_m_width, max_m_height), Image.Resampling.LANCZOS)
                mockup_x = int((width - mockup_img.size[0]) / 2)
                mockup_y = height - mockup_img.size[1]
                img.paste(mockup_img, (mockup_x, mockup_y), mockup_img)
            except Exception as e:
                print(f"⚠️ Mockup error: {e}")

        file_name = os.path.join(BASE_DIR, f"{post_id}_slide_{i+1}.png")
        img.save(file_name, "PNG")
        temp_files.append(file_name)

    print("Generated 7 slide images.")

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

    print("☁️ Pujant imatges a servidor temporal per generar URLs públiques...")
    public_urls = []
    for f_path in temp_files:
        p_url = upload_image_to_temp_host(f_path)
        public_urls.append(p_url)

    print("📤 Enviant el carrousel a Buffer via GraphQL API...")
    success = post_to_buffer(BUFFER_ACCESS_TOKEN, public_urls, selected_caption)

    if success:
        telegram_msg = f"🚀 **{post_id} Publicat amb èxit!**\n\n📱 **Destí:** Instagram & TikTok (Buffer)\n\n📝 **Caption:**\n{selected_caption}"
        send_telegram_notification(telegram_msg, photo_path=temp_files[0])

        rows[current_row_idx][status_col_idx] = 'Done'
        with open(CSV_PATH, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)
        print(f"📝 CSV actualitzat! Fila {current_row_idx + 1} ({post_id}) marcada com a 'Done'.")
    else:
        send_telegram_notification(f"❌ Error en publicar **{post_id}** a Buffer.")

    # Neteja de fitxers locals
    for file_path in temp_files:
        try:
            os.remove(file_path)
        except OSError:
            pass

if __name__ == "__main__":
    main()
