from typing import Dict, List, Optional, Union, Tuple
import json
import os
from dataclasses import dataclass

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
            file_path = os.path.join(self.content_dir, f"{section}.json")
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.content[section] = {
                        str(item['id']): Content(
                            id=str(item['id']),
                            type=section,
                            text=item['text'],
                            media_path=item.get('media_path'),
                            media_type=item.get('media_type'),
                            additional_info=item.get('additional_info')
                        )
                        for item in data
                    }
    
    def get_content(self, section: str, index: int) -> Optional[Content]:
        """Get content by section and index"""
        if section not in self.content:
            return None
        
        content_list = list(self.content[section].values())
        if not content_list or index >= len(content_list):
            return None
            
        return content_list[index]
    
    def get_content_by_id(self, section: str, content_id: str) -> Optional[Content]:
        """Get content by section and ID"""
        return self.content.get(section, {}).get(content_id)
    
    def get_section_size(self, section: str) -> int:
        """Get number of items in a section"""
        return len(self.content.get(section, {}))
    
    def get_tutorial(self, section: str) -> Optional[Content]:
        """Get tutorial content for a section"""
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
    
    def get_all_content_zip(self) -> Optional[str]:
        """Get path to ZIP file containing all content"""
        zip_path = os.path.join(self.content_dir, "all_content.zip")
        return zip_path if os.path.exists(zip_path) else None

    def add_content(self, section: str, content_data: Dict) -> None:
        """Add new content to a section"""
        if section not in self.content:
            self.content[section] = {}
            
        # Generate a new unique ID
        new_id = str(len(self.content[section]) + 1)
        while new_id in self.content[section]:
            new_id = str(int(new_id) + 1)
            
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
        file_path = os.path.join(self.content_dir, f"{section}.json")
        content_list = [
            {
                "id": content.id,
                "text": content.text,
                "media_path": content.media_path,
                "media_type": content.media_type,
                "additional_info": content.additional_info
            }
            for content in self.content[section].values()
        ]
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(content_list, f, ensure_ascii=False, indent=4)

# Global instance
content_manager = ContentManager() 