from typing import Dict, Optional
from datetime import datetime

class UserManager:
    def __init__(self):
        self.users: Dict[str, Dict] = {}
        
    def init_user(self, user_id: str) -> None:
        """Initialize a new user with default values"""
        if user_id not in self.users:
            self.users[user_id] = {
                "is_vip": False,
                "subscription_date": None,
                "usage_counts": {},
                "current_section": None,
                "current_index": {},
                "favorites": set(),
                "last_activity": datetime.now()
            }
    
    def is_vip(self, user_id: str) -> bool:
        """Check if user is VIP"""
        self.init_user(user_id)
        return self.users[user_id]["is_vip"]
    
    def set_vip(self, user_id: str, status: bool = True) -> None:
        """Set user's VIP status"""
        self.init_user(user_id)
        self.users[user_id]["is_vip"] = status
        if status:
            self.users[user_id]["subscription_date"] = datetime.now()
    
    def get_usage_count(self, user_id: str, section: str) -> int:
        """Get usage count for a specific section"""
        self.init_user(user_id)
        return self.users[user_id]["usage_counts"].get(section, 0)
    
    def increment_usage(self, user_id: str, section: str) -> None:
        """Increment usage count for a section"""
        self.init_user(user_id)
        counts = self.users[user_id]["usage_counts"]
        counts[section] = counts.get(section, 0) + 1
    
    def get_current_index(self, user_id: str, section: str) -> int:
        """Get current index for a section"""
        self.init_user(user_id)
        return self.users[user_id]["current_index"].get(section, 0)
    
    def set_current_index(self, user_id: str, section: str, index: int) -> None:
        """Set current index for a section"""
        self.init_user(user_id)
        self.users[user_id]["current_index"][section] = index
    
    def set_current_section(self, user_id: str, section: str) -> None:
        """Set current section for user"""
        self.init_user(user_id)
        self.users[user_id]["current_section"] = section
    
    def get_current_section(self, user_id: str) -> Optional[str]:
        """Get current section for user"""
        self.init_user(user_id)
        return self.users[user_id]["current_section"]
    
    def add_to_favorites(self, user_id: str, content_id: str) -> None:
        """Add content to user's favorites"""
        self.init_user(user_id)
        self.users[user_id]["favorites"].add(content_id)
    
    def remove_from_favorites(self, user_id: str, content_id: str) -> None:
        """Remove content from user's favorites"""
        self.init_user(user_id)
        self.users[user_id]["favorites"].discard(content_id)
    
    def get_favorites(self, user_id: str) -> set:
        """Get user's favorites"""
        self.init_user(user_id)
        return self.users[user_id]["favorites"]
    
    def update_last_activity(self, user_id: str) -> None:
        """Update user's last activity timestamp"""
        self.init_user(user_id)
        self.users[user_id]["last_activity"] = datetime.now()

    def activate_vip(self, user_id: str, activation_code: str) -> bool:
        """Activate VIP status using activation code"""
        # TODO: Implement proper activation code validation
        # For now, accept any non-empty code
        if activation_code.strip():
            self.set_vip(user_id, True)
            return True
        return False

    def can_access_section(self, user_id: int, section: str) -> bool:
        """Check if user can access a section"""
        # Admins always have access
        if self.is_admin(user_id):
            return True
            
        user = self.get_user(user_id)
        
        # Free sections that don't require VIP
        free_sections = ["text_template", "image_template"]
        if section in free_sections:
            return True
        
        # VIP users have access to all sections
        if user["vip"]:
            return True
        
        # All users have unlimited access to all sections
        return True
    
    def increment_usage(self, user_id: int, section: str) -> None:
        """Increment usage count for a section"""
        # Don't increment usage for admins
        if self.is_admin(user_id):
            return
            
        # Don't increment usage for anyone - unlimited access
        return

# Global instance
user_manager = UserManager() 