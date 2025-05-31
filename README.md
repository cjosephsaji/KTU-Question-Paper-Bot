# KTU-Question-Paper-Bot
Retrieves PYQ Papers from the JEC Digital Library


# 🎓 Question Paper Bot

A Telegram bot that helps users search, find, and download question papers from an institutional repository. The bot scrapes question papers from a DSpace repository and delivers them directly to users via Telegram.

### Installation

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure the bot**
   
   The bot will create a `bot_config.json` file on first run. You can either:
   
   **Option A: Edit the config file after first run**
   ```json
   {
     "bot_token": "YOUR_BOT_TOKEN_HERE",
     "admin_user_id": YOUR_TELEGRAM_USER_ID
   }
   ```
   
   **Option B: Modify the default config in the code**
   ```python
   default_config = {
       'bot_token': "YOUR_BOT_TOKEN_HERE",
       'admin_user_id': YOUR_TELEGRAM_USER_ID
   }
   ```

4. **Run the bot**
   ```bash
   python bot.py
   ```

## 🔧 Configuration

### Getting Your Bot Token

1. Open Telegram and search for `@BotFather`
2. Send `/newbot` command
3. Choose a name and username for your bot
4. Copy the provided token
5. Add it to your `bot_config.json` file

### Getting Your Telegram User ID

1. Search for `@userinfobot` on Telegram
2. Send `/start` command
3. Copy your User ID
4. Add it to the `admin_user_id` field in config
