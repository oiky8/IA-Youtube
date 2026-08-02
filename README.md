# IA-Youtube

An AI-powered YouTube Live Moderator that automatically reads YouTube Live Chat messages and generates AI responses in real time.

The bot supports **Google Gemini** and **OpenAI-compatible APIs**, making it easy to integrate with your preferred AI provider.

---

## Features

- 📺 Read YouTube Live Chat automatically
- 🤖 AI-generated replies
- 💬 Google Gemini support
- 🔗 Custom OpenAI-Compatible API support
- 🛡️ Basic spam filtering and blacklist
- 🎥 OBS Studio integration
- ⚡ Automatic livestream detection
- 🔄 Automatic authentication using Google OAuth

---

# Requirements

Before installing the project, make sure you have:

- Python **3.10+**
- OBS Studio (Optional)
- A Google Cloud Project
- YouTube Data API v3 enabled
- Google OAuth Desktop Client
- A Gemini API Key (Optional)
- A Custom AI API (Optional)

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

# Environment Variables

Create a file named

```
.env
```

Example:

```env
YOUTUBE_API_KEY=

CHANNEL_ID=

CUSTOM_API_URL=
CUSTOM_API_KEY=
MODEL_NAME=

GEMINI_API_KEY=
```

Leave optional fields empty if you don't need them.

---

# Google Cloud Setup

## Step 1

Open

https://console.cloud.google.com/

Create a new project.

---

## Step 2

Open

```
APIs & Services
```

↓

```
Library
```

Enable

```
YouTube Data API v3
```

---

## Step 3

Open

```
Credentials
```

↓

```
Create Credentials
```

↓

```
API Key
```

Copy the generated key.

Paste it into

```env
YOUTUBE_API_KEY=
```

---

# Google OAuth Setup

Inside

```
Credentials
```

Click

```
Create Credentials
```

↓

```
OAuth Client ID
```

Choose

```
Desktop App
```

Download the JSON file.

Rename it to

```
client_secret.json
```

Move it into the project folder.

---

# First Login

Run

```bash
python AI_MOD_ALL_IN_ONE.py
```

A browser window will open.

Log in with your Google account.

Click **Allow**.

After authorization, the project will automatically create

```
token.json
```

You only need to do this once.

---

# Get Your Channel ID

Open

```
YouTube Studio
```

↓

```
Settings
```

↓

```
Channel
```

↓

```
Advanced Settings
```

Copy your Channel ID.

Paste it into

```env
CHANNEL_ID=
```

---

# Gemini API Key (Optional)

Visit

https://aistudio.google.com/app/apikey

Create a new API Key.

Paste it into

```env
GEMINI_API_KEY=
```

---

# Custom AI API (Optional)

If you use an OpenAI-compatible server:

```env
CUSTOM_API_URL=
CUSTOM_API_KEY=
MODEL_NAME=
```

Otherwise, leave them empty.

---

# Running the Bot

Start the bot with

```bash
python AI_MOD_ALL_IN_ONE.py
```

If everything is configured correctly, the bot will:

- Detect your livestream
- Read YouTube Live Chat
- Send messages to the AI
- Reply automatically

---

# OBS Studio Integration

If you want the bot to start automatically with OBS:

Open

```
OBS Studio
```

↓

```
Tools
```

↓

```
Scripts
```

↓

Click

```
+
```

Select

```
obs_control.py
```

The script will automatically detect when streaming starts and launch the bot.

---

# Project Structure

```
IA-Youtube
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
Start Livestream
        │
        ▼
Detect Live Stream
        │
        ▼
Read Live Chat
        │
        ▼
Spam Filter
        │
        ▼
Send Message to AI
        │
        ▼
Receive AI Response
        │
        ▼
Reply to Live Chat
```

---

# Troubleshooting

## No livestream detected

- Make sure your livestream is currently live.
- Verify that the Channel ID is correct.

---

## OAuth Error

Delete

```
token.json
```

Run the project again.

---

## API Key Error

Make sure

```
YOUTUBE_API_KEY
```

is valid.

---

## Gemini Error

Verify

```
GEMINI_API_KEY
```

and check your API quota.

---

## Missing client_secret.json

Place

```
client_secret.json
```

in the project root.

---

# License

MIT License

---

# Credits

Developed by **MIta Kuzota (oiky8)**

Powered by

- Google Gemini
- YouTube Data API v3
- Google OAuth
- OBS Studio
