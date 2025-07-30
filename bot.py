import os
import json
import logging
from typing import Dict, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo, ForceReply
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ParseMode
import aiohttp

from config import (
    TELEGRAM_TOKEN,
    WORDPRESS_BASE_URL,
    ADMIN_IDS,
    DEBUG
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

# Configure logging with more detail
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG if DEBUG else logging.INFO,
    filename='bot.log'
)
logger = logging.getLogger(__name__)

# Add a console handler for immediate feedback
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG if DEBUG else logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

class MillionishoBot:
    def __init__(self):
        """Initialize bot with required handlers"""
        logger.info("Initializing MillionishoBot")
        self.application = Application.builder().token(TELEGRAM_TOKEN).build()
        self.current_section = {}
        self.current_action = {}
        self.temp_content = {}
        self.admin_state = {}
        self._setup_handlers()
        
    def _setup_handlers(self):
        """Setup all necessary command and callback handlers"""
        logger.info("Setting up message handlers")
        
        # Command handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("save", self.save_command))
        
        # Text handler for admin command
        self.application.add_handler(MessageHandler(
            filters.TEXT & filters.Regex("^!admin$"),
            self.handle_admin_command
        ))
        
        # General text handler
        self.application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            self.handle_text_input
        ))
        
        # Media handlers
        self.application.add_handler(MessageHandler(filters.PHOTO, self.handle_photo))
        self.application.add_handler(MessageHandler(filters.VIDEO, self.handle_video))
        self.application.add_handler(MessageHandler(filters.Document.ALL, self.handle_document))
        
        # Callback handlers
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))
        
        # Error handler
        self.application.add_error_handler(self.error_handler)
    
        logger.info("All handlers have been set up")

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Central callback handler"""
        user_id = str(update.effective_user.id)
        callback_data = update.callback_query.data
        logger.info(f"Callback received - user_id: {user_id}, data: {callback_data}")

        try:
            # Admin callbacks
            if callback_data.startswith("admin_"):
                await self.handle_admin_callback(update, context)
                return

            # Direct matches
            direct_handlers = {
                "template": self.handle_template,
                "text_template": self.handle_text_template,
                "image_template": self.handle_image_template,
                "tutorial": self.handle_tutorial,
                "next": self.handle_next,
                "back": self.handle_back,
                "main_menu": self.handle_main_menu,
                "reels_idea": self.handle_reels_idea,
                "call_to_action": self.handle_call_to_action,
                "caption": self.handle_caption,
                "complete_idea": self.handle_complete_idea,
                "interactive_story": self.handle_interactive_story,
                "bio": self.handle_bio,
                "roadmap": self.handle_roadmap,
                "all_files": self.handle_all_files,
                "vip": self.handle_vip,
                "favorites": self.handle_favorites,
            }

            if callback_data in direct_handlers:
                logger.info(f"Handling callback '{callback_data}' for user {user_id}")
                await direct_handlers[callback_data](update, context)
                await update.callback_query.answer()
                return

            logger.warning(f"Unhandled callback data: {callback_data}")
            await update.callback_query.answer("این گزینه در حال حاضر در دسترس نیست.", show_alert=True)

        except Exception as e:
            logger.error(f"Error in callback handler - user: {user_id}, callback: {callback_data}, error: {str(e)}")
            await update.callback_query.answer("خطایی رخ داد. لطفاً دوباره تلاش کنید.", show_alert=True)

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

    async def send_content(self, update: Update, section: str, index: int, edit_message: bool = True) -> None:
        """Send content to user with appropriate format and keyboard"""
        user_id = str(update.effective_user.id)
        logger.info(f"Sending content - user: {user_id}, section: {section}, index: {index}")
        
        try:
            # Get content
            content = content_manager.get_content(section, index)
            if not content:
                logger.error(f"Content not found - section: {section}, index: {index}")
                await update.callback_query.answer("محتوای مورد نظر یافت نشد", show_alert=True)
                return

            # Get section size and prepare message
            section_size = content_manager.get_section_size(section)
            message = f"{content.text}\n\n{index + 1} از {section_size}"
            keyboard = self.get_navigation_keyboard()

            # Handle media content
            if content.media_path and content.media_type:
                try:
                    if edit_message:
                        if content.media_type == "photo":
                            await update.callback_query.message.edit_media(
                                media=InputMediaPhoto(content.media_path, caption=message),
                                reply_markup=keyboard
                            )
                        elif content.media_type == "video":
                            await update.callback_query.message.edit_media(
                                media=InputMediaVideo(content.media_path, caption=message),
                                reply_markup=keyboard
                            )
                    else:
                        if content.media_type == "photo":
                            await update.callback_query.message.reply_photo(
                                photo=content.media_path,
                                caption=message,
                                reply_markup=keyboard
                            )
                        elif content.media_type == "video":
                            await update.callback_query.message.reply_video(
                                video=content.media_path,
                                caption=message,
                                reply_markup=keyboard
                            )
                except Exception as e:
                    logger.error(f"Error sending media content: {str(e)}")
                    # Fallback to text-only if media fails
                    await update.callback_query.message.edit_text(
                        text=message,
                        reply_markup=keyboard,
                        parse_mode=ParseMode.HTML
                    )
            else:
                # Text-only content
                if edit_message:
                    await update.callback_query.message.edit_text(
                        text=message,
                        reply_markup=keyboard,
                        parse_mode=ParseMode.HTML
                    )
                else:
                    await update.callback_query.message.reply_text(
                        text=message,
                        reply_markup=keyboard,
                        parse_mode=ParseMode.HTML
                    )

            logger.info(f"Content sent successfully - user: {user_id}, section: {section}, index: {index}")
            
        except Exception as e:
            logger.error(f"Error in send_content - user: {user_id}, error: {str(e)}")
            await update.callback_query.answer(
                "خطا در نمایش محتوا. لطفاً به منوی اصلی برگردید و دوباره تلاش کنید.",
                show_alert=True
            )

    async def handle_section_content(self, update: Update, context: ContextTypes.DEFAULT_TYPE, section: str) -> None:
        """Generic handler for all content sections"""
        user_id = str(update.effective_user.id)
        logger.info(f"Section {section} accessed by user {user_id}")
        
        try:
            if not await self.check_access(update, section):
                logger.warning(f"Access denied to section {section} for user {user_id}")
                return

            # Initialize user state
            user_manager.set_current_section(user_id, section)
            index = user_manager.get_current_index(user_id, section)
            
            # Send content
            await self.send_content(update, section, index)
            
            # Update usage statistics
            if section in FREE_LIMITS:
                user_manager.increment_usage(user_id, section)
                logger.info(f"Usage incremented for section {section} - user: {user_id}")
                
        except Exception as e:
            logger.error(f"Error in handle_section_content - user: {user_id}, section: {section}, error: {str(e)}")
            await update.callback_query.answer(
                "خطا در دسترسی به محتوا. لطفاً دوباره تلاش کنید.",
                show_alert=True
            )

    async def handle_next(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle next button"""
        user_id = str(update.effective_user.id)
        logger.info(f"Next button pressed by user {user_id}")
        
        try:
            current_section = user_manager.get_current_section(user_id)
            if not current_section:
                logger.warning(f"No current section found for user {user_id}")
                await update.callback_query.answer(
                    "لطفاً ابتدا یک بخش را انتخاب کنید.",
                    show_alert=True
                )
                return

            current_index = user_manager.get_current_index(user_id, current_section)
            section_size = content_manager.get_section_size(current_section)
            
            if section_size == 0:
                logger.error(f"No content found in section {current_section}")
                await update.callback_query.answer(
                    "محتوایی در این بخش وجود ندارد.",
                    show_alert=True
                )
                return

            next_index = (current_index + 1) % section_size
            user_manager.set_current_index(user_id, current_section, next_index)
            
            await self.send_content(update, current_section, next_index)
            logger.info(f"Next content displayed - user: {user_id}, section: {current_section}, index: {next_index}")
            
        except Exception as e:
            logger.error(f"Error in handle_next - user: {user_id}, error: {str(e)}")
            await update.callback_query.answer(
                "خطا در نمایش محتوای بعدی. لطفاً به منوی اصلی برگردید و دوباره تلاش کنید.",
                show_alert=True
            )

    async def handle_back(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle back button"""
        user_id = str(update.effective_user.id)
        logger.info(f"Back button pressed by user {user_id}")
        
        try:
            current_section = user_manager.get_current_section(user_id)
            if not current_section:
                logger.warning(f"No current section found for user {user_id}")
                await update.callback_query.answer(
                    "لطفاً ابتدا یک بخش را انتخاب کنید.",
                    show_alert=True
                )
                return

            current_index = user_manager.get_current_index(user_id, current_section)
            section_size = content_manager.get_section_size(current_section)
            
            if section_size == 0:
                logger.error(f"No content found in section {current_section}")
                await update.callback_query.answer(
                    "محتوایی در این بخش وجود ندارد.",
                    show_alert=True
                )
                return

            prev_index = (current_index - 1) % section_size
            user_manager.set_current_index(user_id, current_section, prev_index)
            
            await self.send_content(update, current_section, prev_index)
            logger.info(f"Previous content displayed - user: {user_id}, section: {current_section}, index: {prev_index}")
            
        except Exception as e:
            logger.error(f"Error in handle_back - user: {user_id}, error: {str(e)}")
            await update.callback_query.answer(
                "خطا در نمایش محتوای قبلی. لطفاً به منوی اصلی برگردید و دوباره تلاش کنید.",
                show_alert=True
            )

    async def handle_main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Return to main menu"""
        user_id = str(update.effective_user.id)
        logger.info(f"User {user_id} returning to main menu")
        try:
            await update.callback_query.message.edit_text(
                MESSAGES["welcome"],
                reply_markup=self.get_main_menu_keyboard(),
                parse_mode=ParseMode.HTML
            )
            logger.info(f"Main menu displayed for user {user_id}")
        except Exception as e:
            logger.error(f"Error showing main menu - user: {user_id}, error: {str(e)}")
            await update.callback_query.answer("خطا در نمایش منو. لطفاً دوباره تلاش کنید.", show_alert=True)

    async def handle_reels_idea(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle reels idea section"""
        await self.handle_section_content(update, context, "reels_idea")

    async def handle_call_to_action(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle call to action section"""
        await self.handle_section_content(update, context, "call_to_action")

    async def handle_caption(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle caption section"""
        await self.handle_section_content(update, context, "caption")

    async def handle_complete_idea(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle complete idea section"""
        await self.handle_section_content(update, context, "complete_idea")

    async def handle_interactive_story(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle interactive story section"""
        await self.handle_section_content(update, context, "interactive_story")

    async def handle_bio(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle bio section"""
        await self.handle_section_content(update, context, "bio")

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

    async def save_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /save command - saves admin content"""
        user_id = str(update.effective_user.id)
        if str(user_id) not in [str(admin_id) for admin_id in ADMIN_IDS]:
            await update.message.reply_text("این دستور فقط برای ادمین‌ها در دسترس است.")
            return
            
        if not self.temp_content.get(user_id):
            await update.message.reply_text("محتوایی برای ذخیره وجود ندارد.")
            return
            
        content = self.temp_content[user_id]
        section = self.current_section.get(user_id)
        if not section:
            await update.message.reply_text("لطفاً ابتدا بخش مورد نظر را انتخاب کنید.")
            return
            
        content_manager.add_content(section, content)
        self.temp_content.pop(user_id)
        await update.message.reply_text("محتوا با موفقیت ذخیره شد.")

    async def handle_activation_code(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /activate command"""
        await update.message.reply_text(
            "لطفاً کد لایسنس خود را وارد کنید:",
            reply_markup=ForceReply()
        )

    async def handle_activation_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle license key input"""
        user_id = update.message.from_user.id
        license_key = update.message.text.strip()
        
        # Verify license with WordPress site
        async with aiohttp.ClientSession() as session:
            try:
                params = {'key': license_key}
                async with session.get('https://millionisho.com/wp-json/licensing/v1/verify', params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('status') == 'valid':
                            # Activate VIP status
                            user_manager.activate_vip(user_id)
                            await update.message.reply_text(
                                "✅ کد لایسنس شما با موفقیت فعال شد!\n"
                                "اکنون می‌توانید به تمام محتوا دسترسی داشته باشید."
                            )
                            return
                
                await update.message.reply_text(
                    "❌ کد لایسنس نامعتبر است.\n"
                    "لطفاً از صحت کد وارد شده اطمینان حاصل کنید."
                )
            except Exception as e:
                logging.error(f"Error verifying license: {e}")
                await update.message.reply_text(
                    "❌ خطا در بررسی کد لایسنس.\n"
                    "لطفاً دوباره تلاش کنید."
                )

    async def handle_admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle !admin command"""
        user_id = str(update.effective_user.id)
        logger.info(f"Admin command received from user {user_id}")
        
        # Clear any existing state
        self.admin_state.pop(user_id, None)
        self.current_section.pop(user_id, None)
        self.temp_content.pop(user_id, None)
        
        if str(user_id) not in [str(admin_id) for admin_id in ADMIN_IDS]:
            logger.warning(f"Unauthorized admin access attempt from user {user_id}")
            await update.message.reply_text("شما دسترسی به پنل ادمین ندارید.")
            return
            
        keyboard = [
            [InlineKeyboardButton("افزودن محتوا", callback_data="admin_add_content")],
            [InlineKeyboardButton("مشاهده آمار", callback_data="admin_stats")],
            [InlineKeyboardButton("بازگشت به منوی اصلی", callback_data="main_menu")]
        ]
        
        await update.message.reply_text(
            "به پنل مدیریت خوش آمدید. لطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        logger.info(f"Admin panel opened for user {user_id}")

    async def handle_admin_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle admin panel callbacks"""
        user_id = str(update.effective_user.id)
        logger.info(f"Admin callback received from user {user_id}")
        
        if str(user_id) not in [str(admin_id) for admin_id in ADMIN_IDS]:
            logger.warning(f"Unauthorized admin callback from user {user_id}")
            await update.callback_query.answer("شما دسترسی به پنل ادمین ندارید.", show_alert=True)
            return
            
        callback_data = update.callback_query.data
        logger.info(f"Callback data: {callback_data}")
        
        if callback_data == "admin_add_content":
            # Clear any existing state
            self.admin_state.pop(user_id, None)
            self.current_section.pop(user_id, None)
            self.temp_content.pop(user_id, None)
            
            self.admin_state[user_id] = "waiting_for_section"
            sections = list(CONTENT_COUNTS.keys())
            keyboard = []
            for section in sections:
                keyboard.append([InlineKeyboardButton(section, callback_data=f"admin_section_{section}")])
            keyboard.append([InlineKeyboardButton("بازگشت", callback_data="admin_back")])
            await update.callback_query.message.edit_text(
                "لطفاً بخش مورد نظر را انتخاب کنید:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            logger.info(f"Content sections shown to user {user_id}")
            
        elif callback_data == "admin_stats":
            # Get statistics for each section
            stats = "📊 آمار استفاده از بخش‌های مختلف:\n\n"
            total_users = len(user_manager.users)
            vip_users = sum(1 for user in user_manager.users.values() if user.get("is_vip", False))
            
            stats += f"👥 تعداد کل کاربران: {total_users}\n"
            stats += f"💎 تعداد کاربران VIP: {vip_users}\n\n"
            stats += "📈 تعداد محتوا در هر بخش:\n"
            
            for section, count in CONTENT_COUNTS.items():
                stats += f"- {section}: {count}\n"
            
            keyboard = [[InlineKeyboardButton("بازگشت", callback_data="admin_back")]]
            await update.callback_query.message.edit_text(
                stats,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            logger.info(f"Stats shown to user {user_id}")
            
        elif callback_data.startswith("admin_section_"):
            section = callback_data.replace("admin_section_", "")
            self.current_section[user_id] = section
            self.admin_state[user_id] = "waiting_for_content"
            logger.info(f"Section {section} selected by user {user_id}")
            
            await update.callback_query.message.edit_text(
                f"لطفاً محتوای جدید برای بخش {section} را ارسال کنید.\n"
                "می‌توانید متن، عکس، ویدیو یا فایل ارسال کنید.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("انصراف", callback_data="admin_back")
                ]])
            )
            
        elif callback_data == "admin_add_media":
            self.admin_state[user_id] = "waiting_for_media"
            logger.info(f"Waiting for media from user {user_id}")
            await update.callback_query.message.edit_text(
                "لطفاً رسانه مورد نظر (عکس/ویدیو/فایل) را ارسال کنید.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("انصراف", callback_data="admin_back")
                ]])
            )
            
        elif callback_data == "admin_save_content":
            if user_id not in self.temp_content:
                logger.warning(f"No content to save for user {user_id}")
                await update.callback_query.answer("خطا: محتوایی برای ذخیره وجود ندارد.", show_alert=True)
                return
                
            section = self.current_section.get(user_id)
            if not section:
                logger.warning(f"No section selected for user {user_id}")
                await update.callback_query.answer("خطا: بخش مورد نظر یافت نشد.", show_alert=True)
                return
                
            content = self.temp_content[user_id]
            logger.info(f"Saving content for user {user_id} in section {section}: {content}")
            content_manager.add_content(section, content)
            
            # پاکسازی وضعیت
            self.temp_content.pop(user_id, None)
            self.current_section.pop(user_id, None)
            self.admin_state.pop(user_id, None)
            
            await update.callback_query.message.edit_text(
                "✅ محتوا با موفقیت ذخیره شد.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("بازگشت به پنل ادمین", callback_data="admin_back")
                ]])
            )
            logger.info(f"Content saved successfully for user {user_id}")
            
        elif callback_data == "admin_back":
            # پاکسازی وضعیت
            self.temp_content.pop(user_id, None)
            self.current_section.pop(user_id, None)
            self.admin_state.pop(user_id, None)
            
            keyboard = [
                [InlineKeyboardButton("افزودن محتوا", callback_data="admin_add_content")],
                [InlineKeyboardButton("مشاهده آمار", callback_data="admin_stats")],
                [InlineKeyboardButton("بازگشت به منوی اصلی", callback_data="main_menu")]
            ]
            await update.callback_query.message.edit_text(
                "به پنل مدیریت خوش آمدید. لطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            logger.info(f"User {user_id} returned to admin panel")

    async def handle_text_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle text input for admin content addition"""
        user_id = str(update.effective_user.id)
        text = update.message.text
        logger.debug(f"Text input received - user_id: {user_id}, text: {text}")

        # Skip if not admin
        if str(user_id) not in [str(admin_id) for admin_id in ADMIN_IDS]:
            logger.debug(f"Non-admin text input ignored - user_id: {user_id}")
            return

        # Skip if not in admin mode
        if user_id not in self.admin_state:
            logger.debug(f"Text input ignored (not in admin mode) - user_id: {user_id}")
            return

        state = self.admin_state[user_id]
        logger.debug(f"Processing text input - user_id: {user_id}, state: {state}")

        if state == "waiting_for_content":
            section = self.current_section.get(user_id)
            if not section:
                logger.warning(f"No section selected - user_id: {user_id}")
                await update.message.reply_text(
                    "خطا: بخش مورد نظر یافت نشد. لطفاً دوباره از منوی ادمین شروع کنید.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("بازگشت به منوی ادمین", callback_data="admin_back")
                    ]])
                )
                return

            # Store the text content
            if user_id not in self.temp_content:
                self.temp_content[user_id] = {}
            
            self.temp_content[user_id]["text"] = text
            logger.debug(f"Text content stored - user_id: {user_id}, section: {section}")

            # Show appropriate options
            keyboard = [
                [InlineKeyboardButton("بله، می‌خواهم رسانه اضافه کنم", callback_data="admin_add_media")],
                [InlineKeyboardButton("خیر، همین متن ذخیره شود", callback_data="admin_save_content")],
                [InlineKeyboardButton("انصراف", callback_data="admin_back")]
            ]

            try:
                await update.message.reply_text(
                    f"متن دریافت شد:\n\n{text}\n\nآیا می‌خواهید رسانه‌ای (عکس/ویدیو/فایل) هم اضافه کنید؟",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                logger.debug(f"Options message sent - user_id: {user_id}")
            except Exception as e:
                logger.error(f"Error sending options message - user_id: {user_id}, error: {str(e)}")
                await update.message.reply_text("خطا در ارسال پیام. لطفاً دوباره تلاش کنید.")

    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle photo upload for admin content"""
        user_id = str(update.effective_user.id)
        logger.info(f"Photo received from user {user_id}")
        
        if str(user_id) not in [str(admin_id) for admin_id in ADMIN_IDS] or user_id not in self.admin_state:
            logger.warning(f"Unauthorized photo upload attempt from user {user_id}")
            return
            
        state = self.admin_state.get(user_id)
        logger.info(f"User {user_id} state: {state}")
        
        if state in ["waiting_for_media", "waiting_for_content"]:
            photo = update.message.photo[-1]  # Get the largest photo size
            file_id = photo.file_id
            
            if user_id not in self.temp_content:
                self.temp_content[user_id] = {}
            
            self.temp_content[user_id].update({
                "media_type": "photo",
                "media_path": file_id
            })
            
            # If we don't have text content yet, wait for it
            if "text" not in self.temp_content[user_id]:
                await update.message.reply_text(
                    "عکس دریافت شد. حالا لطفاً متن مربوط به این محتوا را ارسال کنید:",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("انصراف", callback_data="admin_back")
                    ]])
                )
                self.admin_state[user_id] = "waiting_for_content"
            else:
                # We have both text and photo, show save option
                keyboard = [
                    [InlineKeyboardButton("ذخیره", callback_data="admin_save_content")],
                    [InlineKeyboardButton("انصراف", callback_data="admin_back")]
                ]
                await update.message.reply_text(
                    f"عکس دریافت شد. محتوای کامل:\n\n"
                    f"📝 متن: {self.temp_content[user_id]['text']}\n"
                    f"🖼 عکس: دریافت شد\n\n"
                    "آیا می‌خواهید این محتوا ذخیره شود؟",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                self.admin_state[user_id] = "waiting_for_save_confirmation"
            
            logger.info(f"Photo processed for user {user_id}, temp_content: {self.temp_content[user_id]}")
        else:
            logger.warning(f"Photo received in invalid state from user {user_id}")
            await update.message.reply_text(
                "لطفاً ابتدا از منوی ادمین، بخش مورد نظر را انتخاب کنید.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("بازگشت به منوی ادمین", callback_data="admin_back")
                ]])
            )

    async def handle_video(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle video upload for admin content"""
        user_id = str(update.effective_user.id)
        if str(user_id) not in [str(admin_id) for admin_id in ADMIN_IDS] or user_id not in self.admin_state:
            return
            
        if self.admin_state[user_id] == "waiting_for_media":
            video = update.message.video
            file_id = video.file_id
            self.temp_content[user_id]["media_type"] = "video"
            self.temp_content[user_id]["media_path"] = file_id
            await update.message.reply_text(
                "ویدیو دریافت شد. برای ذخیره محتوا از دستور /save استفاده کنید."
            )

    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle document upload for admin content"""
        user_id = str(update.effective_user.id)
        if str(user_id) not in [str(admin_id) for admin_id in ADMIN_IDS] or user_id not in self.admin_state:
            return
            
        if self.admin_state[user_id] == "waiting_for_media":
            document = update.message.document
            file_id = document.file_id
            self.temp_content[user_id]["media_type"] = "document"
            self.temp_content[user_id]["media_path"] = file_id
            await update.message.reply_text(
                "فایل دریافت شد. برای ذخیره محتوا از دستور /save استفاده کنید."
            )

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle errors"""
        logger.error(f"Error occurred: {context.error}")
        try:
            if update and update.effective_message:
                await update.effective_message.reply_text(
                    "متأسفانه خطایی رخ داد. لطفاً مجدداً تلاش کنید."
                )
        except Exception as e:
            logger.error(f"Error in error handler: {e}")

    def run(self) -> None:
        """Run the bot"""
        app = Application.builder().token(TELEGRAM_TOKEN).build()

        # Add handlers
        app.add_handler(CommandHandler("start", self.start_command))
        app.add_handler(CommandHandler("help", self.help_command))
        app.add_handler(CommandHandler("activate", self.handle_activation_code))
        
        # Add message handlers
        app.add_handler(MessageHandler(
            filters.TEXT & filters.REPLY & ~filters.COMMAND,
            self.handle_activation_input
        ))
        
        # Command handlers
        app.add_handler(CommandHandler("start", self.start_command))
        app.add_handler(CommandHandler("help", self.help_command))
        app.add_handler(CommandHandler("save", self.save_command))
        
        # Text handler for admin command
        app.add_handler(MessageHandler(
            filters.TEXT & filters.Regex("^!admin$"),
            self.handle_admin_command
        ))
        
        # General text handler
        app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            self.handle_text_input
        ))
        
        # Media handlers
        app.add_handler(MessageHandler(filters.PHOTO, self.handle_photo))
        app.add_handler(MessageHandler(filters.VIDEO, self.handle_video))
        app.add_handler(MessageHandler(filters.Document.ALL, self.handle_document))
        
        # Callback handlers
        app.add_handler(CallbackQueryHandler(self.handle_callback))
        
        # Error handler
        app.add_error_handler(self.error_handler)
    
        logger.info("All handlers have been set up")

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

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command"""
        user_id = str(update.effective_user.id)
        logger.info(f"Start command received from user {user_id}")
        
        try:
            user_manager.init_user(user_id)
            await update.message.reply_text(
                MESSAGES["welcome"],
                reply_markup=self.get_main_menu_keyboard(),
                parse_mode=ParseMode.HTML
            )
            logger.info(f"Welcome message sent to user {user_id}")
        except Exception as e:
            logger.error(f"Error in start_command - user: {user_id}, error: {str(e)}")
            await update.message.reply_text("خطا در شروع ربات. لطفاً دوباره تلاش کنید.")

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command"""
        user_id = str(update.effective_user.id)
        logger.info(f"Help command received from user {user_id}")
        
        try:
            await update.message.reply_text(
                "لطفاً دستورات زیر را در اختیار دارید:\n\n"
                "/start - شروع کردن با ربات\n"
                "/help - دریافت دستورات\n"
                "/save - ذخیره محتوای اضافه شده برای ادمین\n\n"
                "برای دسترسی به پنل ادمین، دستور !admin را ارسال کنید.",
                parse_mode=ParseMode.HTML
            )
            logger.info(f"Help message sent to user {user_id}")
        except Exception as e:
            logger.error(f"Error in help_command - user: {user_id}, error: {str(e)}")
            await update.message.reply_text("خطا در نمایش راهنما. لطفاً دوباره تلاش کنید.")

    async def handle_template(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle template section"""
        user_id = str(update.effective_user.id)
        logger.info(f"Template section accessed by user {user_id}")
        
        try:
            if not await self.check_access(update, "template"):
                logger.warning(f"Access denied to template section for user {user_id}")
                return
                
            await update.callback_query.message.edit_text(
                "لطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
                reply_markup=self.get_template_submenu_keyboard(),
                parse_mode=ParseMode.HTML
            )
            logger.info(f"Template submenu displayed for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error in handle_template - user: {user_id}, error: {str(e)}")
            await update.callback_query.answer("خطا در نمایش منو. لطفاً دوباره تلاش کنید.", show_alert=True)

    async def handle_text_template(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle text template section"""
        await self.handle_section_content(update, context, "text_template")
        if await self.check_access(update, "text_template"):
            user_manager.increment_usage(str(update.effective_user.id), "template")

    async def handle_image_template(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle image template section"""
        await self.handle_section_content(update, context, "image_template")
        if await self.check_access(update, "image_template"):
            user_manager.increment_usage(str(update.effective_user.id), "template")

    async def handle_tutorial(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle tutorial section"""
        user_id = str(update.effective_user.id)
        logger.info(f"Tutorial section accessed by user {user_id}")
        
        try:
            current_section = user_manager.get_current_section(user_id)
            if not current_section:
                logger.warning(f"No current section found for tutorial - user: {user_id}")
                await update.callback_query.answer("لطفاً ابتدا یک بخش را انتخاب کنید.", show_alert=True)
                return
            
            if not await self.check_access(update, "tutorial"):
                logger.warning(f"Access denied to tutorial section for user {user_id}")
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
                logger.info(f"Tutorial content sent for section {current_section} - user: {user_id}")
            else:
                logger.warning(f"No tutorial content found for section {current_section}")
                await update.callback_query.answer("محتوای آموزشی در دسترس نیست", show_alert=True)
                
        except Exception as e:
            logger.error(f"Error in handle_tutorial - user: {user_id}, error: {str(e)}")
            await update.callback_query.answer("خطا در نمایش آموزش. لطفاً دوباره تلاش کنید.", show_alert=True)

if __name__ == "__main__":
    # Create and run bot
    bot = MillionishoBot()
    bot.run() 