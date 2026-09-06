# SIT ReadyTalent Job Polling Bot

An automated job monitoring bot that logs into Singapore Institute of Technology's (SIT) ReadyTalent portal, checks for newly posted student jobs, persists job history locally, and sends real-time alert notifications directly to your Telegram chat.

---

## Features

- **Automated Authentication**: Logs in through SIT's ADFS Single Sign-On using Playwright.
- **Hourly Polling**: Queries the portal at configurable intervals (defaults to 1 hour).
- **Smart Diffing & Persistence**: Stores known job postings in `data/jobs.json` to avoid duplicate alerts and detect new listings.
- **Instant Telegram Alerts**: Delivers formatted job cards with title, company, vacancy count, and portal links directly to your Telegram chat.
- **First-Run Guard**: Establishes a baseline on the initial scrape so you aren't spammed with dozens of existing jobs.

---

## 1. Telegram Bot Setup (via BotFather / "Bot Daddy")

Before running the bot, you need a Telegram Bot Token and your personal Chat ID.

### Step 1: Create the Bot with @BotFather
1. Open Telegram and search for **[@BotFather](https://t.me/BotFather)** (the official verified bot with the blue checkmark).
2. Send `/start`, then send `/newbot`.
3. Enter a display name for your bot (e.g. `SIT Job Alert Bot`).
4. Enter a username for your bot that must end in `bot` (e.g. `sit_job_notifier_bot`).
5. BotFather will provide an **HTTP API Token** formatted like:
   ```text
   1234567890:ABCdefGhIJKlmNoPQRsTUVwxyZ
   ```
   Save this token as your `TELEGRAM_BOT_TOKEN`.

### Step 2: Start the Bot Chat
> [!IMPORTANT]
> Telegram bots cannot initiate conversations with users. You **must** message your bot first.
1. Open the chat link to your new bot provided by BotFather (or search for its `@username`).
2. Click **Start** or send `/start`.

### Step 3: Find Your Personal Chat ID
1. Search for **[@userinfobot](https://t.me/userinfobot)** on Telegram.
2. Send any message or click `/start`.
3. It will reply with your details:
   ```text
   Id: 987654321
   First: YourName
   ```
4. Copy the numeric `Id` (e.g. `987654321`). This is your `TELEGRAM_CHAT_ID`.
   *(Note: Do not use the bot's own ID from the bot token, or Telegram will return a `403 Forbidden: the bot can't send messages to the bot` error).*

---

## 2. Environment Configuration (`.env`)

Create a `.env` file in the root of the project by copying the example:

```bash
cp .env.example .env
```

Open `.env` and fill in your details:

```dotenv
# SIT ReadyTalent Login Credentials
user_name=your_sit_student_id@singaporetech.edu.sg
password=your_sit_password

# Telegram Configuration
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGhIJKlmNoPQRsTUVwxyZ
TELEGRAM_CHAT_ID=987654321

# Polling Interval in seconds (optional, default: 3600 = 1 hour)
POLL_INTERVAL_SECONDS=3600
```

---

## 3. Linux Environment Setup (with `venv`)

Follow these steps to set up and run the bot on a Linux server (Ubuntu, Debian, Raspberry Pi OS, etc.).

### Prerequisites
Update package lists and ensure Python 3, `pip`, and `python3-venv` are installed:

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git
```

### Setup Virtual Environment

1. **Clone or copy the project to your Linux machine**:
   ```bash
   git clone <your-repo-url> sit-bot
   cd sit-bot
   ```

2. **Create a virtual environment (`venv`)**:
   ```bash
   python3 -m venv venv
   ```

3. **Activate the virtual environment**:
   ```bash
   source venv/bin/activate
   ```
   *(Your terminal prompt will change to show `(venv)`).*

4. **Install Python dependencies**:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

5. **Install Playwright Browser and System Dependencies**:
   > [!IMPORTANT]
   > Headless Chromium requires system-level libraries on Linux (fonts, NSS, graphics libraries). Run both of the following commands:
   ```bash
   playwright install chromium
   sudo playwright install-deps chromium
   ```

---

## 4. Running the Bot

Ensure your virtual environment is active (`source venv/bin/activate`).

### Run in Foreground (Testing)
```bash
python src/bot.py
```

### Run 24/7 in Background

#### Option A: Using `tmux` (Simplest & Detachable)
```bash
sudo apt install -y tmux
tmux new -s sit-bot
source venv/bin/activate
python src/bot.py
```
- Press `Ctrl + B`, then press `D` to detach and leave it running in the background.
- To re-attach later and check logs: `tmux attach -t sit-bot`.

#### Option B: Using `systemd` (Recommended for Auto-Restart on Boot)
Create a background system service that starts on boot and restarts if it crashes:

1. Create a service file:
   ```bash
   sudo nano /etc/systemd/system/sit-bot.service
   ```

2. Paste the following configuration (replace `/home/ubuntu/sit-bot` and `ubuntu` with your actual username and path):
   ```ini
   [Unit]
   Description=SIT ReadyTalent Job Polling Bot
   After=network.target

   [Service]
   Type=simple
   User=ubuntu
   WorkingDirectory=/home/ubuntu/sit-bot
   ExecStart=/home/ubuntu/sit-bot/venv/bin/python /home/ubuntu/sit-bot/src/bot.py
   Restart=always
   RestartSec=30
   Environment=PYTHONUNBUFFERED=1

   [Install]
   WantedBy=multi-user.target
   ```

3. Enable and start the service:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable sit-bot
   sudo systemctl start sit-bot
   ```

4. View live logs:
   ```bash
   journalctl -u sit-bot -f
   ```

---

## 5. File Structure

```text
sit-bot/
├── data/
│   └── jobs.json             # Cached job data and first_seen timestamps (auto-created)
├── src/
│   ├── bot.py                # Main scraping, diffing, and Telegram polling engine
│   └── log_config.py         # Logging configuration
├── .env                      # Secret credentials (git-ignored)
├── .env.example              # Sample environment template
├── .gitignore
├── requirements.txt          # Python dependencies
└── README.md
```

---

## 6. Troubleshooting

- **`Forbidden: the bot can't send messages to the bot` (HTTP 403)**:
  `TELEGRAM_CHAT_ID` in `.env` was set to the bot's own ID. Use `@userinfobot` to get your personal user chat ID.
- **`Forbidden: bot was blocked by the user`**:
  You have not initiated a conversation with your bot yet. Open the chat with your bot on Telegram and press `/start`.
- **`Host system is missing dependencies to run browsers`**:
  Run `sudo playwright install-deps chromium` to install the required Linux shared libraries.
