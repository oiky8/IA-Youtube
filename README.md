# IA-Youtube

An AI-powered YouTube Live Moderator that automatically reads live chat messages, processes them with AI, and replies in real time.

---

# Features

- 📺 Read YouTube Live Chat in real time
- 🤖 AI-powered automatic replies
- 💬 Support for Gemini AI
- 🔗 Support for Custom OpenAI-Compatible APIs
- 🛡️ Anti-spam and blacklist system
- ⚡ Multi-threaded message queue
- 📡 Automatic livestream detection
- 🎥 OBS integration
- 🔄 Automatic recovery from unexpected errors

---

# Requirements

- Python 3.10 or newer
- Google Cloud Project
- YouTube Data API v3
- OAuth Client Credentials
- OBS Studio (Optional)

---

# Installation

## 1. Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/IA-Youtube.git
cd IA-Youtube
```

---

## 2. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## 3. Configure Environment Variables

Create a `.env` file in the project root.

Example:

```env
YOUTUBE_API_KEY=
CHANNEL_ID=

CUSTOM_API_URL=
CUSTOM_API_KEY=
MODEL_NAME=

GEMINI_API_KEY=
```

---

# Google OAuth Setup

1. Open **Google Cloud Console**
2. Create a Desktop OAuth Client.
3. Download the credentials file.
4. Rename it to:

```
client_secret.json
```

5. Place it in the project root.

When you run the bot for the first time, it will automatically generate:

```
token.json
```

---

# Enable YouTube Data API

Inside Google Cloud Console:

- Enable **YouTube Data API v3**
- Create an API Key

Paste it into:

```
YOUTUBE_API_KEY
```

---

# Get Your Channel ID

Copy your YouTube Channel ID and place it inside:

```
CHANNEL_ID
```

---

# Running the Bot

Start the bot with:

```bash
python AI_MOD_ALL_IN_ONE.py
```

---

# OBS Integration (Optional)

# OBS Script Setup

If you want the bot to automatically start and stop together with your livestream, follow these steps:

## 1. Open OBS Studio

Launch **OBS Studio**.

---

## 2. Open the Scripts Window

Go to:

```
Tools → Scripts
```

---

## 3. Add the Script

Click the **+** button and select:

```
obs_control.py
```

from the project folder.

---

## 4. Configure the Script

If the script requires a path to your project, select the folder containing:

```
AI_MOD_ALL_IN_ONE.py
```

---

## 5. Start Streaming

Click **Start Streaming** in OBS.

The script will automatically:

- Detect when streaming starts
- Launch the AI Moderator
- Monitor YouTube Live Chat
- Automatically stop the bot when the stream ends

---

# Troubleshooting

### Script does not appear

Make sure you are using the **Python version of OBS Studio** that supports Python scripts.

---

### Nothing happens after starting the stream

Check that:

- `AI_MOD_ALL_IN_ONE.py` exists.
- Your `.env` file is correctly configured.
- `client_secret.json` and `token.json` are present.
- Your YouTube livestream is public or unlisted and currently live.

---

### OBS reports Python errors

Verify that all required Python packages are installed:

```bash
pip install -r requirements.txt
```

If the issue persists, check the OBS log for detailed error messages.
# Project Structure

```
IA-Youtube/
│
├── AI_MOD_ALL_IN_ONE.py
├── obs_control.py
├── check_quota_status.py
├── blacklist.json
├── requirements.txt
├── client_secret.json
├── token.json
└── README.md
```

---

# Workflow

```
YouTube Live Chat
        │
        ▼
Read Messages
        │
        ▼
Spam Detection
        │
        ▼
Send to AI
        │
        ▼
Generate Response
        │
        ▼
Reply to Live Chat
```

---

# Supported AI Providers

- Google Gemini
- Custom OpenAI-Compatible API

---

# Blacklist

Blocked users are stored in:

```
blacklist.json
```

You can manually edit this file to add or remove users.

---

# License

This project is licensed under the **MIT License**.

---

# Disclaimer

This project is intended for educational and personal use only. Users are responsible for complying with YouTube's Terms of Service and Google's API policies.
