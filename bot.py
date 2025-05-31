import logging
import json
import os
import re
from datetime import datetime
from typing import List, Optional
import requests
from bs4 import BeautifulSoup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BASE_URL = "http://202.88.225.92"

class QuestionPaperBot:
    def __init__(self):
        self.users_file = 'bot_users.json'
        self.config_file = 'bot_config.json'
        self.load_users()
        self.load_config()
    
    def load_config(self):
        default_config = {
            'bot_token': "DEFAULT_BOT_TOKEN",
            'admin_user_id': DEFAULT_ADMIN_ID
        }
        
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    self.config = json.load(f)
                for key, default_value in default_config.items():
                    if key not in self.config:
                        self.config[key] = default_value
            except (json.JSONDecodeError, FileNotFoundError):
                self.config = default_config
        else:
            self.config = default_config
        
        self.save_config()
    
    def save_config(self):
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def get_bot_token(self):
        return self.config.get('bot_token', '')
    
    def get_admin_user_id(self):
        return self.config.get('admin_user_id', 0)
    
    def load_users(self):
        if os.path.exists(self.users_file):
            try:
                with open(self.users_file, 'r') as f:
                    self.users = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                self.users = {}
        else:
            self.users = {}
    
    def save_users(self):
        with open(self.users_file, 'w') as f:
            json.dump(self.users, f, indent=2)
    
    def add_user(self, user_id: int, username: str = None, first_name: str = None, last_name: str = None):
        user_key = str(user_id)
        if user_key not in self.users:
            self.users[user_key] = {
                'user_id': user_id,
                'username': username,
                'first_name': first_name,
                'last_name': last_name,
                'joined_date': datetime.now().isoformat()
            }
        else:
            self.users[user_key].update({
                'username': username,
                'first_name': first_name,
                'last_name': last_name
            })
        self.save_users()
    
    def get_all_users(self) -> List[int]:
        return [int(user_id) for user_id in self.users.keys()]
    
    def clean_filename(self, filename: str) -> str:
        if not filename:
            return "document"
        
        filename = filename.strip('"\'')
        
        if '?' in filename:
            filename = filename.split('?')[0]
        
        unwanted_patterns = [
            r'[?&]sequence=\d+',
            r'[?&]isAllowed=\w+',
            r'[?&]origin=\w+',
            r'[?&]download=\w+',
            r'[?&].*$',
            r';.*$',
            r'\s+sequence=\d+',
            r'\s+isAllowed=\w+',
        ]
        
        for pattern in unwanted_patterns:
            filename = re.sub(pattern, '', filename, flags=re.IGNORECASE)
        
        filename = filename.strip()
        
        if not filename:
            filename = "document"
        
        filename = re.sub(r'[^\w\s.-]', '', filename)
        
        filename = re.sub(r'\s+', ' ', filename).strip()
        
        if '.' not in filename:
            filename += '.pdf'
        
        return filename
    
    def search_artifacts(self, query: str) -> tuple[bool, List[dict], str]:
        try:
            search_url = f"{BASE_URL}/xmlui/search?scope=%2F&query={query}&rpp=100&sort_by=0"
            response = requests.get(search_url, timeout=5)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'lxml')
            artifact_divs = soup.find_all('div', class_='artifact-title')
            
            if not artifact_divs:
                return False, [], f"No results found for query '{query}'. Please check your search term and try again."
            
            artifacts = []
            for div in artifact_divs:
                a_tag = div.find('a')
                if a_tag and a_tag.has_attr('href'):
                    artifacts.append({
                        'title': a_tag.get_text(strip=True),
                        'link': a_tag['href']
                    })
            
            if not artifacts:
                return False, [], f"Found {len(artifact_divs)} results but couldn't extract valid links. The website structure might have changed."
            
            return True, artifacts, ""
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during search: {str(e)}")
            return False, [], f"Network error while searching: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error during search: {str(e)}")
            return False, [], f"An unexpected error occurred. Please try again later."
    
    def get_file_info(self, artifact_link: str) -> tuple[bool, List[dict], str]:
        try:
            full_url = artifact_link if artifact_link.startswith('http') else BASE_URL + artifact_link
            response = requests.get(full_url, timeout=30)
            response.raise_for_status()
            
            page_soup = BeautifulSoup(response.text, 'lxml')
            file_list = page_soup.find(class_='file-list')
            
            if not file_list:
                return False, [], "No files found on this page. The page structure might have changed."
            
            rows = file_list.find_all(class_='ds-table-row')
            if not rows:
                return False, [], "No file rows found. The page structure might have changed."
            
            file_info = []
            for row in rows:
                a_in_row = row.find('a', href=True)
                if a_in_row:
                    file_url = a_in_row['href']
                    if not file_url.startswith('http'):
                        file_url = BASE_URL + file_url
                    
                    file_name = a_in_row.get_text(strip=True)
                    if not file_name or file_name == "":
                        file_name = file_url.split('/')[-1] if '/' in file_url else "Unknown File"
                    
                    clean_name = self.clean_filename(file_name)
                    
                    file_info.append({
                        'name': clean_name,
                        'url': file_url
                    })
            
            if not file_info:
                return False, [], "No downloadable files found on this page."
            
            return True, file_info, ""
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error while getting file info: {str(e)}")
            return False, [], f"Network error while accessing files: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error while getting file info: {str(e)}")
            return False, [], f"An unexpected error occurred while accessing files."
    
    def download_file(self, file_url: str) -> tuple[bool, bytes, str, str]:
        try:
            response = requests.get(file_url, timeout=60)
            response.raise_for_status()
            
            filename = "document"
            if 'content-disposition' in response.headers:
                cd = response.headers['content-disposition']
                filename_match = re.findall(r'filename[^;=\n]*=(([\'"]).*?\2|[^;\n]*)', cd)
                if filename_match:
                    filename = filename_match[0][0].strip('"\'')
            
            if filename == "document":
                filename = file_url.split('/')[-1] if '/' in file_url else "document"
            
            filename = self.clean_filename(filename)
            
            if '.' not in filename:
                content_type = response.headers.get('content-type', '')
                if 'pdf' in content_type:
                    filename += '.pdf'
                elif 'image' in content_type:
                    filename += '.jpg'
                elif 'text' in content_type:
                    filename += '.txt'
                elif 'word' in content_type:
                    filename += '.doc'
                else:
                    filename += '.pdf'
            
            return True, response.content, filename, ""
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error while downloading file: {str(e)}")
            return False, b"", "", f"Network error while downloading: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error while downloading file: {str(e)}")
            return False, b"", "", f"An unexpected error occurred while downloading."

