# Millionisho Telegram Bot (ربات تلگرام میلیونی‌شو) 🤖

A Telegram bot integrated with WordPress and OpenAI GPT-4 for the Millionisho platform.

یک ربات تلگرام با قابلیت یکپارچه‌سازی با وردپرس و OpenAI GPT-4 برای پلتفرم میلیونی‌شو.

## Features (ویژگی‌ها) ✨

- License verification system (سیستم تأیید لایسنس)
- Integration with OpenAI GPT-4 (یکپارچه‌سازی با OpenAI GPT-4)
- WordPress API integration (یکپارچه‌سازی با API وردپرس)
- Persistent license caching (ذخیره‌سازی موقت لایسنس‌ها)
- Graceful error handling (مدیریت خطاهای هوشمند)
- Proxy support (پشتیبانی از پروکسی)

## Requirements (پیش‌نیازها) 📋

- Python 3.8 or higher (پایتون 3.8 یا بالاتر)
- WordPress site with Millionisho plugin (سایت وردپرس با افزونه میلیونی‌شو)
- Telegram Bot Token (توکن ربات تلگرام)
- OpenAI API Key (کلید API اوپن‌ای‌آی)

## Installation (نصب و راه‌اندازی) 🚀

1. Clone the repository (کلون کردن مخزن):
```bash
git clone https://github.com/yourusername/millionisho-bot.git
cd millionisho-bot
```

2. Create virtual environment (ساخت محیط مجازی):
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

3. Install dependencies (نصب وابستگی‌ها):
```bash
pip install -r requirements.txt
```

4. Set up environment variables (تنظیم متغیرهای محیطی):
```bash
cp .env.example .env
# Edit .env file with your configurations
```

## Configuration (پیکربندی) ⚙️

Create a `.env` file with the following variables:

```env
# Telegram Bot Configuration
TELEGRAM_TOKEN=your_telegram_token_here

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here

# WordPress API Configuration
WORDPRESS_BASE_URL=https://your-wordpress-site.com

# Proxy Configuration (optional)
PROXY_URL=http://127.0.0.1:8118

# Cache Configuration
CACHE_TTL=3600
CACHE_MAX_SIZE=1000
```

## Running the Bot (اجرای ربات) 🏃‍♂️

### Local Development (توسعه لوکال)

```bash
python bot.py
```

### Production Deployment (استقرار در محیط تولید)

The bot is configured to run on Railway. Simply push to the repository and Railway will automatically deploy.

ربات برای اجرا روی Railway پیکربندی شده است. کافیست تغییرات را push کنید تا Railway به صورت خودکار مستقر شود.

## WordPress Plugin (افزونه وردپرس) 🔌

1. Install the Millionisho WordPress plugin (نصب افزونه وردپرس میلیونی‌شو)
2. Activate the plugin (فعال‌سازی افزونه)
3. Configure the license settings (پیکربندی تنظیمات لایسنس)

## Error Handling (مدیریت خطاها) 🔧

The bot includes comprehensive error handling:
- License verification errors
- OpenAI API errors
- Network timeouts
- Invalid user inputs

ربات شامل مدیریت خطاهای جامع است:
- خطاهای تأیید لایسنس
- خطاهای API اوپن‌ای‌آی
- تایم‌اوت‌های شبکه
- ورودی‌های نامعتبر کاربر

## Logging (ثبت رویدادها) 📝

Logs are stored in `bot.log` with the following information:
- Bot startup/shutdown
- License verifications
- API calls
- Error messages

لاگ‌ها در فایل `bot.log` ذخیره می‌شوند و شامل اطلاعات زیر هستند:
- شروع/توقف ربات
- تأییدیه‌های لایسنس
- فراخوانی‌های API
- پیام‌های خطا

## Contributing (مشارکت) 👥

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License (مجوز) 📄

This project is proprietary and confidential. All rights reserved.

این پروژه اختصاصی و محرمانه است. تمامی حقوق محفوظ است. 