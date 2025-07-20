import os
import json
import logging
from typing import Dict, Optional
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

# تنظیمات لاگینگ
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    filename='admin_bot.log'
)
logger = logging.getLogger(__name__)

# توکن ربات ادمین - این را باید با توکن واقعی جایگزین کنید
ADMIN_BOT_TOKEN = "YOUR_ADMIN_BOT_TOKEN"

# شناسه‌های ادمین‌ها
ADMIN_IDS = [123456789]  # شناسه‌های تلگرام ادمین‌ها را اینجا وارد کنید

class AdminBot:
    def __init__(self):
        """Initialize bot with required handlers"""
        self.application = Application.builder().token(ADMIN_BOT_TOKEN).build()
        self.current_section = {}
        self.current_action = {}
        self.temp_content = {}
        self._setup_handlers()

    def _setup_handlers(self):
        """Setup all necessary command and callback handlers"""
        # دستورات اصلی
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("done", self.done_command))
        
        # هندلرهای بخش‌های مختلف
        self.application.add_handler(CallbackQueryHandler(self.handle_section_selection, pattern="^section_"))
        self.application.add_handler(CallbackQueryHandler(self.handle_action_selection, pattern="^action_"))
        
        # هندلرهای عملیات
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text_input))
        self.application.add_handler(MessageHandler(filters.PHOTO, self.handle_photo))
        self.application.add_handler(MessageHandler(filters.VIDEO, self.handle_video))
        self.application.add_handler(MessageHandler(filters.DOCUMENT, self.handle_document))
        
        # هندلر خطا
        self.application.add_error_handler(self.error_handler)

    def run(self):
        """Run the bot"""
        self.application.run_polling()

    async def is_admin(self, user_id: int) -> bool:
        """Check if user is admin"""
        return user_id in ADMIN_IDS

    def get_main_menu_keyboard(self) -> InlineKeyboardMarkup:
        """Create main menu keyboard"""
        keyboard = [
            [
                InlineKeyboardButton("قالب متنی", callback_data="section_text_template"),
                InlineKeyboardButton("قالب تصویری", callback_data="section_image_template")
            ],
            [
                InlineKeyboardButton("ایده ریلز", callback_data="section_reels_idea"),
                InlineKeyboardButton("کال تو اکشن", callback_data="section_call_to_action")
            ],
            [
                InlineKeyboardButton("کپشن", callback_data="section_caption"),
                InlineKeyboardButton("بایو", callback_data="section_bio")
            ],
            [
                InlineKeyboardButton("نقشه راه", callback_data="section_roadmap"),
                InlineKeyboardButton("آموزش‌ها", callback_data="section_tutorials")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)

    def get_action_keyboard(self) -> InlineKeyboardMarkup:
        """Create action selection keyboard"""
        keyboard = [
            [
                InlineKeyboardButton("افزودن محتوا", callback_data="action_add"),
                InlineKeyboardButton("ویرایش محتوا", callback_data="action_edit")
            ],
            [
                InlineKeyboardButton("حذف محتوا", callback_data="action_delete"),
                InlineKeyboardButton("مشاهده محتوا", callback_data="action_view")
            ],
            [InlineKeyboardButton("بازگشت به منو", callback_data="action_back")]
        ]
        return InlineKeyboardMarkup(keyboard)

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command"""
        user_id = update.effective_user.id
        if not await self.is_admin(user_id):
            await update.message.reply_text("متأسفانه شما دسترسی به این ربات را ندارید.")
            return

        await update.message.reply_text(
            "به ربات مدیریت محتوای میلیونی‌شو خوش آمدید!\n"
            "لطفاً بخش مورد نظر خود را انتخاب کنید:",
            reply_markup=self.get_main_menu_keyboard()
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command"""
        user_id = update.effective_user.id
        if not await self.is_admin(user_id):
            return

        help_text = """
راهنمای استفاده از ربات مدیریت محتوا:

1️⃣ افزودن محتوا:
- بخش مورد نظر را انتخاب کنید
- گزینه "افزودن محتوا" را بزنید
- متن محتوا را ارسال کنید
- در صورت نیاز، فایل رسانه را ارسال کنید

2️⃣ ویرایش محتوا:
- بخش مورد نظر را انتخاب کنید
- گزینه "ویرایش محتوا" را بزنید
- شماره محتوا را وارد کنید
- محتوای جدید را ارسال کنید

3️⃣ حذف محتوا:
- بخش مورد نظر را انتخاب کنید
- گزینه "حذف محتوا" را بزنید
- شماره محتوا را وارد کنید

4️⃣ مشاهده محتوا:
- بخش مورد نظر را انتخاب کنید
- گزینه "مشاهده محتوا" را بزنید
"""
        await update.message.reply_text(help_text)

    async def handle_section_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle section selection"""
        user_id = update.effective_user.id
        if not await self.is_admin(user_id):
            return

        query = update.callback_query
        await query.answer()
        
        section = query.data.replace("section_", "")
        self.current_section[user_id] = section
        
        await query.message.edit_text(
            f"بخش {section} انتخاب شد.\nچه عملیاتی می‌خواهید انجام دهید؟",
            reply_markup=self.get_action_keyboard()
        )

    async def handle_action_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle action selection"""
        user_id = update.effective_user.id
        if not await self.is_admin(user_id):
            return

        query = update.callback_query
        await query.answer()
        
        action = query.data.replace("action_", "")
        self.current_action[user_id] = action
        
        if action == "back":
            await query.message.edit_text(
                "لطفاً بخش مورد نظر خود را انتخاب کنید:",
                reply_markup=self.get_main_menu_keyboard()
            )
            return
            
        section = self.current_section.get(user_id)
        if action == "add":
            await query.message.edit_text(
                "لطفاً متن محتوای جدید را ارسال کنید:"
            )
        elif action == "edit":
            await query.message.edit_text(
                "لطفاً شماره محتوایی که می‌خواهید ویرایش کنید را وارد کنید:"
            )
        elif action == "delete":
            await query.message.edit_text(
                "لطفاً شماره محتوایی که می‌خواهید حذف کنید را وارد کنید:"
            )
        elif action == "view":
            await self.show_content(query.message, section)

    async def handle_text_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle text input"""
        user_id = update.effective_user.id
        if not await self.is_admin(user_id):
            return

        text = update.message.text
        action = self.current_action.get(user_id)
        section = self.current_section.get(user_id)
        
        if not action or not section:
            return
            
        if action == "add":
            self.temp_content[user_id] = {"text": text}
            await update.message.reply_text(
                "متن ذخیره شد. اگر می‌خواهید فایل رسانه‌ای اضافه کنید، آن را ارسال کنید.\n"
                "در غیر این صورت /done را بزنید."
            )
        elif action == "edit":
            try:
                content_id = int(text)
                # ذخیره شناسه محتوا برای ویرایش
                self.temp_content[user_id] = {"id": content_id}
                await update.message.reply_text(
                    "لطفاً متن جدید را وارد کنید:"
                )
                self.current_action[user_id] = "edit_text"
            except ValueError:
                if "id" in self.temp_content.get(user_id, {}):
                    # ویرایش متن محتوای موجود
                    content_id = self.temp_content[user_id]["id"]
                    new_content = {"text": text}
                    if await self.edit_content(section, content_id, new_content):
                        await update.message.reply_text(
                            "محتوا با موفقیت ویرایش شد. اگر می‌خواهید فایل رسانه‌ای را هم تغییر دهید، آن را ارسال کنید.\n"
                            "در غیر این صورت /done را بزنید."
                        )
                    else:
                        await update.message.reply_text(
                            "متأسفانه در ویرایش محتوا مشکلی پیش آمد.",
                            reply_markup=self.get_main_menu_keyboard()
                        )
                else:
                    await update.message.reply_text("لطفاً یک شماره معتبر وارد کنید.")
        elif action == "delete":
            try:
                content_id = int(text)
                if await self.delete_content(section, content_id):
                    await update.message.reply_text(
                        "محتوا با موفقیت حذف شد.",
                        reply_markup=self.get_main_menu_keyboard()
                    )
                else:
                    await update.message.reply_text(
                        "متأسفانه در حذف محتوا مشکلی پیش آمد.",
                        reply_markup=self.get_main_menu_keyboard()
                    )
            except ValueError:
                await update.message.reply_text("لطفاً یک شماره معتبر وارد کنید.")

    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle photo upload"""
        user_id = update.effective_user.id
        if not await self.is_admin(user_id):
            return

        photo = update.message.photo[-1]
        file_id = photo.file_id
        
        if user_id in self.temp_content:
            self.temp_content[user_id]["media_type"] = "photo"
            self.temp_content[user_id]["media_path"] = file_id
            await update.message.reply_text("تصویر ذخیره شد. برای اتمام /done را بزنید.")

    async def handle_video(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle video upload"""
        user_id = update.effective_user.id
        if not await self.is_admin(user_id):
            return

        video = update.message.video
        file_id = video.file_id
        
        if user_id in self.temp_content:
            self.temp_content[user_id]["media_type"] = "video"
            self.temp_content[user_id]["media_path"] = file_id
            await update.message.reply_text("ویدیو ذخیره شد. برای اتمام /done را بزنید.")

    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle document upload"""
        user_id = update.effective_user.id
        if not await self.is_admin(user_id):
            return

        document = update.message.document
        file_id = document.file_id
        
        if user_id in self.temp_content:
            self.temp_content[user_id]["media_type"] = "document"
            self.temp_content[user_id]["media_path"] = file_id
            await update.message.reply_text("فایل ذخیره شد. برای اتمام /done را بزنید.")

    async def show_content(self, message, section: str) -> None:
        """Show content of a section"""
        try:
            with open(f"content/{section}.json", "r", encoding="utf-8") as f:
                content = json.load(f)
                text = f"محتوای بخش {section}:\n\n"
                for item in content:
                    text += f"🔹 شماره {item['id']}:\n{item['text']}\n\n"
                await message.edit_text(
                    text,
                    reply_markup=self.get_action_keyboard()
                )
        except FileNotFoundError:
            await message.edit_text(
                f"محتوایی برای بخش {section} یافت نشد.",
                reply_markup=self.get_action_keyboard()
            )

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle errors"""
        logger.error(f"Error occurred: {context.error}")
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "متأسفانه خطایی رخ داد. لطفاً دوباره تلاش کنید."
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

    async def save_content(self, user_id: int) -> None:
        """Save content to JSON file"""
        if user_id not in self.temp_content:
            return
            
        section = self.current_section.get(user_id)
        if not section:
            return
            
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

    async def done_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /done command"""
        user_id = update.effective_user.id
        if not await self.is_admin(user_id):
            return
            
        if user_id not in self.temp_content:
            await update.message.reply_text(
                "هیچ محتوایی برای ذخیره وجود ندارد.",
                reply_markup=self.get_main_menu_keyboard()
            )
            return
            
        if await self.save_content(user_id):
            await update.message.reply_text(
                "محتوا با موفقیت ذخیره شد.",
                reply_markup=self.get_main_menu_keyboard()
            )
            # پاک کردن محتوای موقت
            del self.temp_content[user_id]
        else:
            await update.message.reply_text(
                "متأسفانه در ذخیره محتوا مشکلی پیش آمد. لطفاً دوباره تلاش کنید.",
                reply_markup=self.get_main_menu_keyboard()
            )

    async def edit_content(self, section: str, content_id: int, new_content: dict) -> bool:
        """Edit existing content"""
        filepath = f"content/{section}.json"
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = json.load(f)
                
            # پیدا کردن محتوای مورد نظر
            for i, item in enumerate(content):
                if item["id"] == str(content_id):
                    # اگر فایل رسانه جدید وجود دارد
                    if "media_type" in new_content and "media_path" in new_content:
                        media_path = await self.save_media_file(
                            new_content["media_path"],
                            section,
                            new_content["media_type"]
                        )
                        new_content["media_path"] = media_path
                        
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

# Create and run admin bot
if __name__ == "__main__":
    admin_bot = AdminBot()
    admin_bot.run() 