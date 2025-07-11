import os
import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.constants import ParseMode
from openai import OpenAI
from cachetools import TTLCache
import aiohttp
from aiohttp_socks import ProxyConnector

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Environment Variables
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '7631560101:AAEezcBRD_JXH5l5KNoBggflvqcVs4YPYbk')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
WORDPRESS_BASE_URL = os.getenv('WORDPRESS_BASE_URL', 'https://mirallino.ir')
PROXY_HOST = os.getenv('PROXY_HOST', 'm3.bernoclub.top')
PROXY_PORT = int(os.getenv('PROXY_PORT', '18979'))
PROXY_USERNAME = os.getenv('PROXY_USERNAME', 'bec3a75d-9030-4ca4-9ffc-ef8d76f46f94')
PROXY_PASSWORD = os.getenv('PROXY_PASSWORD', '')

# States for conversation handler
MAIN_MENU, LICENSE_INPUT, CHAT_STATE = range(3)

# Cache for storing user license status (TTL: 1 hour)
license_cache = TTLCache(maxsize=1000, ttl=3600)

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

# Proxy Configuration
PROXY_CONFIG = {
    'hostname': PROXY_HOST,
    'port': PROXY_PORT,
    'username': PROXY_USERNAME,
    'password': PROXY_PASSWORD
}

async def verify_license(license_key: str) -> bool:
    """Verify license key with WordPress site."""
    url = f"{WORDPRESS_BASE_URL}/wp-json/millionisho/v1/verify-license"
    try:
        connector = ProxyConnector.from_url(
            f'socks5://{PROXY_CONFIG["username"]}:{PROXY_CONFIG["password"]}@{PROXY_CONFIG["hostname"]}:{PROXY_CONFIG["port"]}'
        )
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.post(url, json={'license_key': license_key}) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('valid', False)
    except Exception as e:
        logger.error(f"Error verifying license: {e}")
    return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /start command."""
    keyboard = [
        [
            InlineKeyboardButton("وارد کردن لایسنس 🔑", callback_data="license"),
            InlineKeyboardButton("صحبت با هوش مصنوعی 🤖", callback_data="chat")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "به ربات میلیونی‌شو خوش آمدید! 👋\nلطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
        reply_markup=reply_markup
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "license":
        await query.message.reply_text("لطفاً کد لایسنس خود را وارد کنید:")
        context.user_data['state'] = LICENSE_INPUT
    elif query.data == "chat":
        # Check if user has valid license
        user_id = str(query.from_user.id)
        if user_id in license_cache and license_cache[user_id]:
            await query.message.reply_text("لطفاً سوال خود را بپرسید:")
            context.user_data['state'] = CHAT_STATE
        else:
            await query.message.reply_text("برای استفاده از این بخش نیاز به لایسنس معتبر دارید.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle regular messages."""
    if 'state' not in context.user_data:
        await update.message.reply_text("لطفاً از دستور /start استفاده کنید.")
        return

    if context.user_data['state'] == LICENSE_INPUT:
        license_key = update.message.text
        is_valid = await verify_license(license_key)
        if is_valid:
            user_id = str(update.message.from_user.id)
            license_cache[user_id] = True
            await update.message.reply_text("لایسنس شما با موفقیت تایید شد! ✅")
            context.user_data['state'] = None
        else:
            await update.message.reply_text("لایسنس نامعتبر است. لطفاً دوباره تلاش کنید.")
    elif context.user_data['state'] == CHAT_STATE:
        # Handle chat with GPT
        try:
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": update.message.text}]
            )
            await update.message.reply_text(response.choices[0].message.content)
        except Exception as e:
            logger.error(f"Error in GPT response: {e}")
            await update.message.reply_text("متأسفانه در پردازش درخواست شما مشکلی پیش آمد. لطفاً دوباره تلاش کنید.")

def main():
    """Run the bot."""
    print("Starting bot...")
    print(f"Using SOCKS5 proxy: {PROXY_CONFIG['hostname']}:{PROXY_CONFIG['port']}")
    
    # Initialize bot with proxy settings
    application = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .proxy_url(f"socks5://{PROXY_CONFIG['username']}:{PROXY_CONFIG['password']}@{PROXY_CONFIG['hostname']}:{PROXY_CONFIG['port']}")
        .get_updates_proxy_url(f"socks5://{PROXY_CONFIG['username']}:{PROXY_CONFIG['password']}@{PROXY_CONFIG['hostname']}:{PROXY_CONFIG['port']}")
        .build()
    )

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Start the bot
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()