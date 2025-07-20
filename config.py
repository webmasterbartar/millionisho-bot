import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Telegram Bot Token
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')

# Admin IDs
ADMIN_IDS = [1807336889, 101913815]  # شناسه تلگرام ادمین‌ها: Arshia Aghayi و Sepehr

# WordPress API Configuration
WORDPRESS_BASE_URL = os.getenv('WORDPRESS_BASE_URL', 'https://millionisho.com')

# Content Directory
CONTENT_DIR = os.getenv('CONTENT_DIR', 'content')

# Cache Configuration
CACHE_TTL = int(os.getenv('CACHE_TTL', 3600))  # 1 hour
CACHE_MAX_SIZE = int(os.getenv('CACHE_MAX_SIZE', 1000))

# Debug Mode
DEBUG = True  # Set to True for detailed logging 
