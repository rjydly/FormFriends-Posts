import os
import csv
import random
import requests
import ftplib
import subprocess
import html
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Importació intel·ligent compatible amb MoviePy v1 i v2
try:
    from moviepy.editor import VideoClip, AudioFileClip, concatenate_videoclips, concatenate_audioclips
except ModuleNotFoundError:
    from moviepy import VideoClip, AudioFileClip, concatenate_videoclips, concatenate_audioclips

# ========================================================
# CONFIGURACIÓ I RUTES
# ========================================================
TEST_MODE = True  # Canvia a False quan vulguis publicar a xarxes socials (Buffer)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, 'video_posts.csv')
LOGO_PATH = os.path.join(BASE_DIR, 'logo.png')
MUSIC_DIR = os.path.join(BASE_DIR, 'music')
PUBLIC_VIDEOS_DIR = os.path.join(BASE_DIR, 'public_slides')

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


def download_font(url, save_path):
    if not os.path.exists(save_path):
        print(f"📥 Descarregant font de {url}...")
        res = requests.get(url)
        with open(save_path, 'wb') as f:
            f.write(res.content)


def find_file_case_insensitive(filename):
    base_name, _ = os.path.splitext(filename)
    possible_extensions = ['.png', '.PNG', '.jpg', '.JPG', '.jpeg', '.JPEG']
    for ext in possible_extensions:
        path = os.path.join(BASE_DIR, base_name + ext)
        if os.path.exists(path):
            return path
    return None


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


def send_telegram_video_notification(message, video_path):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram no configurat als Secrets de GitHub.")
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
        payload = {
            'chat_id': TELEGRAM_CHAT_ID,
            'caption': message,
            'parse_mode': 'HTML'
        }
        with open(video_path, 'rb') as f:
            requests.post(url, data=payload, files={'video': f})
        print("📲 Vídeo enviat amb èxit a Telegram!")
    except Exception as e:
        print(f"⚠️ Error enviant el vídeo a Telegram: {e}")


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
        print(f"  └─ Vídeo pujat per FTP a formfriends.com: {public_url}")
        return public_url
    except Exception as e:
        print(f"⚠️ Error pujant vídeo per FTP: {e}")
        return None


