import os
import json
import logging
import asyncio
import aiohttp
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ParseMode
from openai import OpenAI
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

# User states and data
user_states = {}
user_licenses = {}
user_current_post = {}

# Instagram-style system prompts
SYSTEM_PROMPTS = [
    """You are a social media content expert. Create an engaging Instagram-style post in Persian (Farsi) about {topic}. 
    Use one of these formats randomly:
    1. "فقط با 1 جمله قانعم کن که..."
    2. "درباره این هیچکس بهت نمیگه..."
    3. "هرچی درباره این موضوع می‌دونی بذار پشت در بیا تو!"
    4. "۵ اشتباه رایج..."
    5. "با این کارا از همه جلو بزن"
    6. "اگه میخای این کارو بکنی باید..."
    7. "باورم نمیشه اینو دارم رایگان بهتون میگم ولی..."
    8. "کاش اوایل کارم می‌دونستم که..."
    9. "میدونی چرا روی این پست وایسادی؟"
    10. "با این روش، همه رو پشت سر بذار و جلو بزن!"
    
    Make the content engaging, informative, and optimized for social media. Use emojis appropriately."""
]

async def get_wordpress_posts(page=1):
    """Get posts from WordPress site."""
    url = f"{WORDPRESS_BASE_URL}/wp-json/wp/v2/posts"
    params = {
        'page': page,
        'per_page': 1,
        '_embed': 1
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    posts = await response.json()
                    total_pages = int(response.headers.get('X-WP-TotalPages', 1))
                    return posts[0] if posts else None, total_pages
                return None, 0
    except Exception as e:
        logger.error(f"Error fetching WordPress posts: {e}")
        return None, 0

async def verify_license(license_key: str) -> bool:
    """Verify license key with WordPress site."""
    url = f"{WORDPRESS_BASE_URL}/wp-json/licensing/v1/verify"
    
    try:
        conn = aiohttp.TCPConnector(ssl=False)
        timeout = aiohttp.ClientTimeout(total=30)
        
        async with aiohttp.ClientSession(connector=conn, timeout=timeout) as session:
            headers = {
                'Accept': 'application/json',
                'User-Agent': 'Millionisho-Bot/1.0'
            }
            
            params = {'key': license_key}
            
            logger.info(f"Sending license verification request to: {url}")
            logger.info(f"Request params: {params}")
            
            async with session.get(url, params=params, headers=headers) as response:
                logger.info(f"Response status: {response.status}")
                text = await response.text()
                logger.info(f"Response body: {text}")
                
                if response.status == 200:
                    try:
                        data = json.loads(text)
                        return data.get('status') == 'valid'
                    except json.JSONDecodeError:
                        logger.error("Failed to parse JSON response")
                        return False
                return False
                
    except Exception as e:
        logger.error(f"License verification error: {str(e)}")
        return False

def get_main_keyboard(user_id: str):
    """Get main keyboard based on user's license status."""
    keyboard = []
    
    if user_id in user_licenses and user_licenses[user_id]:
        keyboard.extend([
            [
                InlineKeyboardButton("چت با هوش مصنوعی 🤖", callback_data="chat"),
                InlineKeyboardButton("آخرین مطالب 📚", callback_data="posts")
            ],
            [InlineKeyboardButton("خروج از حساب 🚪", callback_data="logout")]
        ])
    else:
        keyboard.append([InlineKeyboardButton("وارد کردن لایسنس 🔑", callback_data="license")])
    
    return InlineKeyboardMarkup(keyboard)

async def show_post(update: Update, context: ContextTypes.DEFAULT_TYPE, page=1):
    """Show WordPress post with navigation buttons."""
    post, total_pages = await get_wordpress_posts(page)
    if not post:
        await update.callback_query.message.edit_text(
            "❌ خطا در دریافت مطلب. لطفاً بعداً تلاش کنید.",
            reply_markup=get_main_keyboard(str(update.effective_user.id))
        )
        return

    user_id = str(update.effective_user.id)
    user_current_post[user_id] = page

    keyboard = []
    nav_buttons = []
    
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("قبلی ⬅️", callback_data=f"post_{page-1}"))
    if page < total_pages:
        nav_buttons.append(InlineKeyboardButton("➡️ بعدی", callback_data=f"post_{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    keyboard.append([InlineKeyboardButton("🏠 بازگشت به منو", callback_data="menu")])
    
    title = post.get('title', {}).get('rendered', '')
    excerpt = post.get('excerpt', {}).get('rendered', '')
    link = post.get('link', '')
    
    message_text = f"📝 *{title}*\n\n{excerpt}\n\n[مشاهده کامل مطلب]({link})"
    
    try:
        await update.callback_query.message.edit_text(
            message_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.error(f"Error showing post: {e}")
        await update.callback_query.message.edit_text(
            "❌ خطا در نمایش مطلب. لطفاً بعداً تلاش کنید.",
            reply_markup=get_main_keyboard(str(update.effective_user.id))
        )

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    user_id = str(update.effective_user.id)
    await update.message.reply_text(
        "به ربات میلیونی‌شو خوش آمدید! 👋\n"
        "لطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
        reply_markup=get_main_keyboard(user_id)
    )

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button clicks."""
    query = update.callback_query
    user_id = str(update.effective_user.id)
    
    await query.answer()
    
    if query.data == "license":
        user_states[user_id] = "awaiting_license"
        await query.message.edit_text(
            "لطفاً کد لایسنس خود را وارد کنید:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🏠 بازگشت به منو", callback_data="menu")
            ]])
        )
    
    elif query.data == "chat":
        if user_id in user_licenses and user_licenses[user_id]:
            user_states[user_id] = "awaiting_topic"
            await query.message.edit_text(
                "🎯 لطفاً موضوع پست خود را وارد کنید:\n\n"
                "مثال: دیجیتال مارکتینگ، کسب درآمد از اینستاگرام، افزایش فروش و...",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 بازگشت به منو", callback_data="menu")
                ]])
            )
        else:
            await query.message.edit_text(
                "برای استفاده از این بخش نیاز به لایسنس معتبر دارید.\n"
                "لطفاً ابتدا لایسنس خود را وارد کنید.",
                reply_markup=get_main_keyboard(user_id)
            )
    
    elif query.data == "posts":
        await show_post(update, context, 1)
    
    elif query.data.startswith("post_"):
        page = int(query.data.split("_")[1])
        await show_post(update, context, page)
    
    elif query.data == "logout":
        if user_id in user_licenses:
            del user_licenses[user_id]
        if user_id in user_states:
            del user_states[user_id]
        if user_id in user_current_post:
            del user_current_post[user_id]
        
        await query.message.edit_text(
            "✅ شما با موفقیت خارج شدید.\n"
            "برای استفاده مجدد، لایسنس خود را وارد کنید:",
            reply_markup=get_main_keyboard(user_id)
        )
    
    elif query.data == "menu":
        await query.message.edit_text(
            "به ربات میلیونی‌شو خوش آمدید! 👋\n"
            "لطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
            reply_markup=get_main_keyboard(user_id)
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user messages."""
    if not update.message or not update.message.text:
        return
        
    user_id = str(update.effective_user.id)
    message_text = update.message.text.strip()
    
    if user_id not in user_states:
        await start_command(update, context)
        return
    
    state = user_states[user_id]
    
    if state == "awaiting_license":
        if not message_text:
            await update.message.reply_text(
                "لطفاً یک کد لایسنس معتبر وارد کنید.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 بازگشت به منو", callback_data="menu")
                ]])
            )
            return
            
        is_valid = await verify_license(message_text)
        
        if is_valid:
            user_licenses[user_id] = True
            user_states[user_id] = None
            await update.message.reply_text(
                "✅ لایسنس شما با موفقیت تأیید شد!\n"
                "حالا می‌توانید از امکانات ربات استفاده کنید.",
                reply_markup=get_main_keyboard(user_id)
            )
        else:
            await update.message.reply_text(
                "❌ لایسنس نامعتبر است.\n"
                "لطفاً دوباره تلاش کنید یا با پشتیبانی تماس بگیرید.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 بازگشت به منو", callback_data="menu")
                ]])
            )
    
    elif state == "awaiting_topic":
        try:
            await update.message.reply_text("🤔 در حال ساخت محتوای جذاب...")
            
            system_prompt = random.choice(SYSTEM_PROMPTS).format(topic=message_text)
            
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": f"لطفاً یک پست جذاب درباره {message_text} بنویس."
                    }
                ],
                temperature=0.8,
                max_tokens=2000
            )
            
            await update.message.reply_text(
                response.choices[0].message.content,
                reply_markup=get_main_keyboard(user_id)
            )
            
            # Ask if they want to generate another post
            user_states[user_id] = "awaiting_topic"
            await update.message.reply_text(
                "🎯 می‌خواهید درباره موضوع دیگری پست بسازم؟\n"
                "موضوع جدید را وارد کنید یا به منو برگردید:",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 بازگشت به منو", callback_data="menu")
                ]])
            )
            
        except Exception as e:
            logger.error(f"GPT error: {e}")
            await update.message.reply_text(
                "❌ متأسفانه در پردازش درخواست شما مشکلی پیش آمد.\n"
                "لطفاً چند دقیقه دیگر دوباره تلاش کنید.",
                reply_markup=get_main_keyboard(user_id)
            )
    
    else:
        await update.message.reply_text(
            "لطفاً از منوی اصلی یکی از گزینه‌ها را انتخاب کنید:",
            reply_markup=get_main_keyboard(user_id)
        )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors."""
    logger.error(f"Error: {context.error}")
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ متأسفانه خطایی رخ داد.\n"
                "لطفاً دوباره تلاش کنید.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🏠 بازگشت به منو", callback_data="menu")
                ]])
            )
    except:
        pass

def main():
    """Start the bot."""
    try:
        # Configure proxy settings for the entire application
        if PROXY_URL:
            os.environ['HTTPS_PROXY'] = PROXY_URL
            os.environ['HTTP_PROXY'] = PROXY_URL
            logger.info(f"Using proxy: {PROXY_URL}")
        
        # Create and configure the application
        application = (
            Application.builder()
            .token(TELEGRAM_TOKEN)
            .build()
        )
        
        # Add handlers
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CallbackQueryHandler(handle_button))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application.add_error_handler(error_handler)
        
        # Start the bot
        logger.info("Starting bot...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        raise

if __name__ == '__main__':
    main()