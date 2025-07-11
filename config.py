import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Telegram Bot Configuration
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '7631560101:AAEezcBRD_JXH5l5KNoBggflvqcVs4YPYbk')

# OpenAI Configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')

# WordPress API Configuration
WORDPRESS_BASE_URL = os.getenv('WORDPRESS_BASE_URL', 'https://mirallino.ir')

# Proxy Configuration (optional)
PROXY_URL = os.getenv('PROXY_URL', None) 