def get_public_video_url(file_path):
    if FTP_HOST and FTP_USER and FTP_PASS:
        print("🌐 Pujant vídeo al teu servidor web via FTP...")
        u = upload_via_ftp(file_path)
        if u:
            return u

    repo = os.getenv("GITHUB_REPOSITORY")
    branch = os.getenv("GITHUB_REF_NAME", "main")
    if repo:
        try:
            print("📦 Guardant vídeo al repositori de GitHub CDN...")
            subprocess.run(["git", "config", "user.name", "github-actions[bot]"], check=True)
            subprocess.run(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"], check=True)
            subprocess.run(["git", "add", "public_slides/"], check=True)
            subprocess.run(["git", "commit", "-m", "upload: add video for Buffer"], check=False)
            subprocess.run(["git", "push"], check=False)
        except Exception:
            pass

        fname = os.path.basename(file_path)
        return f"https://raw.githubusercontent.com/{repo}/{branch}/public_slides/{fname}"

    raise Exception("❌ No s'ha pogut obtenir cap URL pública per al vídeo.")


def post_video_to_buffer(token, video_url, caption):
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
    if resp.status_code != 200 or "errors" in resp.json():
        return False

    organizations = resp.json().get("data", {}).get("account", {}).get("organizations", [])
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
        c_resp = requests.post(buffer_url, headers=headers, json={
            "query": channels_query,
            "variables": {"input": {"organizationId": org["id"]}}
        })
        if c_resp.status_code == 200:
            c_data = c_resp.json()
            if "data" in c_data and "channels" in c_data["data"]:
                channels.extend(c_data["data"]["channels"] or [])

    if not channels:
        return False

    channel_list_str = [f"{c.get('displayName') or c.get('name')} ({c.get('service')})" for c in channels]
    print(f"📡 Canals trobats a Buffer ({len(channels)}): {channel_list_str}")

    assets = [{"video": {"url": video_url}}]

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
        service_name = str(channel.get("service", "")).lower()
        channel_display_name = channel.get('displayName') or channel.get('name') or channel_id

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
                    "type": "reel",
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
                    print(f"✅ Vídeo publicat amb èxit al canal {channel_display_name} ({service_name})!")
                else:
                    error_msg = post_data.get("message", "Error desconegut")
                    print(f"❌ Error al canal {channel_display_name} ({service_name}): {error_msg}")
                    all_success = False
        else:
            print(f"❌ Error HTTP al canal {channel_display_name}: {post_resp.text}")
            all_success = False

    return all_success


def render_base_slide(width, height, bg_color, header_text, main_text, font_title, font_text, logo_img=None, is_title=False):
    """Genera la imatge base de la targeta en format RGBA per mantenir la transparència neta"""
    bg = Image.new('RGBA', (width, height), color=bg_color)

    card_layer = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw_card = ImageDraw.Draw(card_layer)
    card_margin = 80
    top_margin = 220
    bottom_margin = 200

    draw_card.rounded_rectangle(
        [(card_margin, top_margin), (width - card_margin, height - bottom_margin)],
        radius=40, fill=(255, 255, 255, 20), outline=(255, 255, 255, 80), width=2
    )

    img = Image.alpha_composite(bg, card_layer)
    draw = ImageDraw.Draw(img)

    # 1. Capçalera superior ("FormFriends")
    bbox_h = draw.textbbox((0, 0), header_text, font=font_title)
    h_w = bbox_h[2] - bbox_h[0]
    draw.text(((width - h_w) / 2, 260), header_text, fill='#FFFFFF', font=font_title)

    # 2. Text Principal
    current_font = font_title if is_title else font_text
    max_text_w = width - (card_margin * 4)
    wrapped_lines = wrap_text(main_text, draw, current_font, max_text_w)

    line_heights = [draw.textbbox((0, 0), l, font=current_font)[3] - draw.textbbox((0, 0), l, font=current_font)[1] for l in wrapped_lines]
    total_text_h = sum(line_heights) + (24 * (len(wrapped_lines) - 1))

    current_y = (height - total_text_h) / 2

    for line in wrapped_lines:
        bbox = draw.textbbox((0, 0), line, font=current_font)
        text_w = bbox[2] - bbox[0]
        current_x = (width - text_w) / 2
        draw.text((current_x, current_y), line, fill='#FFFFFF', font=current_font)
        current_y += (bbox[3] - bbox[1]) + 24

    # 3. Logo inferior
    if logo_img:
        logo_x = int((width - logo_img.size[0]) / 2)
        logo_y = height - 360
        img.paste(logo_img, (logo_x, logo_y), logo_img)

    return img


def create_slide_clip_with_progress_bar(base_rgba_image, duration, fps=24):
    """Dibuixa la barra de progrés en capes RGBA per a un animat perfecte i fluid"""
    w, h = base_rgba_image.size

    def make_frame(t):
        progress = min(max(t / duration, 0.0), 1.0)
        
        # Capa transparent independent per a la barra de progrés
        overlay = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        draw_overlay = ImageDraw.Draw(overlay)

        bar_margin = 100
        bar_y = 120
        bar_height = 12
        max_bar_w = w - (bar_margin * 2)

        # Fons de la barra (blanc translúcid)
        draw_overlay.rounded_rectangle(
            [(bar_margin, bar_y), (bar_margin + max_bar_w, bar_y + bar_height)],
            radius=6,
            fill=(255, 255, 255, 70)
        )

        # Barra de progrés que s'omple (blanc intens)
        current_w = int(max_bar_w * progress)
        if current_w > 6:
            draw_overlay.rounded_rectangle(
                [(bar_margin, bar_y), (bar_margin + current_w, bar_y + bar_height)],
                radius=6,
                fill=(255, 255, 255, 255)
            )

        # Composició de capes RGBA
        final_frame = Image.alpha_composite(base_rgba_image, overlay)
        return np.array(final_frame.convert('RGB'))

    clip = VideoClip(make_frame, duration=duration)
    
    # Efecte de Fade-In i Fade-Out suau entre targetes (0.3s)
    if hasattr(clip, "fadein") and hasattr(clip, "fadeout"):
        clip = clip.fadein(0.3).fadeout(0.3)

    return clip


def main():
    download_font(FONT_BOLD_URL, FONT_BOLD_PATH)
    download_font(FONT_REG_URL, FONT_REG_PATH)

    os.makedirs(PUBLIC_VIDEOS_DIR, exist_ok=True)

    if not os.path.exists(CSV_PATH):
        print(f"❌ Error: Fitxer CSV no trobat a {CSV_PATH}")
        return

    rows = []
    headers = []
    with open(CSV_PATH, mode='r', encoding='utf-8') as f:
        reader = csv.reader(f)
        try:
            headers = next(reader)
        except StopIteration:
            print("❌ Error: Fitxer CSV buit")
            return
        for r in reader:
            rows.append(r)

    if 'Status' not in headers:
        headers.append('Status')
        for r in rows:
            r.append('')

    status_col_idx = headers.index('Status')

    current_row_idx = None
    video_data = None
    for idx, r in enumerate(rows):
        while len(r) < len(headers):
            r.append('')
        status_val = r[status_col_idx].strip().lower()
        if status_val != 'done':
            current_row_idx = idx
            video_data = dict(zip(headers, r))
            break

    if current_row_idx is None:
        print("🎉 Tots els vídeos del CSV estan completats!")
        return

    video_id = video_data.get('Video_ID', f"Video_{current_row_idx + 1}")
    print(f"🎬 Generant vídeo per a {video_id} (Mode Prova = {TEST_MODE})...")

    # Mides 9:16 per a Reels/TikTok/Shorts
    width, height = 1080, 1920

    # Paleta de fons foscos estètics elegants
    dark_colors = [
        '#101520', '#161F2B', '#121824', '#1A2A30', '#181A1B',
        '#2C1420', '#1B2A26', '#281E12', '#1E1E28', '#251818',
        '#142028', '#1F1728', '#221915', '#13221C'
    ]

    # Slide 1 portada (5s), Slides 2-6 preguntes (9s cada una)
    slides = [
        {"text": video_data.get('Slide_1_Title', ''), "duration": 5.0, "is_title": True},
        {"text": video_data.get('Slide_2_Question', ''), "duration": 9.0, "is_title": False},
        {"text": video_data.get('Slide_3_Question', ''), "duration": 9.0, "is_title": False},
        {"text": video_data.get('Slide_4_Question', ''), "duration": 9.0, "is_title": False},
        {"text": video_data.get('Slide_5_Question', ''), "duration": 9.0, "is_title": False},
        {"text": video_data.get('Slide_6_Question', ''), "duration": 9.0, "is_title": False},
    ]

    try:
        font_title = ImageFont.truetype(FONT_BOLD_PATH, 58)
        font_text = ImageFont.truetype(FONT_REG_PATH, 48)
    except Exception:
        font_title = ImageFont.load_default()
        font_text = ImageFont.load_default()

    logo_path_found = find_file_case_insensitive('logo.png')
    logo_img = None
    if logo_path_found:
        try:
            logo_img = Image.open(logo_path_found).convert('RGBA')
            max_logo_h = 130
            w_perc = (max_logo_h / float(logo_img.size[1]))
            max_logo_w = int((float(logo_img.size[0]) * float(w_perc)))
            logo_img = logo_img.resize((max_logo_w, max_logo_h), Image.Resampling.LANCZOS)
        except Exception:
            pass

    # Generar clips de vídeo per a cada slide amb la barra de progrés i transicions
    video_clips = []
    fps = 24

    for i, slide in enumerate(slides):
        bg_color = random.choice(dark_colors)
        header_text = "FormFriends"

        base_img = render_base_slide(
            width, height, bg_color,
            header_text, slide["text"],
            font_title, font_text,
            logo_img=logo_img,
            is_title=slide["is_title"]
        )

        clip = create_slide_clip_with_progress_bar(base_img, slide["duration"], fps=fps)
        video_clips.append(clip)

    final_video = concatenate_videoclips(video_clips)
    total_duration = final_video.duration

    # Selecció aleatòria de música de la carpeta music/
    music_file = None
    if os.path.exists(MUSIC_DIR):
        possible_tracks = [os.path.join(MUSIC_DIR, f) for f in os.listdir(MUSIC_DIR) if f.lower().endswith(('.mp3', '.m4a', '.wav'))]
        if possible_tracks:
            music_file = random.choice(possible_tracks)
            print(f"🎵 Cançó triada per al vídeo: {os.path.basename(music_file)}")

    if music_file:
        try:
            audio = AudioFileClip(music_file)
            subclip_fn = getattr(audio, "subclip", getattr(audio, "subclipped", None))

            if audio.duration < total_duration:
                n_loops = int(np.ceil(total_duration / audio.duration))
                audio = concatenate_audioclips([audio] * n_loops)
                if subclip_fn:
                    audio = subclip_fn(0, total_duration)
            else:
                if subclip_fn:
                    audio = subclip_fn(0, total_duration)

            if hasattr(audio, "audio_fadein") and hasattr(audio, "audio_fadeout"):
                audio = audio.audio_fadein(1.0).audio_fadeout(2.0)

            if hasattr(final_video, "set_audio"):
                final_video = final_video.set_audio(audio)
            elif hasattr(final_video, "with_audio"):
                final_video = final_video.with_audio(audio)
        except Exception as e:
            print(f"⚠️ Warning: No s'ha pogut afegir l'àudio: {e}")

    output_filename = os.path.join(PUBLIC_VIDEOS_DIR, f"{video_id}.mp4")
    print(f"🎥 Renderitzant vídeo MP4 final amb transicions i barra fluida ({total_duration}s)...")
    final_video.write_videofile(
        output_filename,
        fps=fps,
        codec='libx264',
        audio_codec='aac',
        preset='fast',
        threads=4
    )

    print("✅ Vídeo MP4 renderitzat amb èxit!")

    hashtag_pool = ['#formfriends', '#couples', '#relationshipquestions', '#deepconversations', '#coupleschallenge', '#questionsforcouples']
    tags_string = " ".join(random.sample(hashtag_pool, 4))
    caption = f"{video_data.get('Slide_1_Title', '')}\n\nSave this for your next late night talk with your person. ✨\n\n—\n{tags_string}"

    if TEST_MODE:
        # ========================================================
        # MODE PROVA: ENVIAMENT DIRECTE A TELEGRAM
        # ========================================================
        title_text = html.escape(video_data.get('Slide_1_Title', ''))
        telegram_msg = (
            f"🎬 <b>[MODE PROVA] {video_id} generat!</b>\n\n"
            f"📖 <b>Portada:</b> {title_text}\n"
            f"🏷️ <b>Hashtags:</b> {tags_string}\n\n"
            f"<i>Nota: El vídeo no s'ha enviat a Buffer (Mode Prova actiu).</i>"
        )
        print("📲 Mode Prova: Enviant vídeo a Telegram per a la teva revisió...")
        send_telegram_video_notification(telegram_msg, output_filename)

        rows[current_row_idx][status_col_idx] = 'Done'
        with open(CSV_PATH, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)
        print(f"📝 CSV actualitzat! Fila {current_row_idx + 1} ({video_id}) marcada com a 'Done'.")

    else:
        # ========================================================
        # MODE PRODUCCIÓ: PUBLICACIÓ A XARXES SOCIALS VIA BUFFER
        # ========================================================
        if not BUFFER_ACCESS_TOKEN:
            print("⚠️ Warning: BUFFER_ACCESS_TOKEN no configurat als Secrets.")
            return

        public_video_url = get_public_video_url(output_filename)

        print("📤 Enviant el vídeo a Buffer (Instagram Reels, TikTok & YouTube Shorts)...")
        success = post_video_to_buffer(BUFFER_ACCESS_TOKEN, public_video_url, caption)

        if success:
            title_text = html.escape(video_data.get('Slide_1_Title', ''))
            telegram_msg = (
                f"🎬 <b>{video_id} publicat amb èxit!</b>\n\n"
                f"📱 <b>Destí:</b> Instagram Reels, TikTok &amp; YouTube Shorts\n"
                f"📖 <b>Títol:</b> {title_text}\n"
                f"🏷️ <b>Hashtags:</b> {tags_string}"
            )
            send_telegram_video_notification(telegram_msg, output_filename)

            rows[current_row_idx][status_col_idx] = 'Done'
            with open(CSV_PATH, mode='w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                writer.writerows(rows)
            print(f"📝 CSV actualitzat! Fila {current_row_idx + 1} ({video_id}) marcada com a 'Done'.")
        else:
            send_telegram_video_notification(f"❌ <b>Error en publicar {video_id} a Buffer.</b>", output_filename)


if __name__ == "__main__":
    main()
