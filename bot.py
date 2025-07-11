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
from config import (
    TELEGRAM_TOKEN,
    OPENAI_API_KEY,
    WORDPRESS_BASE_URL,
    PROXY_URL,
    CACHE_TTL,
    CACHE_MAX_SIZE
)

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot.log')
    ]
)
logger = logging.getLogger(__name__)

# States for conversation handler
MAIN_MENU, LICENSE_INPUT, CHAT_STATE = range(3)

# Cache for storing user license status
license_cache = TTLCache(maxsize=CACHE_MAX_SIZE, ttl=CACHE_TTL)

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

# Global variables
application = None
is_running = False

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
        timeout = aiohttp.ClientTimeout(total=10)  # 10 seconds timeout
        async with aiohttp.ClientSession(timeout=timeout) as session:
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
    except asyncio.TimeoutError:
        logger.error("License verification timeout")
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
            await query.message.reply_text(
                "برای استفاده از این بخش نیاز به لایسنس معتبر دارید.\n"
                "از دکمه «وارد کردن لایسنس 🔑» استفاده کنید."
            )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle regular messages."""
    if 'state' not in context.user_data:
        await start(update, context)
        return

    if context.user_data['state'] == LICENSE_INPUT:
        license_key = update.message.text.strip()
        if not license_key:
            await update.message.reply_text("لطفاً یک کد لایسنس معتبر وارد کنید.")
            return
            
        logger.info(f"Received license key: {license_key}")
        is_valid = await verify_license(license_key)
        if is_valid:
            user_id = str(update.message.from_user.id)
            license_cache[user_id] = True
            await update.message.reply_text(
                "لایسنس شما با موفقیت تایید شد! ✅\n"
                "حالا می‌توانید از بخش «صحبت با هوش مصنوعی 🤖» استفاده کنید."
            )
            await start(update, context)
            context.user_data['state'] = None
        else:
            await update.message.reply_text(
                "لایسنس نامعتبر است. لطفاً مطمئن شوید که کد را درست وارد کرده‌اید و دوباره تلاش کنید."
            )
    elif context.user_data['state'] == CHAT_STATE:
        user_id = str(update.message.from_user.id)
        if user_id not in license_cache or not license_cache[user_id]:
            await update.message.reply_text("لایسنس شما منقضی شده است. لطفاً دوباره لایسنس خود را وارد کنید.")
            context.user_data['state'] = None
            await start(update, context)
            return
            
        try:
            await update.message.reply_text("در حال پردازش درخواست شما...")
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant. Please respond in Persian (Farsi) language."},
                    {"role": "user", "content": update.message.text}
                ],
                temperature=0.7,
                max_tokens=2000
            )
            await update.message.reply_text(response.choices[0].message.content)
        except Exception as e:
            logger.error(f"Error in GPT response: {e}")
            await update.message.reply_text(
                "متأسفانه در پردازش درخواست شما مشکلی پیش آمد.\n"
                "لطفاً چند لحظه دیگر دوباره تلاش کنید."
            )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors in the telegram bot."""
    logger.error(f"Exception while handling an update: {context.error}")
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "متأسفانه خطایی رخ داد. لطفاً دوباره تلاش کنید."
            )
    except Exception as e:
        logger.error(f"Error in error handler: {e}")

async def shutdown():
    """Cleanup and shutdown the bot gracefully."""
    global application, is_running
    
    if application and is_running:
        logger.info("Stopping bot...")
        is_running = False
        try:
            if application.running:
                await application.stop()
            logger.info("Bot stopped successfully")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

def signal_handler(signum, frame):
    """Handle system signals for graceful shutdown."""
    logger.info(f"Received signal {signum}")
    if asyncio.get_event_loop().is_running():
        asyncio.create_task(shutdown())

async def main() -> None:
    """Start the bot."""
    global application, is_running
    
    try:
        # Build the application with proxy if configured
        builder = Application.builder().token(TELEGRAM_TOKEN)
        if PROXY_URL:
            builder.proxy_url(PROXY_URL)
        application = builder.build()

        # Add handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CallbackQueryHandler(button_callback))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application.add_error_handler(error_handler)

        # Set up signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Start the bot
        logger.info("Starting bot...")
        is_running = True
        
        # Run the bot until a stop signal is received
        await application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
            close_loop=False
        )

    except Exception as e:
        logger.error(f"Error running bot: {e}")
    finally:
        await shutdown()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot stopped due to error: {e}")