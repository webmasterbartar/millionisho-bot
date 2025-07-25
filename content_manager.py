import os
import json
import logging
from typing import Dict, List, Optional, Union, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class Content:
    id: str
    type: str
    text: str
    media_path: Optional[str] = None
    media_type: Optional[str] = None  # 'photo', 'video', 'voice', 'document'
    additional_info: Optional[Dict] = None

class ContentManager:
    def __init__(self, content_dir: str = "content"):
        self.content_dir = content_dir
        self.content: Dict[str, Dict[str, Content]] = {}
        self.load_content()
    
    def load_content(self) -> None:
        """Load all content from JSON files"""
        sections = [
            "text_template",
            "image_template",
            "reels_idea",
            "call_to_action",
            "caption",
            "interactive_story",
            "bio",
            "roadmap"
        ]
        
        for section in sections:
            self.content[section] = {}
            
            # Load default content
            default_file = os.path.join(self.content_dir, f"{section}.json")
            if os.path.exists(default_file):
                try:
                    with open(default_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        for item in data:
                            content = Content(
                                id=str(item['id']),
                                type=section,
                                text=item['text'],
                                media_path=item.get('media_path'),
                                media_type=item.get('media_type'),
                                additional_info=item.get('additional_info')
                            )
                            self.content[section][content.id] = content
                    logger.info(f"Loaded {len(data)} default items for section {section}")
                except Exception as e:
                    logger.error(f"Error loading default content for section {section}: {str(e)}")
            
            # Load admin-added content
            admin_file = os.path.join(self.content_dir, f"{section}_admin.json")
            if os.path.exists(admin_file):
                try:
                    with open(admin_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        for item in data:
                            content = Content(
                                id=str(item['id']),
                                type=section,
                                text=item['text'],
                                media_path=item.get('media_path'),
                                media_type=item.get('media_type'),
                                additional_info=item.get('additional_info')
                            )
                            self.content[section][content.id] = content
                    logger.info(f"Loaded {len(data)} admin-added items for section {section}")
                except Exception as e:
                    logger.error(f"Error loading admin content for section {section}: {str(e)}")
    
    def save_admin_content(self, section: str) -> None:
        """Save admin-added content to separate file"""
        try:
            admin_file = os.path.join(self.content_dir, f"{section}_admin.json")
            content_list = [
                {
                    "id": content.id,
                    "text": content.text,
                    "media_path": content.media_path,
                    "media_type": content.media_type,
                    "additional_info": content.additional_info
                }
                for content in self.content[section].values()
                if content.id.startswith("admin_")  # Only save admin-added content
            ]
            
            with open(admin_file, 'w', encoding='utf-8') as f:
                json.dump(content_list, f, ensure_ascii=False, indent=4)
            logger.info(f"Saved {len(content_list)} admin items for section {section}")
        except Exception as e:
            logger.error(f"Error saving admin content for section {section}: {str(e)}")
    
    def add_content(self, section: str, content_data: Dict) -> Optional[str]:
        """Add new content to a section"""
        try:
            if section not in self.content:
                self.content[section] = {}
            
            # Generate a new unique ID with admin_ prefix
            new_id = "admin_1"
            admin_count = 1
            while new_id in self.content[section]:
                admin_count += 1
                new_id = f"admin_{admin_count}"
            
            # Create new content object
            new_content = Content(
                id=new_id,
                type=section,
                text=content_data["text"],
                media_path=content_data.get("media_path"),
                media_type=content_data.get("media_type"),
                additional_info=content_data.get("additional_info")
            )
            
            # Add to memory
            self.content[section][new_id] = new_content
            
            # Save to file
            self.save_admin_content(section)
            
            logger.info(f"Added new content to section {section} with ID {new_id}")
            return new_id
            
        except Exception as e:
            logger.error(f"Error adding content to section {section}: {str(e)}")
            return None
    
    def get_content(self, section: str, index: int) -> Optional[Content]:
        """Get content by section and index"""
        try:
            if section not in self.content:
                logger.warning(f"Section {section} not found")
                return None
            
            content_list = list(self.content[section].values())
            if not content_list or index >= len(content_list):
                logger.warning(f"Content not found at index {index} in section {section}")
                return None
                
            return content_list[index]
            
        except Exception as e:
            logger.error(f"Error getting content from section {section} at index {index}: {str(e)}")
            return None
    
    def get_content_by_id(self, section: str, content_id: str) -> Optional[Content]:
        """Get content by section and ID"""
        try:
            return self.content.get(section, {}).get(content_id)
        except Exception as e:
            logger.error(f"Error getting content by ID from section {section}: {str(e)}")
            return None
    
    def get_section_size(self, section: str) -> int:
        """Get number of items in a section"""
        try:
            return len(self.content.get(section, {}))
        except Exception as e:
            logger.error(f"Error getting section size for {section}: {str(e)}")
            return 0
    
    def get_tutorial(self, section: str) -> Optional[Content]:
        """Get tutorial content for a section"""
        try:
            tutorial_file = os.path.join(self.content_dir, "tutorials", f"{section}.json")
            if os.path.exists(tutorial_file):
                with open(tutorial_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return Content(
                        id="tutorial",
                        type="tutorial",
                        text=data['text'],
                        media_path=data.get('media_path'),
                        media_type=data.get('media_type')
                    )
            return None
        except Exception as e:
            logger.error(f"Error getting tutorial for section {section}: {str(e)}")
            return None
    
    def get_all_content_zip(self) -> Optional[str]:
        """Get path to ZIP file containing all content"""
        try:
            zip_path = os.path.join(self.content_dir, "all_content.zip")
            return zip_path if os.path.exists(zip_path) else None
        except Exception as e:
            logger.error(f"Error getting content ZIP: {str(e)}")
            return None

# Global instance
content_manager = ContentManager() 