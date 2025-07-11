import os
import json
import logging
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.constants import ParseMode
from openai import OpenAI
from cachetools import TTLCache
import aiohttp
import signal

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

# States for conversation handler
MAIN_MENU, LICENSE_INPUT, CHAT_STATE = range(3)

# Cache for storing user license status (TTL: 1 hour)
license_cache = TTLCache(maxsize=1000, ttl=3600)

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

# Global variables
application = None
shutdown_event = asyncio.Event()

async def cleanup_webhook():
    """Clean up webhook and session."""
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteWebhook?drop_pending_updates=true"
            async with session.get(url) as response:
                if response.status == 200:
                    logger.info("Successfully cleaned up webhook")
                else:
                    logger.error(f"Failed to clean up webhook: {response.status}")
    except Exception as e:
        logger.error(f"Error during webhook cleanup: {e}")

async def verify_license(license_key: str) -> bool:
    """Verify license key with WordPress site."""
    url = f"{WORDPRESS_BASE_URL}/wp-json/millionisho/v1/verify-license"
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    data = {
        'license_key': license_key
    }
    
    logger.info(f"Verifying license at URL: {url}")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, headers=headers) as response:
                logger.info(f"License verification response status: {response.status}")
                response_text = await response.text()
                logger.info(f"License verification response: {response_text}")
                
                if response.status == 200:
                    try:
                        data = json.loads(response_text)
                        is_valid = data.get('valid', False)
                        logger.info(f"License is valid: {is_valid}")
                        return is_valid
                    except json.JSONDecodeError as e:
                        logger.error(f"Error parsing JSON response: {e}")
                        return False
                else:
                    logger.error(f"Error response from WordPress: {response.status}")
                    return False
    except Exception as e:
        logger.error(f"Error verifying license: {str(e)}")
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
        logger.info(f"Received license key: {license_key}")
        is_valid = await verify_license(license_key)
        if is_valid:
            user_id = str(update.message.from_user.id)
            license_cache[user_id] = True
            await update.message.reply_text("لایسنس شما با موفقیت تایید شد! ✅")
            context.user_data['state'] = None
        else:
            await update.message.reply_text("لایسنس نامعتبر است. لطفاً مطمئن شوید که کد را درست وارد کرده‌اید و دوباره تلاش کنید.")
    elif context.user_data['state'] == CHAT_STATE:
        try:
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": update.message.text}]
            )
            await update.message.reply_text(response.choices[0].message.content)
        except Exception as e:
            logger.error(f"Error in GPT response: {e}")
            await update.message.reply_text("متأسفانه در پردازش درخواست شما مشکلی پیش آمد. لطفاً دوباره تلاش کنید.")

async def shutdown():
    """Cleanup and shutdown the bot gracefully."""
    global application
    
    logger.info("Starting graceful shutdown...")
    
    if application:
        await cleanup_webhook()
        await application.stop()
        await application.shutdown()
    
    logger.info("Bot shutdown complete")

def signal_handler():
    """Handle system signals for graceful shutdown."""
    logger.info("Received shutdown signal")
    shutdown_event.set()

async def main():
    """Run the bot."""
    global application
    
    # Clean up any existing webhook
    await cleanup_webhook()
    
    logger.info("Starting bot...")
    logger.info(f"WordPress API URL: {WORDPRESS_BASE_URL}")
    
    # Initialize bot
    application = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .build()
    )

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Set up signal handlers for graceful shutdown
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda s, f: signal_handler())

    try:
        # Initialize and start the application
        await application.initialize()
        await application.start()
        await application.run_polling(drop_pending_updates=True)
        
        # Wait for shutdown signal
        await shutdown_event.wait()
        
        # Perform cleanup
        await shutdown()
        
    except Exception as e:
        logger.error(f"Error in main loop: {e}")
        await shutdown()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot stopped due to error: {e}")
    finally:
        # Ensure event loop is properly closed
        if not asyncio.get_event_loop().is_closed():
            asyncio.get_event_loop().close()