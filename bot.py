import logging
import json
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from openai import OpenAI
import aiohttp
from config import (
    TELEGRAM_TOKEN,
    OPENAI_API_KEY,
    WORDPRESS_BASE_URL,
    PROXY_URL
)

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

# Dictionary to store user states
user_states = {}

# Dictionary to store user licenses
user_licenses = {}

async def verify_license(license_key: str) -> bool:
    """Verify license key with WordPress site."""
    url = f"{WORDPRESS_BASE_URL}/wp-json/wp/v2/millionisho/verify-license"  # Updated API path
    data = {'license_key': license_key}
    
    logger.info(f"Verifying license key: {license_key}")
    logger.info(f"Sending request to: {url}")
    logger.info(f"Request data: {data}")
    
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
            if PROXY_URL:
                session._connector._proxy = PROXY_URL
                logger.info(f"Using proxy: {PROXY_URL}")
            
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'User-Agent': 'Millionisho-Bot/1.0',
                'Authorization': f'Bearer {license_key}'  # Added authorization
            }
            
            async with session.post(
                url,
                json=data,
                headers=headers
            ) as response:
                logger.info(f"Response status: {response.status}")
                response_text = await response.text()
                logger.info(f"Response body: {response_text}")
                
                if response.status == 200:
                    try:
                        response_data = json.loads(response_text)
                        is_valid = response_data.get('valid', False)
                        logger.info(f"License is valid: {is_valid}")
                        return is_valid
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse JSON response: {e}")
                        logger.error(f"Raw response: {response_text}")
                        return False
                else:
                    logger.error(f"Server returned non-200 status: {response.status}")
                    logger.error(f"Response body: {response_text}")
                    return False
    except asyncio.TimeoutError:
        logger.error("Request timed out after 10 seconds")
        return False
    except Exception as e:
        logger.error(f"Error during license verification: {str(e)}")
        logger.exception("Full traceback:")
        return False

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    keyboard = [
        [
            InlineKeyboardButton("وارد کردن لایسنس 🔑", callback_data="license"),
            InlineKeyboardButton("چت با هوش مصنوعی 🤖", callback_data="chat")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "به ربات میلیونی‌شو خوش آمدید! 👋\n"
        "لطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
        reply_markup=reply_markup
    )

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button clicks."""
    query = update.callback_query
    user_id = str(update.effective_user.id)
    
    await query.answer()
    
    if query.data == "license":
        user_states[user_id] = "awaiting_license"
        await query.message.reply_text(
            "لطفاً کد لایسنس خود را وارد کنید:"
        )
    
    elif query.data == "chat":
        if user_id in user_licenses and user_licenses[user_id]:
            user_states[user_id] = "chatting"
            await query.message.reply_text(
                "لطفاً سؤال خود را بپرسید. من با کمک GPT-4 به شما پاسخ خواهم داد."
            )
        else:
            await query.message.reply_text(
                "برای استفاده از این بخش نیاز به لایسنس معتبر دارید.\n"
                "لطفاً ابتدا لایسنس خود را وارد کنید."
            )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user messages."""
    user_id = str(update.effective_user.id)
    message_text = update.message.text
    
    if user_id not in user_states:
        await start_command(update, context)
        return
    
    state = user_states[user_id]
    
    if state == "awaiting_license":
        # Handle license verification
        is_valid = await verify_license(message_text)
        if is_valid:
            user_licenses[user_id] = True
            user_states[user_id] = "chatting"
            await update.message.reply_text(
                "✅ لایسنس شما با موفقیت تأیید شد!\n"
                "حالا می‌توانید از بخش چت با هوش مصنوعی استفاده کنید."
            )
            # Show main menu again
            await start_command(update, context)
        else:
            await update.message.reply_text(
                "❌ لایسنس نامعتبر است.\n"
                "لطفاً دوباره تلاش کنید یا با پشتیبانی تماس بگیرید."
            )
    
    elif state == "chatting":
        if not user_licenses.get(user_id):
            await update.message.reply_text(
                "⚠️ لایسنس شما منقضی شده است.\n"
                "لطفاً دوباره لایسنس خود را وارد کنید."
            )
            user_states[user_id] = "awaiting_license"
            return
        
        # Handle chat with GPT
        try:
            await update.message.reply_text("🤔 در حال پردازش سؤال شما...")
            
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant. Please respond in Persian (Farsi) language."
                    },
                    {
                        "role": "user",
                        "content": message_text
                    }
                ],
                temperature=0.7,
                max_tokens=2000
            )
            
            await update.message.reply_text(response.choices[0].message.content)
            
        except Exception as e:
            logger.error(f"GPT error: {e}")
            await update.message.reply_text(
                "❌ متأسفانه در پردازش درخواست شما مشکلی پیش آمد.\n"
                "لطفاً چند دقیقه دیگر دوباره تلاش کنید."
            )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors."""
    logger.error(f"Error: {context.error}")
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ متأسفانه خطایی رخ داد.\n"
                "لطفاً دوباره تلاش کنید."
            )
    except:
        pass

def main():
    """Start the bot."""
    # Create application with proxy if configured
    builder = Application.builder().token(TELEGRAM_TOKEN)
    if PROXY_URL:
        logger.info(f"Using proxy for Telegram: {PROXY_URL}")
        builder.proxy_url(PROXY_URL)
    application = builder.build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CallbackQueryHandler(handle_button))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    # Start the bot
    logger.info("Starting bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()