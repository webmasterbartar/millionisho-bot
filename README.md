# Millionisho Telegram Bot (ربات تلگرام میلیونی‌شو)

ربات تلگرام هوشمند برای پروژه میلیونی‌شو با قابلیت چت GPT-4 و سیستم لایسنس.

## امکانات

- چت با GPT-4
- سیستم مدیریت لایسنس
- یکپارچه‌سازی با وردپرس
- رابط کاربری فارسی

## پیش‌نیازها

- Python 3.8+
- پایگاه وردپرس با افزونه Millionisho Licensing
- توکن ربات تلگرام
- کلید API از OpenAI

## نصب و راه‌اندازی

1. کلون کردن مخزن:
```bash
git clone https://github.com/YourUsername/millionisho-bot.git
cd millionisho-bot
```

2. نصب وابستگی‌ها:
```bash
pip install -r requirements.txt
```

3. کپی کردن فایل نمونه تنظیمات:
```bash
cp config.example.py config.py
```

4. تنظیم متغیرهای محیطی در فایل config.py:
- TELEGRAM_TOKEN
- OPENAI_API_KEY
- WORDPRESS_BASE_URL
- تنظیمات پروکسی

5. اجرای ربات:
```bash
python bot.py
```

## متغیرهای محیطی

```env
TELEGRAM_TOKEN=your_telegram_bot_token
OPENAI_API_KEY=your_openai_api_key
WORDPRESS_BASE_URL=your_wordpress_site_url
PROXY_HOST=proxy_host
PROXY_PORT=proxy_port
PROXY_USERNAME=proxy_username
PROXY_PASSWORD=proxy_password
```

## دیپلوی

این پروژه برای دیپلوی در Railway بهینه‌سازی شده است. برای دیپلوی:

1. یک پروژه جدید در Railway ایجاد کنید
2. متغیرهای محیطی را تنظیم کنید
3. پروژه را به مخزن GitHub متصل کنید

## مجوز

کلیه حقوق محفوظ است © 2024 