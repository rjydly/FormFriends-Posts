# 📱 Telegram Poster Bot (GitHub Actions)

This folder contains the complete, ready-to-use codebase for generating social media slides and posting them automatically to your Telegram channel, group, or chat using **GitHub Actions**.

Instead of requiring Google Cloud credentials or interactive logins, this version uses a local database (`posts.csv`) directly in your GitHub repository. The workflow will automatically update this file to mark each processed post as `Done` and commit the change back to the repository.

---

## 📁 File Structure

* **`posts.csv`**: Contains all your 100 posts extracted from your Google Sheet. Column `Status` keeps track of which ones are finished.
* **`logo.png`**: The logo image that will be centered and pasted near the bottom of each slide.
* **`generate_and_send.py`**: The core Python script that downloads fonts, renders the 6 card-style slides, generates the caption with random hashtags, sends them as a Telegram photo group (album), and marks the post as `Done`.
* **`requirements.txt`**: Specifies the Python libraries (`pillow` and `requests`) needed to run the script.
* **`post_workflow.yml`**: The configuration file for the GitHub Actions workflow.

---

## 🛠️ Setup Instructions

Follow these steps to configure your GitHub repository and activate the bot:

### Step 1: Create a Telegram Bot
1. Open Telegram and search for [@BotFather](https://t.me/BotFather).
2. Start a chat and send the command `/newbot`.
3. Follow the instructions to give your bot a name and a username.
4. Copy the generated **HTTP API Token** (e.g. `123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ`). Keep this token safe!

### Step 2: Get your Telegram Chat ID
You need the ID of the channel, group, or chat where you want the posts to be sent:
* **For a Channel or Group**:
  1. Add your newly created bot to the channel/group as an **Administrator** with permission to post messages.
  2. Send a temporary message in the channel/group.
  3. Forward that message to [@userinfobot](https://t.me/userinfobot) or [@MissRose_bot](https://t.me/MissRose_bot) to get the Chat ID (it will start with `-100` for channels).
* **For a Private Chat**:
  1. Start a conversation with your bot by searching for its username and clicking **Start**.
  2. Start a chat with [@userinfobot](https://t.me/userinfobot) and click start to get your personal User ID.

### Step 3: Add Secrets to GitHub
To prevent exposing your bot credentials in public code, you must save them as GitHub Secrets:
1. Go to your repository on GitHub.
2. Navigate to **Settings** (top tab) -> **Secrets and variables** (left sidebar) -> **Actions**.
3. Click the **New repository secret** button.
4. Add the following two secrets:
   * **Name**: `TELEGRAM_BOT_TOKEN`
     * **Value**: *Your Telegram Bot Token from Step 1*
   * **Name**: `TELEGRAM_CHAT_ID`
     * **Value**: *Your Telegram Chat ID from Step 2 (e.g. `-100123456789`)*

### Step 4: Position the Workflow File
For GitHub to recognize the workflow, the YAML file must be placed in a specific folder structure at the root of your repository:
1. Create a folder named `.github` at the root of your repository (if it doesn't already exist).
2. Inside it, create another folder named `workflows`.
3. Move (or copy) `post_workflow.yml` from this folder into `.github/workflows/`.
   * *Path in repository should be:* `.github/workflows/post_workflow.yml`

*Note: You can leave the rest of the files (`generate_and_send.py`, `posts.csv`, `logo.png`, `requirements.txt`) inside the `telegram_poster` directory.*

### Step 5: Enable Write Permissions in Repository Settings
To allow the workflow to commit the updated `posts.csv` back to your repo:
1. In your GitHub repository, go to **Settings** -> **Actions** -> **General**.
2. Scroll down to **Workflow permissions**.
3. Choose **Read and write permissions** and click **Save**.

---

## 🚀 How to Run the Bot

Once everything is set up:
1. Go to the **Actions** tab at the top of your GitHub repository page.
2. Under **Workflows** on the left, click **Generate and Send Post to Telegram**.
3. Click the **Run workflow** dropdown button on the right.
4. Select your branch (e.g. `main`) and click the green **Run workflow** button.
5. In a few seconds, the workflow will start, generate the slides, post them to Telegram, update `posts.csv`, and commit it back to your repo automatically!
