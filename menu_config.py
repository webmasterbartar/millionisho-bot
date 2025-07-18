from typing import Dict, List

# تنظیمات کلی منوها
MAIN_MENU_BUTTONS = {
    "template": "قالب میلیونی",
    "reels_idea": "ایده ریلز میلیونی",
    "call_to_action": "کال تو اکشن",
    "caption": "کپشن",
    "complete_idea": "ایده کامل (رندوم)",
    "interactive_story": "استوری تعاملی",
    "bio": "بایو",
    "roadmap": "نقشه راه (الگوریتم اینستا)",
    "all_files": "دریافت همه فایل ها به صورت یکجا (zip)",
    "vip": "اشتراک مادام العمر میلیونی شو (vip)",
    "favorites": "علاقه مندی ها"
}

# تنظیمات زیرمنوی قالب
TEMPLATE_SUBMENU_BUTTONS = {
    "text_template": "قالب متنی",
    "image_template": "قالب تصویری",
    "tutorial": "توضیحات و آموزش",
    "back_to_main": "بازگشت به منوی اصلی"
}

# دکمه‌های ناوبری
NAVIGATION_BUTTONS = {
    "next": "بعدی",
    "back": "بازگشت به مرحله قبل",
    "back_to_main": "بازگشت به منوی اصلی"
}

# پیام‌های سیستمی
MESSAGES = {
    "welcome": "به ربات میلیونی‌شو خوش آمدید! 👋\nلطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
    "vip_only": "کاربر عزیز این بخش مخصوص مشترکین vip ما هست",
    "free_limit_reached": "برای استفاده از امکانات کامل ربات و دسترسی به همه قالب ها نیاز به داشتن اشتراک دارید",
    "already_subscribed": "کاربر عزیز شما جزو مشترکین ما هستید نیاز به تهییه اشتراک دیگری ندارید"
}

# تنظیمات محدودیت‌های رایگان
FREE_LIMITS = {
    "template": 3,
    "reels_idea": 3,
    "call_to_action": 3,
    "caption": 3,
    "interactive_story": 3,
    "bio": 3
}

# بخش‌های قفل شده برای کاربران رایگان
LOCKED_SECTIONS = [
    "tutorial",
    "roadmap",
    "all_files",
    "favorites"
]

# تعداد محتوا در هر بخش
CONTENT_COUNTS = {
    "text_template": 470,
    "image_template": 60,
    "reels_idea": 100,  # مثال
    "call_to_action": 50,  # مثال
    "caption": 80,  # مثال
    "bio": 40  # مثال
} 