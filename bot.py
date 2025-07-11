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
    """You are a professional social media content expert specializing in viral Instagram hooks in Persian (Farsi). Create ONE engaging hook about {topic} using one of these formats:

    Hook Templates:
    1. "۵ اشتباه رایج در {topic} که کسب و کارت رو نابود میکنه 😱"
    2. "۳ اشتباه مرگبار {topic} که باید همین الان متوقف کنی ⛔"
    3. "۷ نکته طلایی {topic} که رقبات نمیخوان بدونی 🔥"
    4. "اشتباه بزرگ {topic} که ۹۰٪ کسب و کارها انجام میدن 💀"
    5. "راز موفقیت در {topic} که هیچکس بهت نمیگه 🤫"
    6. "چرا {topic} شما شکست میخوره؟ (دلیل اصلی) ⚠️"
    7. "بهترین استراتژی {topic} که نتیجه‌ش تضمینیه 💯"
    8. "اگه تو {topic} موفق نیستی، این پست مال توئه 👆"
    9. "این اشتباهات {topic} داره کسب و کارت رو نابود میکنه 😨"
    10. "قبل از شروع {topic} حتما اینو بخون ⚡"

    Guidelines for the hook:
    1. Make it ONE line only - short, punchy, and attention-grabbing
    2. Use maximum 2 emojis strategically
    3. Focus on value and urgency
    4. Make it specific to the topic
    5. Use natural, conversational Farsi
    6. Avoid clickbait - deliver real value
    7. For business topics, focus on ROI and results
    8. For technical topics, focus on best practices and common mistakes
    9. For marketing topics, focus on growth and strategy
    10. Always maintain professional tone while being engaging

    Remember: The goal is to create a hook that's both professional AND attention-grabbing, while staying true to the topic's context."""
]

# Hook templates for direct use
HOOK_TEMPLATES = [
    "درباره {topic} هیچکس بهت نمیگه...",
    "هرچی درباره {topic} می‌دونی بذار پشت در بیا تو!",
    "۵ اشتباه رایج {topic}",
    "با این کارا از همه جلو بزن",
    "اگه میخای {topic} رو انجام بدی باید...",
    "باورم نمیشه اینو دارم رایگان بهتون میگم ولی {topic}...",
    "کاش اوایل کارم می‌دونستم که {topic} بهترین کار اینه که با روش {topic} پیش برم",
    "میدونی چرا روی این پست وایسادی؟",
    "با این روش، همه رو پشت سر بذار و جلو بزن!",
    "برای تو هم اتفاق افتاده که {topic}...",
    "می‌خوام یه رازی رو بهتون بگم {topic}...",
    "عمراً کسی بهت بگه که {topic}...",
    "عمراً این ترفند رو بلد باشی {topic}...",
    "مطمئنم این قرار زندگی تو عوض کنه {topic}...",
    "اینو اشتباه انجام میدی",
    "ویژگی جدیدی که تعداد کمی از مردم می‌دونند",
    "اگه بلد نیستی {topic} حتما تا آخر ببین",
    "تخفیف باورنکردنی",
    "۵ حرکت ایده آل",
    "ترفندهایی که باید بدونی تا {topic}...",
    "۳ ترفند خلاقانه برای {topic}...",
    "اینو اصلاً نمی‌دونی که {topic}...",
    "اگه می‌خوای {topic} این ریلز رو ببین",
    "اگه می‌خوای فقط تو یک هفته {topic} این ریلز رو ببین",
    "اگه می‌خوای خیلی سریع {topic}...",
    "آدم با جنبه هستی؟ می‌خوام یه ایده بهت بدم {topic}...",
    "می‌خوام بهت روشی رو بگم {topic}...",
    "این کارو همین الان باید انجامش بدی"
]

# Store used templates for each user
user_used_templates = {}

# Add after the user_current_post dictionary
user_current_template = {}

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

