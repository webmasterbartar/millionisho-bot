import os
import json
import logging
from typing import Dict, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ParseMode

from config import (
    TELEGRAM_TOKEN,
    WORDPRESS_BASE_URL
)
from menu_config import (
    MAIN_MENU_BUTTONS,
    TEMPLATE_SUBMENU_BUTTONS,
    NAVIGATION_BUTTONS,
    MESSAGES,
    FREE_LIMITS,
    LOCKED_SECTIONS,
    CONTENT_COUNTS
)
from user_manager import user_manager
from content_manager import content_manager

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    filename='bot.log'
)
logger = logging.getLogger(__name__)

class MillionishoBot:
    def __init__(self):
        """Initialize bot with required handlers"""
        self.application = Application.builder().token(TELEGRAM_TOKEN).build()
        self.current_section = {}
        self.current_action = {}
        self.temp_content = {}
        self.admin_state = {}  # برای نگهداری وضعیت ادمین‌ها
        self._setup_handlers()
        
    def _setup_handlers(self):
        """Setup all necessary command and callback handlers"""
        # Command handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("save", self.save_command))
        
        # Callback handlers for main menu
        self.application.add_handler(CallbackQueryHandler(self.handle_template, pattern="^template$"))
        self.application.add_handler(CallbackQueryHandler(self.handle_reels_idea, pattern="^reels_idea$"))
        self.application.add_handler(CallbackQueryHandler(self.handle_call_to_action, pattern="^call_to_action$"))
        self.application.add_handler(CallbackQueryHandler(self.handle_caption, pattern="^caption$"))
        self.application.add_handler(CallbackQueryHandler(self.handle_complete_idea, pattern="^complete_idea$"))
        self.application.add_handler(CallbackQueryHandler(self.handle_interactive_story, pattern="^interactive_story$"))
        self.application.add_handler(CallbackQueryHandler(self.handle_bio, pattern="^bio$"))
        self.application.add_handler(CallbackQueryHandler(self.handle_roadmap, pattern="^roadmap$"))
        self.application.add_handler(CallbackQueryHandler(self.handle_all_files, pattern="^all_files$"))
        self.application.add_handler(CallbackQueryHandler(self.handle_vip, pattern="^vip$"))
        self.application.add_handler(CallbackQueryHandler(self.handle_favorites, pattern="^favorites$"))
        
        # Navigation handlers
        self.application.add_handler(CallbackQueryHandler(self.handle_next, pattern="^next"))
        self.application.add_handler(CallbackQueryHandler(self.handle_back, pattern="^back"))
        self.application.add_handler(CallbackQueryHandler(self.handle_main_menu, pattern="^main_menu$"))
        
        # Template submenu handlers
        self.application.add_handler(CallbackQueryHandler(self.handle_text_template, pattern="^text_template$"))
        self.application.add_handler(CallbackQueryHandler(self.handle_image_template, pattern="^image_template$"))
        self.application.add_handler(CallbackQueryHandler(self.handle_tutorial, pattern="^tutorial"))
        
        # VIP handlers
        self.application.add_handler(CallbackQueryHandler(self.handle_activation_code, pattern="^activate_code$"))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_activation_input))
        
        # Admin handlers
        self.application.add_handler(CallbackQueryHandler(self.handle_admin_callback, pattern="^admin_"))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text_input))
        self.application.add_handler(MessageHandler(filters.PHOTO, self.handle_photo))
        self.application.add_handler(MessageHandler(filters.VIDEO, self.handle_video))
        self.application.add_handler(MessageHandler(filters.DOCUMENT, self.handle_document))
        
        # Error handler
        self.application.add_error_handler(self.error_handler)
    
    def run(self):
        """Run the bot"""
        self.application.run_polling()

    def get_main_menu_keyboard(self) -> InlineKeyboardMarkup:
        """Create main menu keyboard"""
        keyboard = []
        buttons = list(MAIN_MENU_BUTTONS.items())
        
        # Create rows of 2 buttons each
        for i in range(0, len(buttons), 2):
            row = []
            for key, text in buttons[i:i+2]:
                row.append(InlineKeyboardButton(text, callback_data=key))
            keyboard.append(row)
    
        return InlineKeyboardMarkup(keyboard)

    def get_template_submenu_keyboard(self) -> InlineKeyboardMarkup:
        """Create template submenu keyboard"""
        keyboard = []
        for key, text in TEMPLATE_SUBMENU_BUTTONS.items():
            keyboard.append([InlineKeyboardButton(text, callback_data=key)])
        return InlineKeyboardMarkup(keyboard)

    def get_navigation_keyboard(self, show_tutorial: bool = True) -> InlineKeyboardMarkup:
        """Create navigation keyboard"""
        keyboard = []
        nav_row = []
        
        if "back" in NAVIGATION_BUTTONS:
            nav_row.append(InlineKeyboardButton(NAVIGATION_BUTTONS["back"], callback_data="back"))
        if "next" in NAVIGATION_BUTTONS:
            nav_row.append(InlineKeyboardButton(NAVIGATION_BUTTONS["next"], callback_data="next"))
        
        if nav_row:
            keyboard.append(nav_row)
            
        if show_tutorial:
            keyboard.append([InlineKeyboardButton("توضیحات و آموزش", callback_data="tutorial")])
            
        keyboard.append([InlineKeyboardButton(NAVIGATION_BUTTONS["back_to_main"], callback_data="main_menu")])
        
        return InlineKeyboardMarkup(keyboard)

    async def check_access(self, update: Update, section: str) -> bool:
        """Check if user has access to the section"""
        user_id = str(update.effective_user.id)
        
        # If user is VIP, they have access to everything
        if user_manager.is_vip(user_id):
            return True
            
        # If section is locked for free users, deny access
        if section in LOCKED_SECTIONS:
            await update.callback_query.answer(MESSAGES["vip_only"], show_alert=True)
            return False
            
        # Check usage limits for free sections
        if section in FREE_LIMITS:
            usage_count = user_manager.get_usage_count(user_id, section)
            if usage_count >= FREE_LIMITS[section]:
                await update.callback_query.answer(MESSAGES["free_limit_reached"], show_alert=True)
                return False
                
        return True

    async def send_content(self, update: Update, section: str, index: int) -> None:
        """Send content to user with appropriate format and keyboard"""
        content = content_manager.get_content(section, index)
        if not content:
            await update.callback_query.answer("محتوای مورد نظر یافت نشد", show_alert=True)
            return
            
        section_size = content_manager.get_section_size(section)
        message = f"{content.text}\n\n{index + 1} از {section_size}"
        
        # Handle different media types
        if content.media_path and content.media_type:
            if content.media_type == "photo":
                await update.callback_query.message.reply_photo(
                    photo=content.media_path,
                    caption=message,
                    reply_markup=self.get_navigation_keyboard()
                )
            elif content.media_type == "video":
                await update.callback_query.message.reply_video(
                    video=content.media_path,
                    caption=message,
                    reply_markup=self.get_navigation_keyboard()
                )
            elif content.media_type == "voice":
                await update.callback_query.message.reply_voice(
                    voice=content.media_path,
                    caption=message,
                    reply_markup=self.get_navigation_keyboard()
            )
        else:
            await update.callback_query.message.edit_text(
                text=message,
                reply_markup=self.get_navigation_keyboard(),
                parse_mode=ParseMode.HTML
            )

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle errors"""
        logger.error(f"Exception while handling an update: {context.error}")
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "متأسفانه خطایی رخ داد. لطفاً دوباره تلاش کنید."
            ) 

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command"""
        user_id = str(update.effective_user.id)
        user_manager.init_user(user_id)
        await update.message.reply_text(
            MESSAGES["welcome"],
            reply_markup=self.get_main_menu_keyboard()
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command"""
        await update.message.reply_text(
            "لطفاً دستورات زیر را در اختیار دارید:\n\n"
            "/start - شروع کردن با ربات\n"
            "/help - دریافت دستورات\n"
            "/save - ذخیره محتوای اضافه شده برای ادمین\n\n"
            "برای دسترسی به پنل ادمین، کد فعال‌سازی را وارد کنید."
        )

    async def save_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /save command for admin content"""
        user_id = str(update.effective_user.id)
        if user_id not in ADMIN_IDS:
            return
            
        if await self.save_content(user_id):
            await update.message.reply_text(
                "محتوا با موفقیت ذخیره شد.",
                reply_markup=self.get_main_menu_keyboard()
            )
            # پاک کردن محتوای موقت
            del self.temp_content[user_id]
            if user_id in self.admin_state:
                del self.admin_state[user_id]
        else:
            await update.message.reply_text(
                "متأسفانه در ذخیره محتوا مشکلی پیش آمد. لطفاً دوباره تلاش کنید.",
                reply_markup=self.get_main_menu_keyboard()
            )

    async def handle_template(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle template section"""
        if not await self.check_access(update, "template"):
            return
            
        await update.callback_query.message.edit_text(
            "لطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
            reply_markup=self.get_template_submenu_keyboard()
        )

    async def handle_text_template(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle text template section"""
        user_id = str(update.effective_user.id)
        if not await self.check_access(update, "text_template"):
            return
            
        user_manager.set_current_section(user_id, "text_template")
        index = user_manager.get_current_index(user_id, "text_template")
        await self.send_content(update, "text_template", index)
        user_manager.increment_usage(user_id, "template")

    async def handle_image_template(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle image template section"""
        user_id = str(update.effective_user.id)
        if not await self.check_access(update, "image_template"):
            return
            
        user_manager.set_current_section(user_id, "image_template")
        index = user_manager.get_current_index(user_id, "image_template")
        await self.send_content(update, "image_template", index)
        user_manager.increment_usage(user_id, "template")

    async def handle_tutorial(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle tutorial section"""
        user_id = str(update.effective_user.id)
        current_section = user_manager.get_current_section(user_id)
        
        if not await self.check_access(update, "tutorial"):
            return
            
        tutorial = content_manager.get_tutorial(current_section)
        if tutorial:
            keyboard = [[
                InlineKeyboardButton(NAVIGATION_BUTTONS["back"], callback_data="back"),
                InlineKeyboardButton(NAVIGATION_BUTTONS["back_to_main"], callback_data="main_menu")
            ]]
            
            if tutorial.media_path and tutorial.media_type == "document":
                await update.callback_query.message.reply_document(
                    document=tutorial.media_path,
                    caption=tutorial.text,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                await update.callback_query.message.edit_text(
                    tutorial.text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode=ParseMode.HTML
                )
        else:
            await update.callback_query.answer("محتوای آموزشی در دسترس نیست", show_alert=True)

    async def handle_next(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle next button"""
        user_id = str(update.effective_user.id)
        current_section = user_manager.get_current_section(user_id)
        if not current_section:
            return
            
        current_index = user_manager.get_current_index(user_id, current_section)
        section_size = content_manager.get_section_size(current_section)
        
        next_index = (current_index + 1) % section_size
        user_manager.set_current_index(user_id, current_section, next_index)
        await self.send_content(update, current_section, next_index)

    async def handle_back(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle back button"""
        user_id = str(update.effective_user.id)
        current_section = user_manager.get_current_section(user_id)
        if not current_section:
            return
            
        current_index = user_manager.get_current_index(user_id, current_section)
        section_size = content_manager.get_section_size(current_section)
        
        prev_index = (current_index - 1) % section_size
        user_manager.set_current_index(user_id, current_section, prev_index)
        await self.send_content(update, current_section, prev_index)

    async def handle_main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Return to main menu"""
        await update.callback_query.message.edit_text(
            MESSAGES["welcome"],
            reply_markup=self.get_main_menu_keyboard()
        )

    async def handle_reels_idea(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle reels idea section"""
        user_id = str(update.effective_user.id)
        if not await self.check_access(update, "reels_idea"):
            return
            
        user_manager.set_current_section(user_id, "reels_idea")
        index = user_manager.get_current_index(user_id, "reels_idea")
        await self.send_content(update, "reels_idea", index)
        user_manager.increment_usage(user_id, "reels_idea")

    async def handle_call_to_action(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle call to action section"""
        user_id = str(update.effective_user.id)
        if not await self.check_access(update, "call_to_action"):
            return
            
        user_manager.set_current_section(user_id, "call_to_action")
        index = user_manager.get_current_index(user_id, "call_to_action")
        await self.send_content(update, "call_to_action", index)
        user_manager.increment_usage(user_id, "call_to_action")

    async def handle_caption(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle caption section"""
        user_id = str(update.effective_user.id)
        if not await self.check_access(update, "caption"):
            return
            
        user_manager.set_current_section(user_id, "caption")
        index = user_manager.get_current_index(user_id, "caption")
        await self.send_content(update, "caption", index)
        user_manager.increment_usage(user_id, "caption")

    async def handle_complete_idea(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle complete idea section"""
        user_id = str(update.effective_user.id)
        if not await self.check_access(update, "complete_idea"):
            return
            
        user_manager.set_current_section(user_id, "complete_idea")
        index = user_manager.get_current_index(user_id, "complete_idea")
        await self.send_content(update, "complete_idea", index)

    async def handle_interactive_story(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle interactive story section"""
        user_id = str(update.effective_user.id)
        if not await self.check_access(update, "interactive_story"):
            return
            
        user_manager.set_current_section(user_id, "interactive_story")
        index = user_manager.get_current_index(user_id, "interactive_story")
        await self.send_content(update, "interactive_story", index)
        user_manager.increment_usage(user_id, "interactive_story")

    async def handle_bio(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle bio section"""
        user_id = str(update.effective_user.id)
        if not await self.check_access(update, "bio"):
            return
            
        user_manager.set_current_section(user_id, "bio")
        index = user_manager.get_current_index(user_id, "bio")
        await self.send_content(update, "bio", index)
        user_manager.increment_usage(user_id, "bio")

    async def handle_roadmap(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle roadmap section"""
        if not await self.check_access(update, "roadmap"):
            return
            
        content = content_manager.get_content("roadmap", 0)  # Roadmap is a single content
        if content:
            await update.callback_query.message.edit_text(
                content.text,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(NAVIGATION_BUTTONS["back_to_main"], callback_data="main_menu")
                ]]),
                parse_mode=ParseMode.HTML
            )

    async def handle_all_files(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle all files download section"""
        if not await self.check_access(update, "all_files"):
            return
            
        zip_path = content_manager.get_all_content_zip()
        if zip_path:
            await update.callback_query.message.reply_document(
                document=zip_path,
                caption="تمامی فایل‌های میلیونی‌شو",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(NAVIGATION_BUTTONS["back_to_main"], callback_data="main_menu")
                ]])
            )
        else:
            await update.callback_query.answer("فایل در دسترس نیست", show_alert=True)

    async def handle_vip(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle VIP subscription section"""
        user_id = str(update.effective_user.id)
        
        if user_manager.is_vip(user_id):
            await update.callback_query.message.edit_text(
                MESSAGES["already_subscribed"],
                reply_markup=self.get_main_menu_keyboard()
            )
            return
            
        keyboard = [
            [InlineKeyboardButton("خرید از طریق سایت", url=f"{WORDPRESS_BASE_URL}/vip")],
            [InlineKeyboardButton("خرید از طریق ربات", callback_data="activate_code")],
            [InlineKeyboardButton(NAVIGATION_BUTTONS["back_to_main"], callback_data="main_menu")]
        ]
        
        await update.callback_query.message.edit_text(
            "برای تهیه اشتراک VIP یکی از روش‌های زیر را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def handle_favorites(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle favorites section"""
        user_id = str(update.effective_user.id)
        if not await self.check_access(update, "favorites"):
            return
            
        favorites = user_manager.get_favorites(user_id)
        if not favorites:
            await update.callback_query.message.edit_text(
                "شما هنوز محتوایی را به علاقه‌مندی‌ها اضافه نکرده‌اید.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(NAVIGATION_BUTTONS["back_to_main"], callback_data="main_menu")
                ]])
            )
            return
            
        # Show list of favorites with their sections
        message = "محتوای مورد علاقه شما:\n\n"
        for content_id in favorites:
            section = user_manager.get_current_section(user_id)
            content = content_manager.get_content_by_id(section, content_id)
            if content:
                message += f"- {content.text[:50]}...\n"
        
        await update.callback_query.message.edit_text(
            message,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(NAVIGATION_BUTTONS["back_to_main"], callback_data="main_menu")
            ]]),
            parse_mode=ParseMode.HTML
        )

    async def handle_activation_code(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle activation code entry"""
        await update.callback_query.message.edit_text(
            "لطفاً کد فعال‌سازی خود را وارد کنید:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(NAVIGATION_BUTTONS["back_to_main"], callback_data="main_menu")
            ]])
        )

    async def handle_activation_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle activation code verification"""
        user_id = str(update.effective_user.id)
        activation_code = update.message.text.strip()
        
        # Here you should implement the actual code verification logic
        # For now, we'll just set VIP status
        user_manager.set_vip(user_id, True)
        
        await update.message.reply_text(
            "تبریک! اشتراک VIP شما با موفقیت فعال شد.",
            reply_markup=self.get_main_menu_keyboard()
        )

    async def handle_text_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle text input"""
        user_id = str(update.effective_user.id)
        text = update.message.text

        # دستور مخفی برای دسترسی به پنل مدیریت
        if text == "!admin" and user_id in ADMIN_IDS:
            keyboard = [
                [
                    InlineKeyboardButton("افزودن محتوا", callback_data="admin_add"),
                    InlineKeyboardButton("ویرایش محتوا", callback_data="admin_edit")
                ],
                [
                    InlineKeyboardButton("حذف محتوا", callback_data="admin_delete"),
                    InlineKeyboardButton("مشاهده محتوا", callback_data="admin_view")
                ],
                [InlineKeyboardButton("بازگشت به منو", callback_data="menu")]
            ]
            await update.message.reply_text(
                "🔐 پنل مدیریت محتوا\nلطفاً عملیات مورد نظر را انتخاب کنید:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return

        # پردازش ورودی‌های پنل مدیریت
        if user_id in self.admin_state:
            action, section = self.admin_state[user_id]
            if action == "add_text":
                self.temp_content[user_id] = {"text": text}
                await update.message.reply_text(
                    "متن ذخیره شد. اگر می‌خواهید فایل رسانه‌ای اضافه کنید، آن را ارسال کنید.\n"
                    "در غیر این صورت /save را بزنید."
                )
            elif action == "edit_id":
                try:
                    content_id = int(text)
                    self.temp_content[user_id] = {"id": content_id}
                    self.admin_state[user_id] = ("edit_text", section)
                    await update.message.reply_text("لطفاً متن جدید را وارد کنید:")
                except ValueError:
                    await update.message.reply_text("لطفاً یک شماره معتبر وارد کنید.")
            elif action == "edit_text":
                content_id = self.temp_content[user_id]["id"]
                if await self.edit_content(section, content_id, {"text": text}):
                    await update.message.reply_text(
                        "محتوا با موفقیت ویرایش شد.",
                        reply_markup=self.get_main_menu_keyboard()
                    )
                else:
                    await update.message.reply_text("خطا در ویرایش محتوا")
            elif action == "delete":
                try:
                    content_id = int(text)
                    if await self.delete_content(section, content_id):
                        await update.message.reply_text(
                            "محتوا با موفقیت حذف شد.",
                            reply_markup=self.get_main_menu_keyboard()
                        )
                    else:
                        await update.message.reply_text("خطا در حذف محتوا")
                except ValueError:
                    await update.message.reply_text("لطفاً یک شماره معتبر وارد کنید.")

    async def handle_admin_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle admin panel callbacks"""
        user_id = str(update.effective_user.id)
        if user_id not in ADMIN_IDS:
            return

        query = update.callback_query
        await query.answer()
        
        action = query.data.replace("admin_", "")
        
        if action == "add":
            keyboard = [
                [
                    InlineKeyboardButton("قالب متنی", callback_data="admin_section_text_template"),
                    InlineKeyboardButton("قالب تصویری", callback_data="admin_section_image_template")
                ],
                [
                    InlineKeyboardButton("ایده ریلز", callback_data="admin_section_reels_idea"),
                    InlineKeyboardButton("کال تو اکشن", callback_data="admin_section_call_to_action")
                ],
                [
                    InlineKeyboardButton("کپشن", callback_data="admin_section_caption"),
                    InlineKeyboardButton("بایو", callback_data="admin_section_bio")
                ],
                [InlineKeyboardButton("بازگشت", callback_data="admin_back")]
            ]
            await query.message.edit_text(
                "لطفاً بخش مورد نظر را انتخاب کنید:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        elif action.startswith("section_"):
            section = action.replace("section_", "")
            self.admin_state[user_id] = ("add_text", section)
            await query.message.edit_text("لطفاً متن محتوای جدید را وارد کنید:")
        elif action == "edit":
            keyboard = [
                [
                    InlineKeyboardButton("قالب متنی", callback_data="admin_edit_text_template"),
                    InlineKeyboardButton("قالب تصویری", callback_data="admin_edit_image_template")
                ],
                [
                    InlineKeyboardButton("ایده ریلز", callback_data="admin_edit_reels_idea"),
                    InlineKeyboardButton("کال تو اکشن", callback_data="admin_edit_call_to_action")
                ],
                [
                    InlineKeyboardButton("کپشن", callback_data="admin_edit_caption"),
                    InlineKeyboardButton("بایو", callback_data="admin_edit_bio")
                ],
                [InlineKeyboardButton("بازگشت", callback_data="admin_back")]
            ]
            await query.message.edit_text(
                "لطفاً بخش مورد نظر را انتخاب کنید:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        elif action.startswith("edit_"):
            section = action.replace("edit_", "")
            self.admin_state[user_id] = ("edit_id", section)
            await query.message.edit_text("لطفاً شماره محتوای مورد نظر را وارد کنید:")
        elif action == "delete":
            keyboard = [
                [
                    InlineKeyboardButton("قالب متنی", callback_data="admin_delete_text_template"),
                    InlineKeyboardButton("قالب تصویری", callback_data="admin_delete_image_template")
                ],
                [
                    InlineKeyboardButton("ایده ریلز", callback_data="admin_delete_reels_idea"),
                    InlineKeyboardButton("کال تو اکشن", callback_data="admin_delete_call_to_action")
                ],
                [
                    InlineKeyboardButton("کپشن", callback_data="admin_delete_caption"),
                    InlineKeyboardButton("بایو", callback_data="admin_delete_bio")
                ],
                [InlineKeyboardButton("بازگشت", callback_data="admin_back")]
            ]
            await query.message.edit_text(
                "لطفاً بخش مورد نظر را انتخاب کنید:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        elif action.startswith("delete_"):
            section = action.replace("delete_", "")
            self.admin_state[user_id] = ("delete", section)
            await query.message.edit_text("لطفاً شماره محتوای مورد نظر را وارد کنید:")
        elif action == "view":
            keyboard = [
                [
                    InlineKeyboardButton("قالب متنی", callback_data="admin_view_text_template"),
                    InlineKeyboardButton("قالب تصویری", callback_data="admin_view_image_template")
                ],
                [
                    InlineKeyboardButton("ایده ریلز", callback_data="admin_view_reels_idea"),
                    InlineKeyboardButton("کال تو اکشن", callback_data="admin_view_call_to_action")
                ],
                [
                    InlineKeyboardButton("کپشن", callback_data="admin_view_caption"),
                    InlineKeyboardButton("بایو", callback_data="admin_view_bio")
                ],
                [InlineKeyboardButton("بازگشت", callback_data="admin_back")]
            ]
            await query.message.edit_text(
                "لطفاً بخش مورد نظر را انتخاب کنید:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        elif action.startswith("view_"):
            section = action.replace("view_", "")
            await self.show_admin_content(query.message, section)
        elif action == "back":
            keyboard = [
                [
                    InlineKeyboardButton("افزودن محتوا", callback_data="admin_add"),
                    InlineKeyboardButton("ویرایش محتوا", callback_data="admin_edit")
                ],
                [
                    InlineKeyboardButton("حذف محتوا", callback_data="admin_delete"),
                    InlineKeyboardButton("مشاهده محتوا", callback_data="admin_view")
                ],
                [InlineKeyboardButton("بازگشت به منو", callback_data="menu")]
            ]
            await query.message.edit_text(
                "🔐 پنل مدیریت محتوا\nلطفاً عملیات مورد نظر را انتخاب کنید:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

    async def show_admin_content(self, message, section: str) -> None:
        """Show content for admin"""
        try:
            with open(f"content/{section}.json", "r", encoding="utf-8") as f:
                content = json.load(f)
                text = f"محتوای بخش {section}:\n\n"
                for item in content:
                    text += f"🔹 شماره {item['id']}:\n{item['text'][:100]}...\n\n"
                
                keyboard = [[InlineKeyboardButton("بازگشت", callback_data="admin_back")]]
                await message.edit_text(
                    text,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
        except FileNotFoundError:
            await message.edit_text(
                f"محتوایی برای بخش {section} یافت نشد.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("بازگشت", callback_data="admin_back")
                ]])
            )

    async def save_media_file(self, file_id: str, section: str, media_type: str) -> str:
        """Save media file to appropriate directory"""
        file = await self.application.bot.get_file(file_id)
        
        # تعیین پسوند فایل بر اساس نوع
        if media_type == "photo":
            ext = ".jpg"
            dir_name = "images"
        elif media_type == "video":
            ext = ".mp4"
            dir_name = "videos"
        else:
            ext = ""  # پسوند اصلی فایل حفظ می‌شود
            dir_name = "docs"
            
        # ایجاد دایرکتوری اگر وجود ندارد
        os.makedirs(f"content/{dir_name}", exist_ok=True)
        
        # ایجاد نام فایل یکتا
        filename = f"{section}_{file_id}{ext}"
        filepath = f"content/{dir_name}/{filename}"
        
        # دانلود و ذخیره فایل
        await file.download_to_drive(filepath)
        return filepath

    async def save_content(self, user_id: str) -> bool:
        """Save content to JSON file"""
        if user_id not in self.temp_content:
            return False
            
        section = self.admin_state[user_id][1]
        content = self.temp_content[user_id]
        filepath = f"content/{section}.json"
        
        try:
            # خواندن محتوای فعلی
            if os.path.exists(filepath):
                with open(filepath, "r", encoding="utf-8") as f:
                    current_content = json.load(f)
                # تعیین شناسه جدید
                new_id = max([int(item["id"]) for item in current_content]) + 1
            else:
                current_content = []
                new_id = 1
                
            # اگر فایل رسانه وجود دارد، آن را ذخیره می‌کنیم
            if "media_type" in content and "media_path" in content:
                media_path = await self.save_media_file(
                    content["media_path"],
                    section,
                    content["media_type"]
                )
                content["media_path"] = media_path
                
            # افزودن محتوای جدید
            content["id"] = str(new_id)
            current_content.append(content)
            
            # ذخیره فایل JSON
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(current_content, f, ensure_ascii=False, indent=4)
                
            return True
            
        except Exception as e:
            logger.error(f"Error saving content: {e}")
            return False

    async def edit_content(self, section: str, content_id: int, new_content: dict) -> bool:
        """Edit existing content"""
        filepath = f"content/{section}.json"
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = json.load(f)
                
            # پیدا کردن محتوای مورد نظر
            for i, item in enumerate(content):
                if item["id"] == str(content_id):
                    # به‌روزرسانی محتوا
                    content[i].update(new_content)
                    break
            else:
                return False
                
            # ذخیره تغییرات
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(content, f, ensure_ascii=False, indent=4)
                
            return True
            
        except Exception as e:
            logger.error(f"Error editing content: {e}")
            return False

    async def delete_content(self, section: str, content_id: int) -> bool:
        """Delete content"""
        filepath = f"content/{section}.json"
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = json.load(f)
                
            # حذف محتوای مورد نظر
            content = [item for item in content if item["id"] != str(content_id)]
            
            # ذخیره تغییرات
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(content, f, ensure_ascii=False, indent=4)
                
            return True
            
        except Exception as e:
            logger.error(f"Error deleting content: {e}")
            return False

# Create bot instance
bot = MillionishoBot()

if __name__ == "__main__":
    bot.run() 