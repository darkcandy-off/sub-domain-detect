# 🚨 Subdomain Monitoring Telegram Bot

### Real-Time Subdomain Discovery Using crt.sh + Telegram Alerts

This project is a fully automated **Telegram bot** that monitors websites for **newly discovered subdomains** using the public Certificate Transparency logs from **crt.sh**.
It continuously scans, compares results with previously known subdomains, and instantly alerts the admin on Telegram.

Perfect for:

✔ Bug Bounty Hunters
✔ Pentesters / Red Teamers
✔ Domain & Infrastructure Security
✔ DevOps / SRE Monitoring
✔ Security Researchers

---

## 🚀 Features

* 🔐 **Admin Authentication (Password Based)**
* 🧩 **Add / Remove Websites Easily**
* 📋 **List All Monitored Websites**
* 🕵️ **Real-Time Background Subdomain Monitoring**
* 🔁 **Auto-Retry for Timeouts / Rate Limits**
* 🔔 **Instant Telegram Alerts for New Subdomains**
* ❌ **Error Notifications Sent Directly to Admin**
* ✔ **Saves previously found subdomains locally**
* ⏱ **Default scan interval: Every 1 hour**
* 💾 Uses two JSON files:

  * `config.json` – Bot config & monitored sites
  * `known_subdomains.json` – Detected subdomains stored permanently

---

## 📦 Installation & Setup

### 1️⃣ Clone the Repository

```bash
git clone https://github.com/your-username/subdomain-monitor-bot.git
cd subdomain-monitor-bot
```

### 2️⃣ Install Required Dependencies

```bash
pip install -r requirements.txt
```

### 3️⃣ Configure the Bot

Your `config.json` will be auto-created on the first run, but you can manually set:

```json
{
    "telegram_bot_token": "YOUR_TELEGRAM_BOT_TOKEN",
    "admin_user_id": "YOUR_TELEGRAM_USER_ID",
    "password": "YOUR_PASSWORD",
    "websites": []
}
```

To get your Telegram User ID:
Search **@userinfobot** on Telegram.

To create a Telegram bot:
Use **@BotFather** → “/newbot”

---

## ▶️ Usage

### Run the bot:

```bash
python bot.py
```

### Telegram Commands

| Command                 | Description                                   |
| ----------------------- | --------------------------------------------- |
| `/start`                | Authenticate and open main menu               |
| ➕ **Add Website**       | Add a domain to scan (example: `example.com`) |
| ➖ **Remove Website**    | Select a domain to delete                     |
| 📋 **List Websites**    | Shows all monitored domains                   |
| ▶️ **Start Monitoring** | Begins periodic scanning                      |
| ⏹️ **Stop Monitoring**  | Stops scanning                                |

---

## 📨 Example Notification

When new subdomains are detected:

```
🚨 New subdomains detected on example.com

📊 Total found: 5

`api.example.com`
`dev.example.com`
`test.example.com`
`cdn.example.com`
`mail.example.com`
```

---

## ⚠️ Error Handling & Resilience

The bot includes:

* 3-Level retry system
* Backoff delays (for 429 / 503 errors)
* Timeout handling
* Network failure auto-reconnect
* Error messages pushed directly to admin

---

## 🗂️ Project Structure

```
📁 subdomain-monitor-bot
│
├── bot.py                     # Main bot script
├── config.json                # Configuration (auto created)
├── known_subdomains.json      # Stores found subdomains
├── requirements.txt           # Python dependencies
└── README.md                  # Documentation
```

---

## 🛠️ Tech Stack

* Python 3.x
* TeleBot (pyTelegramBotAPI)
* Requests
* crt.sh Certificate Transparency Logs

---

## 🔧 Future Improvements (Optional)

* Database integration (SQLite / MongoDB)
* Dashboard for subdomain history
* Multi-user access
* Webhook-based Telegram deployment
* Docker support

---

## 🤝 Contributing

Pull requests and feature suggestions are welcome!
Feel free to open issues for bugs, improvements, or questions.

---

## 📝 License

This project is licensed under the **MIT License** — free to use, modify, and distribute.

---
