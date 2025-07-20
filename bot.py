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
    WORDPRESS_BASE_URL,
    ADMIN_IDS
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
        
        # Media handlers
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
            "برای دسترسی به پنل ادمین، دستور !admin را ارسال کنید."
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