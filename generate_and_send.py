import os
import csv
import time
import random
import requests
from PIL import Image, ImageDraw, ImageFont

# ========================================================
# CONFIGURATION & PATHS
# ========================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, 'posts.csv')
LOGO_PATH = os.path.join(BASE_DIR, 'logo.png')
FONT_BOLD_PATH = os.path.join(BASE_DIR, 'Poppins-Bold.ttf')
FONT_REG_PATH = os.path.join(BASE_DIR, 'Poppins-Regular.ttf')

# Fonts URL
FONT_BOLD_URL = "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Bold.ttf"
FONT_REG_URL = "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Regular.ttf"

# Telegram configuration from Environment Variables
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

def main():
    # 1. Download Poppins Font if not present
    download_font(FONT_BOLD_URL, FONT_BOLD_PATH)
    download_font(FONT_REG_URL, FONT_REG_PATH)

    # 2. Read the CSV file
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

    # 3. Find the first row that is not "Done"
    current_row_idx = None
    post_data = None
    for idx, r in enumerate(rows):
        # Handle cases where row might be shorter than headers
        while len(r) < len(headers):
            r.append('')
        status_val = r[status_col_idx].strip().lower()
        if status_val != 'done':
            current_row_idx = idx
            # Convert row list to dict for easier access
            post_data = dict(zip(headers, r))
            break

    if current_row_idx is None:
        print("🎉 Brutal! All posts are marked as 'Done' in your CSV file.")
        return

    post_id = post_data.get('Post_ID', f"Post_{current_row_idx + 1}")
    print(f"🚀 Generating images and caption for {post_id}...")

    # 4. Slide configuration and styling
    width, height = 1080, 1080
    dark_backgrounds = [
        '#101520', '#161F2B', '#121824',
        '#1A2A30', '#181A1B',
        '#4A0E17', '#34050B'
    ]
    bg_color = random.choice(dark_backgrounds)

    slides = [
        {"type": "title", "text": post_data.get('Slide_1_Title', '')},
        {"type": "question", "text": post_data.get('Slide_2_Question', '')},
        {"type": "question", "text": post_data.get('Slide_3_Question', '')},
        {"type": "question", "text": post_data.get('Slide_4_Question', '')},
        {"type": "question", "text": post_data.get('Slide_5_Question', '')},
        {"type": "question", "text": post_data.get('Slide_6_Question', '')}
    ]

    # Load Poppins fonts
    try:
        font_title = ImageFont.truetype(FONT_BOLD_PATH, 54)
        font_text = ImageFont.truetype(FONT_REG_PATH, 44)
    except Exception as e:
        print(f"⚠️ Error loading Poppins fonts: {e}. Falling back to default font.")
        font_title = ImageFont.load_default()
        font_text = ImageFont.load_default()

    # Load Logo
    logo_img = None
    if os.path.exists(LOGO_PATH):
        try:
            logo_img = Image.open(LOGO_PATH).convert('RGBA')
            max_logo_height = 120
            w_percent = (max_logo_height / float(logo_img.size[1]))
            max_logo_width = int((float(logo_img.size[0]) * float(w_percent)))
            logo_img = logo_img.resize((max_logo_width, max_logo_height), Image.Resampling.LANCZOS)
            print("Loaded logo image.")
        except Exception as e:
            print(f"⚠️ Error processing logo.png: {e}. Generating post without logo.")
    else:
        print("⚠️ Warning: logo.png not found. Generating post without logo.")

    temp_files = []

    # 5. Create the 6 slides
    for i, slide in enumerate(slides):
        bg = Image.new('RGBA', (width, height), color=bg_color)
        card_layer = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        draw_card = ImageDraw.Draw(card_layer)

        card_margin = 80
        draw_card.rounded_rectangle(
            [(card_margin, card_margin), (width - card_margin, height - card_margin)],
            radius=40,
            fill=(255, 255, 255, 25),
            outline=(255, 255, 255, 90),
            width=2
        )

        img = Image.alpha_composite(bg, card_layer).convert('RGB')
        draw = ImageDraw.Draw(img)

        # Progress bar
        if i > 0:
            pb_x_start = card_margin + 60
            pb_x_end = width - card_margin - 60
            pb_y = card_margin + 60
            pb_width = pb_x_end - pb_x_start
            pb_height = 8

            # Full white progress bar background
            draw.rounded_rectangle(
                [(pb_x_start, pb_y), (pb_x_end, pb_y + pb_height)],
                radius=4,
                fill=(255, 255, 255, 255)
            )

            # Cover rectangle for progress percentage
            num_questions = 5
            progress_percent = i / float(num_questions)
            cover_x_start = int(pb_x_start + (pb_width * progress_percent))

            if cover_x_start < pb_x_end:
                draw.rounded_rectangle(
                    [(cover_x_start, pb_y - 1), (pb_x_end + 1, pb_y + pb_height + 1)],
                    radius=4,
                    fill=bg_color
                )

        # Text wrapping and rendering
        current_font = font_title if slide["type"] == "title" else font_text
        max_text_width = width - (card_margin * 4)
        wrapped_lines = wrap_text(slide["text"], draw, current_font, max_text_width)

        line_heights = []
        for line in wrapped_lines:
            bbox = draw.textbbox((0, 0), line, font=current_font)
            line_heights.append(bbox[3] - bbox[1])
        total_text_height = sum(line_heights) + (20 * (len(wrapped_lines) - 1))

        current_y = (height - total_text_height) / 2

        for idx_line, line in enumerate(wrapped_lines):
            bbox = draw.textbbox((0, 0), line, font=current_font)
            text_w = bbox[2] - bbox[0]
            current_x = (width - text_w) / 2
            draw.text((current_x, current_y), line, fill='#FFFFFF', font=current_font)
            current_y += (bbox[3] - bbox[1]) + 20

        # Paste logo
        if logo_img:
            logo_x = int((width - logo_img.size[0]) / 2)
            logo_y = height - 235
            img.paste(logo_img, (logo_x, logo_y), logo_img)

        file_name = os.path.join(BASE_DIR, f"{post_id}_slide_{i+1}.png")
        img.save(file_name, "PNG")
        temp_files.append(file_name)

    print("Generated 6 slide images.")

    # 6. Generate Instagram Caption
    hashtag_pool = ['#friendforms', '#socialexperiment', '#perspective', '#humanconnection', '#mindset', '#deepconversations', '#socialgame', '#connection']
    chosen_hashtags = random.sample(hashtag_pool, 4)
    chosen_hashtags.append('#questions')
    random.shuffle(chosen_hashtags)
    tags_string = " ".join(chosen_hashtags)

    captions = [
        f"Decks like this are meant to expose what we usually leave unsaid. No right or wrong answers here—just raw perspectives.\n\nSwipe through, process the prompts, and let us know your take.\n\n👇 Which slide hit closest to home? Leave your answer below.\n\n—\n{tags_string}",
        f"A simple card can spark the most unexpected conversations. Some questions are better answered together.\n\nPass the deck around or think it through on your own.\n\n📌 Tag that one friend who absolutely needs to answer Slide 6.\n\n—\n{tags_string}",
        f"A new set of prompts for your thoughts.\n\nRead. Pause. Answer honestly.\n\n👇 Drop your unfiltered thoughts to the final slide in the comments.\n\n—\n{tags_string}"
    ]
    selected_caption = random.choice(captions)

    # 7. Send to Telegram
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Warning: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID environment variables are not set.")
        print("Skipping Telegram send. Images are saved locally.")
        print(f"Caption generated:\n{selected_caption}")
    else:
        print("📥 Sending images to Telegram...")
        telegram_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMediaGroup"
        
        media = []
        files = {}
        opened_files = []
        
        for idx, file_path in enumerate(temp_files):
            file_key = f"photo_{idx}"
            f_handle = open(file_path, 'rb')
            opened_files.append(f_handle)
            files[file_key] = f_handle
            
            media_item = {
                "type": "photo",
                "media": f"attach://{file_key}"
            }
            # Attach the caption to the first image of the group
            if idx == 0:
                media_item["caption"] = selected_caption
            media.append(media_item)

        import json
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "media": json.dumps(media)
        }

        try:
            response = requests.post(telegram_url, data=payload, files=files, timeout=30)
            # Close all opened file handles
            for f_handle in opened_files:
                f_handle.close()
                
            if response.status_code == 200:
                print("✅ Successfully sent post to Telegram!")
            else:
                print(f"❌ Failed to send to Telegram: Code {response.status_code}, Response: {response.text}")
                # Don't update CSV status to Done if sending failed
                return
        except Exception as e:
            for f_handle in opened_files:
                f_handle.close()
            print(f"❌ Exception occurred while sending to Telegram: {e}")
            return

    # Clean up local image files
    for file_path in temp_files:
        try:
            os.remove(file_path)
        except OSError:
            pass

    # 8. Mark post as Done in CSV
    rows[current_row_idx][status_col_idx] = 'Done'
    with open(CSV_PATH, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)
    print(f"📝 CSV updated! Marked row {current_row_idx + 1} ({post_id}) as 'Done'.")

if __name__ == "__main__":
    main()
