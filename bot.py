import json
import logging
import re
import threading
import time
import requests
from telebot import TeleBot, types

# --- Configuration ---
CONFIG_FILE = "config.json"
KNOWN_SUBDOMAINS_FILE = "known_subdomains.json"
CHECK_INTERVAL = 3600  # Check every hour

# --- Logging ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Helper Functions ---
def load_json(filename, default_data=None):
    """Load data from a JSON file."""
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        if default_data is not None:
            save_json(filename, default_data)
        return default_data

def save_json(filename, data):
    """Save data to a JSON file."""
    with open(filename, 'w') as f:
        json.dump(data, f, indent=4)

def format_time_interval(seconds):
    """Convert seconds to a human-readable format (hours, minutes, seconds)."""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    parts = []
    if hours > 0:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes > 0:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    if secs > 0 or len(parts) == 0:
        parts.append(f"{secs} second{'s' if secs != 1 else ''}")
    
    return ", ".join(parts)

# --- Main Bot Class ---
class SubdomainBot:
    def __init__(self):
        self.config = load_json(CONFIG_FILE)
        if self.config is None:
            raise FileNotFoundError(f"Configuration file '{CONFIG_FILE}' not found. Please create it with the required settings.")
        self.bot = TeleBot(self.config["telegram_bot_token"])
        self.known_subdomains = load_json(KNOWN_SUBDOMAINS_FILE, {})
        self.authenticated_users = set()
        self.monitoring_active = False
        self.monitoring_thread = None

        self.setup_handlers()

    def setup_handlers(self):
        """Set up all the message and callback handlers for the bot."""
        self.bot.message_handler(commands=['start'])(self.start_command)
        # A new handler for menu buttons
        self.bot.message_handler(func=lambda message: self.is_admin(message) and message.from_user.id in self.authenticated_users)(self.handle_menu_selection)
        self.bot.message_handler(func=self.is_admin)(self.handle_authenticated_messages)
        # The callback handler is no longer needed for the main menu
        # self.bot.callback_query_handler(func=lambda call: True)(self.handle_callback_query)

    def is_admin(self, message):
        """Check if the user is the admin."""
        return str(message.from_user.id) == str(self.config["admin_user_id"])

    def start_command(self, message):
        """Handle the /start command."""
        if not self.is_admin(message):
            self.bot.reply_to(message, "You are not authorized to use this bot.")
            return

        if message.from_user.id in self.authenticated_users:
            self.show_main_menu(message.chat.id)
        else:
            msg = self.bot.send_message(message.chat.id, "Please enter the password to continue:")
            self.bot.register_next_step_handler(msg, self.check_password)

    def check_password(self, message):
        """Check the password provided by the user."""
        if message.text == self.config["password"]:
            self.authenticated_users.add(message.from_user.id)
            self.bot.send_message(message.chat.id, "Authentication successful!")
            self.show_main_menu(message.chat.id)
        else:
            self.bot.send_message(message.chat.id, "Incorrect password. Please try again.")
            self.start_command(message)

    def show_main_menu(self, chat_id):
        """Display the main menu with a reply keyboard."""
        markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
        add_btn = types.KeyboardButton("➕ Add Website")
        remove_btn = types.KeyboardButton("➖ Remove Website")
        list_btn = types.KeyboardButton("📋 List Websites")
        
        toggle_text = "⏹️ Stop Monitoring" if self.monitoring_active else "▶️ Start Monitoring"
        toggle_btn = types.KeyboardButton(toggle_text)
        
        markup.add(add_btn, remove_btn, list_btn, toggle_btn)
        self.bot.send_message(chat_id, "Main Menu:", reply_markup=markup)

    def handle_authenticated_messages(self, message):
        """Handle messages from authenticated users."""
        if message.from_user.id not in self.authenticated_users:
            self.start_command(message)
            return
        # Fallback for any message that is not a menu button
        self.bot.send_message(message.chat.id, "Please use the menu buttons.")
        self.show_main_menu(message.chat.id)

    def handle_menu_selection(self, message):
        """Handle menu selections from the reply keyboard."""
        if message.text == "➕ Add Website":
            msg = self.bot.send_message(message.chat.id, "Please send the website URL to add (e.g., example.com):", reply_markup=types.ReplyKeyboardRemove())
            self.bot.register_next_step_handler(msg, self.add_website)
        elif message.text == "➖ Remove Website":
            self.show_websites_for_removal(message.chat.id)
        elif message.text == "📋 List Websites":
            self.list_websites(message.chat.id)
        elif message.text.startswith("▶️ Start Monitoring") or message.text.startswith("⏹️ Stop Monitoring"):
            self.toggle_monitoring(message)

    def toggle_monitoring(self, message):
        """Toggle the monitoring state."""
        self.monitoring_active = not self.monitoring_active
        if self.monitoring_active:
            self.bot.send_message(message.chat.id, "▶️ Monitoring started.")
            self.start_monitoring_thread()
        else:
            self.bot.send_message(message.chat.id, "⏹️ Monitoring stopped.")
            # The thread will stop on its own
        self.show_main_menu(message.chat.id)

    def start_monitoring_thread(self):
        """Start the background monitoring thread."""
        if self.monitoring_thread is None or not self.monitoring_thread.is_alive():
            self.monitoring_thread = threading.Thread(target=self.monitoring_loop)
            self.monitoring_thread.daemon = True
            self.monitoring_thread.start()

    def monitoring_loop(self):
        """The main loop for the monitoring thread."""
        logger.info("Monitoring loop started.")
        while self.monitoring_active:
            new_subdomains_found = False
            for website in self.config["websites"]:
                found_new = self.check_website_for_subdomains(website)
                if found_new:
                    new_subdomains_found = True
                # Add delay between websites to avoid rate limiting
                if len(self.config["websites"]) > 1:
                    time.sleep(10)  # Wait 10 seconds between different websites
            
            # Send notification if no new subdomains were found
            if not new_subdomains_found and self.config["websites"]:
                self.send_no_new_subdomains_notification()
            
            time.sleep(CHECK_INTERVAL)
        logger.info("Monitoring loop finished.")

    def check_website_for_subdomains(self, website):
        """Check for new subdomains using the crt.sh API with a retry mechanism.
        Returns True if new subdomains were found, False otherwise."""
        logger.info(f"Checking crt.sh for: {website}")
        url = f"https://crt.sh/?q=%.{website}&output=json"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        retries = 3
        for attempt in range(retries):
            try:
                # Increase timeout to 60 seconds to handle slow responses
                response = requests.get(url, timeout=60, headers=headers)
                
                # Handle 429 rate limiting errors with longer backoff
                if response.status_code == 429:
                    # Check for Retry-After header, otherwise use exponential backoff
                    retry_after = response.headers.get('Retry-After')
                    if retry_after:
                        try:
                            wait_time = int(retry_after)
                        except ValueError:
                            wait_time = (2 ** attempt) * 300  # Default: 300s, 600s, 1200s
                    else:
                        wait_time = (2 ** attempt) * 300  # Exponential backoff: 300s, 600s, 1200s
                    
                    logger.warning(f"429 Too Many Requests for {website} (attempt {attempt + 1}/{retries}). Waiting {wait_time}s...")
                    if attempt + 1 < retries:
                        time.sleep(wait_time)
                        continue
                    else:
                        error_message = f"Could not fetch data from crt.sh for {website} after {retries} attempts: 429 Client Error: Too Many Requests"
                        logger.error(error_message)
                        self.send_error_notification(error_message)
                        return False
                
                # Handle 503 errors specifically with longer backoff
                if response.status_code == 503:
                    wait_time = (2 ** attempt) * 60  # Exponential backoff: 60s, 120s, 240s
                    logger.warning(f"503 Service Unavailable for {website} (attempt {attempt + 1}/{retries}). Waiting {wait_time}s...")
                    if attempt + 1 < retries:
                        time.sleep(wait_time)
                        continue
                    else:
                        error_message = f"Could not fetch data from crt.sh for {website} after {retries} attempts: 503 Server Error: Service Unavailable"
                        logger.error(error_message)
                        self.send_error_notification(error_message)
                        return False
                
                response.raise_for_status()

                if not response.text:
                    logger.warning(f"Received empty response from crt.sh for {website}")
                    return False
                
                try:
                    data = response.json()
                except json.JSONDecodeError:
                    logger.error(f"Failed to decode JSON from crt.sh for {website}")
                    return False

                subdomains = self.extract_subdomains_from_crtsh(data)
                
                if not subdomains:
                    logger.info(f"No subdomains found on crt.sh for {website}")
                else:
                    logger.info(f"Found {len(subdomains)} subdomains on crt.sh for {website}")

                return self.process_new_subdomains(website, subdomains)  # Returns True if new subdomains found

            except requests.exceptions.Timeout as e:
                # Handle timeout errors specifically with longer backoff
                wait_time = (2 ** attempt) * 45  # Exponential backoff: 45s, 90s, 180s
                logger.warning(f"Timeout error for {website} (attempt {attempt + 1}/{retries}): {e}")
                if attempt + 1 < retries:
                    logger.info(f"Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                else:
                    error_message = f"Could not fetch data from crt.sh for {website} after {retries} attempts: {e}"
                    logger.error(error_message)
                    self.send_error_notification(error_message)
                    return False
            except requests.RequestException as e:
                wait_time = (2 ** attempt) * 30  # Exponential backoff: 30s, 60s, 120s
                logger.warning(f"Attempt {attempt + 1}/{retries} failed for {website}: {e}")
                if attempt + 1 < retries:
                    logger.info(f"Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                else:
                    error_message = f"Could not fetch data from crt.sh for {website} after {retries} attempts: {e}"
                    logger.error(error_message)
                    self.send_error_notification(error_message)
                    return False

    def extract_subdomains_from_crtsh(self, data):
        """Extract unique subdomains from the crt.sh JSON response."""
        subdomains = set()
        if not isinstance(data, list):
            return subdomains
            
        for entry in data:
            name_value = entry.get('name_value')
            if name_value:
                # crt.sh often includes multiple lines for the same name, split and add
                for name in name_value.split('\n'):
                    # Remove wildcard prefixes
                    if name.startswith('*.'):
                        name = name[2:]
                    subdomains.add(name.lower())
        return subdomains

    def process_new_subdomains(self, website, found_subdomains):
        """Process newly found subdomains and send notifications.
        Returns True if new subdomains were found, False otherwise."""
        if website not in self.known_subdomains:
            self.known_subdomains[website] = []

        new_subdomains = []
        for sub in found_subdomains:
            if sub not in self.known_subdomains[website]:
                new_subdomains.append(sub)
                self.known_subdomains[website].append(sub)

        if new_subdomains:
            logger.info(f"Found {len(new_subdomains)} new subdomains on {website}")
            self.send_notification(website, new_subdomains)
            save_json(KNOWN_SUBDOMAINS_FILE, self.known_subdomains)
            return True
        return False

    def send_notification(self, website, new_subdomains):
        """Send a notification to the admin about new subdomains."""
        count = len(new_subdomains)
        message = f"🚨 *New subdomains detected on {website}*\n\n"
        message += f"📊 *Total found: {count}*\n\n"
        message += "\n".join([f"`{s}`" for s in new_subdomains])
        try:
            self.bot.send_message(self.config["admin_user_id"], message, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")

    def send_error_notification(self, error_message):
        """Send an error notification to the admin."""
        message = f"⚠️ An error occurred while scanning:\n\n`{error_message}`"
        try:
            self.bot.send_message(self.config["admin_user_id"], message, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Failed to send error notification: {e}")

    def send_no_new_subdomains_notification(self):
        """Send a notification when no new subdomains are found during a check cycle."""
        websites_list = "\n".join([f"• *{site}*" for site in self.config["websites"]])
        next_scan_time = format_time_interval(CHECK_INTERVAL)
        message = f"✅ *Scan Complete*\n\n"
        message += f"🔍 Checked all monitored websites:\n{websites_list}\n\n"
        message += f"✨ No new subdomains detected this cycle.\n"
        message += f"💤 All quiet on the subdomain front! 🎯\n\n"
        message += f"⏰ *Next scan in:* {next_scan_time}"
        try:
            self.bot.send_message(self.config["admin_user_id"], message, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Failed to send no new subdomains notification: {e}")

    def add_website(self, message):
        """Add a website to the monitoring list."""
        website = message.text.strip()
        if not website:
            self.bot.send_message(message.chat.id, "Invalid URL. Please try again.")
            return

        if website not in self.config["websites"]:
            self.config["websites"].append(website)
            save_json(CONFIG_FILE, self.config)
            self.bot.send_message(message.chat.id, f"✅ Website '{website}' added successfully.")
        else:
            self.bot.send_message(message.chat.id, f"⚠️ Website '{website}' is already in the list.")
        self.show_main_menu(message.chat.id)

    def list_websites(self, chat_id):
        """List all monitored websites."""
        websites = self.config["websites"]
        if not websites:
            self.bot.send_message(chat_id, "No websites are currently being monitored.")
            return

        message = "📋 Monitored Websites:\n"
        for i, site in enumerate(websites):
            message += f"{i+1}. {site}\n"
        
        self.bot.send_message(chat_id, message)
        self.show_main_menu(chat_id)

    def show_websites_for_removal(self, chat_id):
        """Prompt the user to enter the website to remove."""
        websites = self.config["websites"]
        if not websites:
            self.bot.send_message(chat_id, "No websites to remove.")
            self.show_main_menu(chat_id)
            return

        message = "📋 Monitored Websites:\n"
        for i, site in enumerate(websites):
            message += f"{i+1}. {site}\n"
        message += "\nPlease type the full name of the website you want to remove."
        
        msg = self.bot.send_message(chat_id, message, reply_markup=types.ReplyKeyboardRemove())
        self.bot.register_next_step_handler(msg, self.remove_website)

    def remove_website(self, message):
        """Remove a website from the monitoring list based on user input."""
        website_to_remove = message.text.strip()
        if website_to_remove in self.config["websites"]:
            self.config["websites"].remove(website_to_remove)
            save_json(CONFIG_FILE, self.config)
            self.bot.send_message(message.chat.id, f"✅ Website '{website_to_remove}' removed successfully.")
        else:
            self.bot.send_message(message.chat.id, f"⚠️ Website '{website_to_remove}' not found in the list.")
        
        self.show_main_menu(message.chat.id)

    def run(self):
        """Start the bot and handle connection errors."""
        logger.info("Bot is running...")
        while True:
            try:
                self.bot.polling(non_stop=True)
            except requests.exceptions.ConnectionError as e:
                logger.error(f"Connection error: {e}. Retrying in 15 seconds...")
                time.sleep(15)
            except Exception as e:
                logger.error(f"An unexpected error occurred: {e}. Retrying in 15 seconds...")
                time.sleep(15)

if __name__ == "__main__":
    bot = SubdomainBot()
    bot.run()