bot = QuestionPaperBot()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    bot.add_user(user.id, user.username, user.first_name, user.last_name)
    
    welcome_message = f"""
🎓 Welcome to the Question Paper Bot, {user.first_name}!

I can help you find and download question papers. Here's how to use me:

📚 **How to search:**
Just send me a query (e.g., "EST100", "CS101", "MATH200")

📋 **What I'll do:**
1. Search for matching papers
2. Show you the list of available papers and their files
3. Let you download all files with a simple button click

🔧 **Commands:**
/help - Show this help message
/stats - Show bot statistics (admin only)

Just send me your query to get started!
    """
    
    await update.message.reply_text(welcome_message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
🤖 **Question Paper Bot Help**

**Basic Usage:**
• Send any query (e.g., "EST100") to search for papers
• Bot will show all available papers and their files
• Click "Download All Files" to receive all files directly
• Files will be sent as documents to your chat

**Error Handling:**
• If no results found, try different search terms
• If files aren't loading, the website might be down
• Large files (>50MB) will be provided as direct links
• Contact admin if you encounter persistent issues

**Tips:**
• Use course codes for better results
• Try variations of your search term
• Be patient - downloading might take a few minutes
• Files are sent directly to you, no need to click external links

Need more help? Contact the bot administrator.
    """
    await update.message.reply_text(help_text)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != bot.get_admin_user_id():
        await update.message.reply_text("❌ You don't have permission to use this command.")
        return
    
    user_count = len(bot.get_all_users())
    stats_text = f"""
📊 **Bot Statistics**

👥 Total Users: {user_count}
🔧 Status: Active
📊 Database: JSON-based storage

💾 Users data is stored in: bot_users.json
    """
    await update.message.reply_text(stats_text)

async def announce_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != bot.get_admin_user_id():
        await update.message.reply_text("❌ You don't have permission to use this command.")
        return
    
    if not context.args:
        await update.message.reply_text(
            "📢 **Announcement Usage:**\n"
            "/announce <your message here>\n\n"
            "This will send your message to all bot users."
        )
        return
    
    announcement = " ".join(context.args)
    users = bot.get_all_users()
    sent_count = 0
    failed_count = 0
    
    await update.message.reply_text(f"📤 Sending announcement to {len(users)} users...")
    
    for user_id in users:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"📢 **Announcement**\n\n{announcement}"
            )
            sent_count += 1
        except Exception as e:
            logger.error(f"Failed to send announcement to user {user_id}: {str(e)}")
            failed_count += 1
    
    result_text = f"""
✅ **Announcement Results**

📤 Successfully sent: {sent_count}
❌ Failed to send: {failed_count}
📊 Total users: {len(users)}
    """
    await update.message.reply_text(result_text)

async def handle_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    bot.add_user(user.id, user.username, user.first_name, user.last_name)
    
    query = update.message.text.strip()
    
    if not query:
        await update.message.reply_text("❌ Please send a valid search query.")
        return
    
    searching_msg = await update.message.reply_text(f"🔍 Searching for '{query}'...")
    
    success, artifacts, error_msg = bot.search_artifacts(query)
    
    if not success:
        await searching_msg.edit_text(f"❌ **Search Error**\n\n{error_msg}")
        return
    
    await searching_msg.edit_text(f"📚 Found {len(artifacts)} result(s) for '{query}'. Getting file information...\n\n⏳ Please wait...")
    
    all_files = []
    artifacts_with_files = []
    
    for artifact in artifacts:
        success_files, file_info, error_msg_files = bot.get_file_info(artifact['link'])
        if success_files and file_info:
            artifacts_with_files.append({
                'title': artifact['title'],
                'files': file_info
            })
            all_files.extend(file_info)
    
    if not artifacts_with_files:
        await searching_msg.edit_text(f"❌ No files found in any of the search results for '{query}'.")
        return
    
    result_text = f"📚 **Search Results for '{query}':**\n\n"
    result_text += f"📊 Found {len(artifacts_with_files)} paper(s) with {len(all_files)} total file(s)\n\n"
    
    for i, artifact_info in enumerate(artifacts_with_files, 1):
        result_text += f"**{i}. {artifact_info['title']}**\n"
        result_text += f"📁 Files ({len(artifact_info['files'])}):\n"
        
        for j, file in enumerate(artifact_info['files'], 1):
            result_text += f"   • {file['name']}\n"
        
        result_text += "\n"
    
    result_text += f"📥 **Total: {len(all_files)} files ready for download**"
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Download All Files", callback_data="download_all"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    context.user_data['all_files'] = all_files
    context.user_data['artifacts_with_files'] = artifacts_with_files
    context.user_data['query'] = query
    
    await searching_msg.edit_text(result_text, reply_markup=reply_markup)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "download_all":
        all_files = context.user_data.get('all_files', [])
        search_query = context.user_data.get('query', 'Unknown')
        
        if not all_files:
            await query.edit_message_text("❌ No files found. Please search again.")
            return
        
        await query.edit_message_text(f"📥 **Downloading {len(all_files)} files...**\n\n⏳ Please wait, this may take a while.")
        
        sent_count = 0
        failed_count = 0
        
        for i, file in enumerate(all_files, 1):
            try:
                progress_text = f"📥 **Downloading files... ({i}/{len(all_files)})**\n\n"
                progress_text += f"Current: {file['name']}\n"
                progress_text += f"✅ Sent: {sent_count}\n"
                progress_text += f"❌ Failed: {failed_count}"
                
                await query.edit_message_text(progress_text)
                
                success, file_data, filename, error_msg = bot.download_file(file['url'])
                
                if success:
                    if len(file_data) > 50 * 1024 * 1024:
                        await context.bot.send_message(
                            chat_id=query.from_user.id,
                            text=f"❌ File '{filename}' is too large (>50MB) to send via Telegram.\n\n📎 Direct link: {file['url']}"
                        )
                        failed_count += 1
                        continue
                    
                    from io import BytesIO
                    file_obj = BytesIO(file_data)
                    file_obj.name = filename
                    
                    await context.bot.send_document(
                        chat_id=query.from_user.id,
                        document=file_obj,
                        filename=filename,
                        caption=f"📄 {filename}\n🔍 Query: {search_query}"
                    )
                    sent_count += 1
                else:
                    await context.bot.send_message(
                        chat_id=query.from_user.id,
                        text=f"❌ Failed to download '{file['name']}': {error_msg}"
                    )
                    failed_count += 1
                    
            except Exception as e:
                logger.error(f"Error sending file {file['name']}: {str(e)}")
                await context.bot.send_message(
                    chat_id=query.from_user.id,
                    text=f"❌ Error sending '{file['name']}': {str(e)}"
                )
                failed_count += 1
        
        summary_text = f"""
✅ **Download Complete!**

📊 **Summary:**
✅ Successfully sent: {sent_count} files
❌ Failed: {failed_count} files
📁 Total files: {len(all_files)}

🔍 Search query: '{search_query}'
        """
        
        await query.edit_message_text(summary_text)
    
    elif query.data == "cancel":
        await query.edit_message_text("❌ Download cancelled.")
    
    else:
        await query.edit_message_text("❌ Invalid action. Please try again.")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")
    
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ An unexpected error occurred. Please try again later or contact the administrator."
        )

def main():
    bot_token = bot.get_bot_token()
    
    if not bot_token:
        print("❌ Bot token not found in config file. Please check bot_config.json")
        return
    
    application = Application.builder().token(bot_token).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("announce", announce_command))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_query))
    
    application.add_error_handler(error_handler)
    
    print("🤖 Question Paper Bot is starting...")
    application.run_polling()

if __name__ == '__main__':
    main()