# Add after the get_main_keyboard function
def get_hook_keyboard(user_id: str):
    """Get keyboard with navigation buttons for hooks."""
    keyboard = [
        [
            InlineKeyboardButton("⬅️ قلاب قبلی", callback_data="prev_hook"),
            InlineKeyboardButton("قلاب بعدی ➡️", callback_data="next_hook")
        ],
        [InlineKeyboardButton("🏠 بازگشت به منو", callback_data="menu")]
    ]
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
    
    # Add these new conditions for hook navigation
    elif query.data in ["prev_hook", "next_hook"]:
        if user_id not in user_states or user_states[user_id] != "viewing_hooks":
            await query.message.edit_text(
                "لطفاً ابتدا موضوع خود را وارد کنید:",
                reply_markup=get_main_keyboard(user_id)
            )
            return
            
        topic = context.user_data.get("current_topic", "")
        if not topic:
            await query.message.edit_text(
                "لطفاً ابتدا موضوع خود را وارد کنید:",
                reply_markup=get_main_keyboard(user_id)
            )
            return
            
        hook = get_random_hook(user_id, topic)
        await query.message.edit_text(
            f"✨ قلاب پیشنهادی:\n\n{hook}",
            reply_markup=get_hook_keyboard(user_id)
        )
        return

    # Modify the chat handler to include hook templates
    elif query.data == "chat":
        if user_id in user_licenses and user_licenses[user_id]:
            user_states[user_id] = "awaiting_topic"
            await query.message.edit_text(
                "🎯 لطفاً موضوع مورد نظر خود را وارد کنید:\n\n"
                "مثال: دیجیتال مارکتینگ، کسب درآمد از اینستاگرام، افزایش فروش و...\n\n"
                "✨ می‌توانید از قالب‌های آماده استفاده کنید یا محتوای هوشمند تولید کنید.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📝 استفاده از قالب‌های آماده", callback_data="use_templates")],
                    [InlineKeyboardButton("🤖 تولید محتوای هوشمند", callback_data="use_ai")],
                    [InlineKeyboardButton("🏠 بازگشت به منو", callback_data="menu")]
                ])
            )
        else:
            await query.message.edit_text(
                "برای استفاده از این بخش نیاز به لایسنس معتبر دارید.",
                reply_markup=get_main_keyboard(user_id)
            )
    
    elif query.data == "use_templates":
        user_states[user_id] = "awaiting_topic_template"
        await query.message.edit_text(
            "🎯 لطفاً موضوع خود را وارد کنید تا قالب‌های آماده را نمایش دهم:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🏠 بازگشت به منو", callback_data="menu")
            ]])
        )
    
    elif query.data == "use_ai":
        user_states[user_id] = "awaiting_topic_ai"
        await query.message.edit_text(
            "🎯 لطفاً موضوع خود را وارد کنید تا محتوای هوشمند تولید کنم:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🏠 بازگشت به منو", callback_data="menu")
            ]])
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
    
    # Add new state handler for template-based hooks
    elif state == "awaiting_topic_template":
        if user_id not in user_licenses or not user_licenses[user_id]:
            await update.message.reply_text(
                "برای استفاده از این بخش نیاز به لایسنس معتبر دارید.",
                reply_markup=get_main_keyboard(user_id)
            )
            return
            
        context.user_data["current_topic"] = message_text
        user_states[user_id] = "viewing_hooks"
        hook = get_random_hook(user_id, message_text)
        await update.message.reply_text(
            f"✨ قلاب پیشنهادی:\n\n{hook}",
            reply_markup=get_hook_keyboard(user_id)
        )
    
    elif state == "awaiting_topic_ai":
        if user_id not in user_licenses or not user_licenses[user_id]:
            await update.message.reply_text(
                "برای استفاده از این بخش نیاز به لایسنس معتبر دارید.",
                reply_markup=get_main_keyboard(user_id)
            )
            return
            
        # Use the existing AI-based generation
        try:
            await update.message.reply_text("🎯 در حال آماده‌سازی محتوای حرفه‌ای...")
            
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
                        "content": f"لطفاً یک هوک (قلاب) حرفه‌ای و تاثیرگذار برای موضوع {message_text} بنویس. هوک باید کاملاً مرتبط با کسب و کار و حرفه‌ای باشد."
                    }
                ],
                temperature=0.7,
                max_tokens=150
            )
            
            generated_hook = response.choices[0].message.content.strip()
            
            await update.message.reply_text(
                f"✨ هوک پیشنهادی شما:\n\n{generated_hook}",
                reply_markup=get_main_keyboard(user_id)
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