import os
import csv
import random
import requests
import ftplib
import subprocess
import html
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Importació de MoviePy utilitzant l'estructura exacta del teu projecte funcional
from moviepy.editor import ImageSequenceClip, AudioFileClip, CompositeAudioClip, concatenate_audioclips

# ========================================================
# CONFIGURACIÓ I RUTES
# ========================================================
TEST_MODE = False  # Canvia a False quan vulguis publicar a xarxes socials (Buffer)

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


def hex_to_rgb(hex_str):
    hex_str = hex_str.lstrip('#')
    return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))


def interpolate_color(color1_hex, color2_hex, factor):
    """Barreja/fusiona dos colors en format HEX segons un factor entre 0.0 i 1.0"""
    r1, g1, b1 = hex_to_rgb(color1_hex)
    r2, g2, b2 = hex_to_rgb(color2_hex)
    
    r = int(r1 + (r2 - r1) * factor)
    g = int(g1 + (g2 - g1) * factor)
    b = int(b1 + (b2 - b1) * factor)
    
    return (r, g, b)


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


def post_video_to_buffer(token, video_url, caption, video_title="Video Title"):
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

        # Metadades per a Instagram Reels
        if "instagram" in service_name:
            channel_input["metadata"] = {
                "instagram": {
                    "type": "reel",
                    "shouldShareToFeed": True
                }
            }

        # NOU: Metadades per a YouTube (Shorts) per evitar l'error de títol buit
        elif "youtube" in service_name:
            clean_title = video_title
            if len(clean_title) > 95:
                clean_title = clean_title[:92] + "..."
            
            channel_input["metadata"] = {
                "youtube": {
                    "title": clean_title,
                    "privacy": "public"
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


def validate_audio_file(file_path):
    if not os.path.exists(file_path):
        return False, "Fitxer no trobat"
    
    file_size = os.path.getsize(file_path)
    if file_size < 1000:
        with open(file_path, 'r', errors='ignore') as f:
            content = f.read(200)
            if "git-lfs" in content or "version https://" in content:
                return False, "És un punter de Git LFS (text) en comptes d'àudio real. Assegura't de tenir lfs: true al workflow."
        return False, f"Fitxer massa petit ({file_size} bytes)."

    return True, "OK"


def clean_and_normalize_audio(input_path, output_path):
    """Saneja i re-codifica directament l'àudio amb FFmpeg de forma estàndard i neta"""
    try:
        print(f"🧹 FFmpeg està sanejant i convertint l'àudio: {os.path.basename(input_path)}")
        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-vn",                  # Desactivar vídeo
            "-ar", "44100",         # Freqüència estàndard
            "-ac", "2",             # Stereo
            "-b:a", "192k",         # Bitrate ideal
            output_path
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode == 0:
            print("✨ Sanejament de la pista de fons completat correctament!")
            return True
        else:
            print(f"❌ FFmpeg ha fallat en codificar: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Error executant comanda de sanejament de FFmpeg: {e}")
        return False


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

    width, height = 1080, 1920
    fps = 24  # Els vídeos d'imatge i fons es renderitzen de forma fluida i optimitzada a 24fps

    dark_colors = [
        '#101520', '#161F2B', '#121824', '#1A2A30', '#181A1B',
        '#2C1420', '#1B2A26', '#281E12', '#1E1E28', '#251818',
        '#142028', '#1F1728', '#221915', '#13221C'
    ]

    slides = [
        {"text": video_data.get('Slide_1_Title', ''), "duration": 5.0, "is_title": True},
        {"text": video_data.get('Slide_2_Question', ''), "duration": 9.0, "is_title": False},
        {"text": video_data.get('Slide_3_Question', ''), "duration": 9.0, "is_title": False},
        {"text": video_data.get('Slide_4_Question', ''), "duration": 9.0, "is_title": False},
        {"text": video_data.get('Slide_5_Question', ''), "duration": 9.0, "is_title": False},
        {"text": video_data.get('Slide_6_Question', ''), "duration": 9.0, "is_title": False},
    ]

    slide_colors = [random.choice(dark_colors) for _ in slides]

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

    # ========================================================
    # GENERACIÓ DE LA LLISTA DE FOTOGRAMES (Pillow)
    # ========================================================
    all_frames = []
    card_margin = 80
    top_margin = 220
    bottom_margin = 200
    trans_duration = 0.5

    print("🎨 Renderitzant frames a memòria (disseny estètic + merge + fade)...")

    for i, slide in enumerate(slides):
        current_bg_hex = slide_colors[i]
        next_bg_hex = slide_colors[i+1] if i < len(slides) - 1 else slide_colors[i]
        
        duration = slide["duration"]
        is_title = slide["is_title"]
        num_frames_slide = int(duration * fps)

        for f_idx in range(num_frames_slide):
            t = f_idx / fps
            t_trans_start = duration - trans_duration

            if t < t_trans_start:
                bg_rgb = hex_to_rgb(current_bg_hex)
                progress = min(1.0, max(0.0, t / t_trans_start))
                text_alpha = min(255, int(255 * (t / trans_duration)))  # Fade-In del text
                bar_fill_alpha = 255
            else:
                k = (t - t_trans_start) / trans_duration
                k = min(1.0, max(0.0, k))

                # Canvi de fons progressiu (Merge)
                bg_rgb = interpolate_color(current_bg_hex, next_bg_hex, k)
                
                # Fade-Out de les lletres
                text_alpha = int(255 * (1.0 - k))
                
                # Barra al 100% de progrés, però iniciant Fade-Out
                progress = 1.0
                bar_fill_alpha = int(255 * (1.0 - k))

            # Render de la imatge de fons
            bg = Image.new('RGBA', (width, height), color=bg_rgb)

            # Targeta central translúcida
            card_layer = Image.new('RGBA', (width, height), (0, 0, 0, 0))
            draw_card = ImageDraw.Draw(card_layer)
            draw_card.rounded_rectangle(
                [(card_margin, top_margin), (width - card_margin, height - bottom_margin)],
                radius=40, fill=(255, 255, 255, 20), outline=(255, 255, 255, 80), width=2
            )
            canvas = Image.alpha_composite(bg, card_layer)

            # Capçalera "FormFriends" i Logo (Estàtics)
            header_layer = Image.new('RGBA', (width, height), (0, 0, 0, 0))
            draw_header = ImageDraw.Draw(header_layer)
            bbox_h = draw_header.textbbox((0, 0), "FormFriends", font=font_title)
            h_w = bbox_h[2] - bbox_h[0]
            draw_header.text(((width - h_w) / 2, 260), "FormFriends", fill='#FFFFFF', font=font_title)

            if logo_img:
                logo_x = int((width - logo_img.size[0]) / 2)
                logo_y = height - 360
                header_layer.paste(logo_img, (logo_x, logo_y), logo_img)

            canvas = Image.alpha_composite(canvas, header_layer)

            # Capa de text (amb fade)
            text_layer = Image.new('RGBA', (width, height), (0, 0, 0, 0))
            draw_text = ImageDraw.Draw(text_layer)
            current_font = font_title if is_title else font_text
            max_text_w = width - (card_margin * 4)
            wrapped_lines = wrap_text(slide["text"], draw_text, current_font, max_text_w)

            line_heights = [draw_text.textbbox((0, 0), l, font=current_font)[3] - draw_text.textbbox((0, 0), l, font=current_font)[1] for l in wrapped_lines]
            total_text_h = sum(line_heights) + (24 * (len(wrapped_lines) - 1))
            current_y = (height - total_text_h) / 2

            text_color = (255, 255, 255, text_alpha)
            for line in wrapped_lines:
                bbox = draw_text.textbbox((0, 0), line, font=current_font)
                text_w = bbox[2] - bbox[0]
                current_x = (width - text_w) / 2
                draw_text.text((current_x, current_y), line, fill=text_color, font=current_font)
                current_y += (bbox[3] - bbox[1]) + 24

            canvas = Image.alpha_composite(canvas, text_layer)

            # Barra de progrés superior
            bar_layer = Image.new('RGBA', (width, height), (0, 0, 0, 0))
            draw_bar = ImageDraw.Draw(bar_layer)
            bar_margin_x = 100
            bar_y = 120
            bar_height = 12
            max_bar_w = width - (bar_margin_x * 2)

            # Track translúcid de fons (sempre visible)
            draw_bar.rounded_rectangle(
                [(bar_margin_x, bar_y), (bar_margin_x + max_bar_w, bar_y + bar_height)],
                radius=6,
                fill=(255, 255, 255, 70)
            )

            # Barra blanca que s'omple i després fa fade out
            current_w = int(max_bar_w * progress)
            if current_w > 6 and bar_fill_alpha > 0:
                draw_bar.rounded_rectangle(
                    [(bar_margin_x, bar_y), (bar_margin_x + current_w, bar_y + bar_height)],
                    radius=6,
                    fill=(255, 255, 255, bar_fill_alpha)
                )

            final_frame = Image.alpha_composite(canvas, bar_layer)
            all_frames.append(np.array(final_frame.convert('RGB')))

    # Creació de la seqüència (ImageSequenceClip)
    clip = ImageSequenceClip(all_frames, fps=fps)
    total_duration = clip.duration

    # ========================================================
    # SELECCIÓ I SANEJAMENT D'ÀUDIO
    # ========================================================
    music_file = None
    music_filename = "Cap cançó trobada ⚠️"
    clean_audio_path = os.path.join(PUBLIC_VIDEOS_DIR, "clean_music.mp3")

    if os.path.exists(MUSIC_DIR):
        possible_tracks = [os.path.join(MUSIC_DIR, f) for f in os.listdir(MUSIC_DIR) if f.lower().endswith(('.mp3', '.m4a', '.wav'))]
        print(f"📂 Arxius detectats a la carpeta music/: {[os.path.basename(p) for p in possible_tracks]}")

        valid_tracks = []
        for track in possible_tracks:
            is_valid, reason = validate_audio_file(track)
            if is_valid:
                valid_tracks.append(track)
            else:
                print(f"⚠️ Atenció amb {os.path.basename(track)}: {reason}")

        if valid_tracks:
            chosen_track = random.choice(valid_tracks)
            if clean_and_normalize_audio(chosen_track, clean_audio_path):
                music_file = clean_audio_path
                music_filename = os.path.basename(chosen_track)
                print(f"🎵 Àudio sanejat perfectament a clean_music.mp3")
            else:
                music_file = chosen_track
                music_filename = os.path.basename(chosen_track) + " (Original sense sanejar)"
        else:
            music_filename = "Cap cançó és un fitxer d'àudio vàlid (comprova Git LFS)"

    # Associar el so exactament com en el teu projecte funcional (CompositeAudioClip)
    if music_file:
        try:
            audio = AudioFileClip(music_file)
            audio_dur = audio.duration
            audio = audio.subclip(0, min(total_duration, audio_dur))

            # Fade-in i fade-out suaus
            if hasattr(audio, "audio_fadein") and hasattr(audio, "audio_fadeout"):
                audio = audio.audio_fadein(1.0).audio_fadeout(2.0)

            # COMPOSITEAUDIOClIP: El mètode que activa els canals de so per FFmpeg
            clip = clip.set_audio(CompositeAudioClip([audio.set_start(0)]).set_duration(total_duration))
            print("🔊 Àudio muntat amb èxit gràcies a CompositeAudioClip!")
        except Exception as e:
            print(f"❌ Error acoblant l'àudio amb CompositeAudioClip: {e}")
            music_filename += f" (Error: {e})"

    output_filename = os.path.join(PUBLIC_VIDEOS_DIR, f"{video_id}.mp4")
    print(f"🎥 Renderitzant vídeo MP4 final amb ImageSequenceClip ({total_duration}s)...")
    
    # Exportació idèntica al teu projecte funcional
    clip.write_videofile(
        output_filename,
        codec='libx264',
        audio_codec='aac',
        fps=fps,
        preset='medium',
        logger=None
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
            f"🎬 <b>[MODE PROVA] {video_id} generat amb so!</b>\n\n"
            f"📖 <b>Portada:</b> {title_text}\n"
            f"🎵 <b>Música utilitzada:</b> {music_filename}\n"
            f"🏷️ <b>Hashtags:</b> {tags_string}\n\n"
            f"<i>Nota: Recorda provar el vídeo un cop rebut. El so ara ha de funcionar completament!</i>"
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
        # NOU: Passem el títol extret del CSV com a quart argument per a YouTube
        success = post_video_to_buffer(
            BUFFER_ACCESS_TOKEN, 
            public_video_url, 
            caption, 
            video_data.get('Slide_1_Title', 'Video Title')
        )

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
