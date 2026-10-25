<div align="center">

# 🎬 FlixVault Secure Delivery Bot
### *Automated Digital Asset & Movie Distribution System*

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![Pyrogram](https://img.shields.io/badge/Pyrogram-Asyncio-orange.svg)](https://docs.pyrogram.org/)
[![MongoDB](https://img.shields.io/badge/MongoDB-Atlas-green.svg)](https://www.mongodb.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

---

## 🚀 Overview

**FlixVault Bot** is a high-performance, secure Telegram FileStore and digital asset delivery bot built with **Python (Pyrogram)** and **MongoDB**. It is natively integrated with the FlixVault web platform, providing an automated, zero-expiry, single-use token delivery system that sends files directly to users' personal Telegram DMs instantly after purchase verification.

---

## 🛠️ Core Architecture & Workflow

1. **Admin File Ingestion:** Admin sends any movie or document file directly to the bot. The bot automatically saves it to MongoDB and generates a unique, human-readable code (e.g., `FLX-MOV-A7X9`).
2. **Website Integration:** The generated `botCode` is mapped to movies on the FlixVault website's admin panel.
3. **Secure Purchase & Token Generation:** Upon successful payment verification on the web app, a unique secure token (`tok_...`) is generated and linked with the respective `botCode` in the shared database.
4. **Direct DM Delivery:** When the user clicks the secure Telegram deep link (`t.me/YourBot?start=tok_...`), the bot validates the token (zero time-expiry, single-use rule), marks it as `used`, and delivers the file directly to the user's personal chat.

---

## ✨ Key Features

* **🔑 Auto Code Generator:** Instant unique code generation when admins upload media files.
* **📦 Secure Direct DM Delivery:** Safe, non-expiring single-use token system preventing link leakage.
* **📢 Advanced Post Builder:** Create rich interactive channel posts with custom URL buttons and live reaction counters (`/create_post`, `/send`).
* **🛡️ Channel Diagnostics:** Built-in admin tools to inspect, add, remove, and verify bot admin status across distribution channels (`/add_channel`, `/diag_channels`).
* **⚡ Lean & Clean Codebase:** Stripped of unnecessary forced-subscriptions, ads, or shortlink bloat for maximum speed and reliability.

---

## ⚙️ Environment Variables (`config.py` / `.env`)

Configure the following environment variables before running the bot:

| Variable | Description |
| :--- | :--- |
| `TG_BOT_TOKEN` | Your Telegram Bot Token obtained from [@BotFather](https://t.me/BotFather) |
| `APP_ID` | Your Telegram API ID from [my.telegram.org](https://my.telegram.org) |
| `API_HASH` | Your Telegram API Hash from [my.telegram.org](https://my.telegram.org) |
| `OWNER_ID` | Telegram User ID of the primary bot owner / administrator |
| `DATABASE_URL` | MongoDB connection string (Shared with your web app) |
| `DATABASE_NAME` | MongoDB database name |
| `ADMINS` | Optional: Space-separated list of additional admin user IDs |
| `START_MESSAGE` | Custom HTML welcome message for the bot |

---

## 🤖 Bot Commands

### User & General Commands
* `/start` — Start the bot or process secure asset delivery tokens.
* `/cmds` — Display available command list.

### Admin & Management Commands
* `/create_post` — Launch the interactive post draft builder.
* `/send` — Publish drafts to authorized channels.
* `/add_channel` — Register a new distribution channel.
* `/remove_channel` — Unlink a distribution channel.
* `/list_channels` — View all registered channels.
* `/diag_channels` — Check bot administrative privileges in all channels.

---

## 📦 Deployment Methods

### Deploy on VPS / Linux Server

```bash
# Clone the repository
git clone [https://github.com/YourUsername/FlixVault-Bot.git](https://github.com/YourUsername/FlixVault-Bot.git)
cd FlixVault-Bot

# Install dependencies
pip3 install -U -r requirements.txt

# Configure your credentials in config.py
# Run the bot
python3 main.py
