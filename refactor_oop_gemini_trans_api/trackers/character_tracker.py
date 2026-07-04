"""
Character Tracker Module (AI-Inference Based)
==============================================
Theo dõi trạng thái nhân vật dựa trên insights từ AI Director.

Principles:
1. No Regex: Không tự scan text để tìm sự kiện.
2. State Management: Quản lý location, trauma, power, relationships.
3. Lazy Persistence: Chỉ lưu khi có thay đổi thực sự.
"""

import os
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime


class EmotionalState(Enum):
    """Trạng thái cảm xúc"""
    CALM = "calm"           # Bình tĩnh
    TENSE = "tense"         # Căng thẳng
    ANGRY = "angry"         # Tức giận
    FEARFUL = "fearful"     # Sợ hãi
    DETERMINED = "determined"  # Quyết tâm
    HOPEFUL = "hopeful"     # Hy vọng
    DESPERATE = "desperate"  # Tuyệt vọng
    COLD = "cold"           # Lạnh lùng
    HAPPY = "happy"         # Vui vẻ
    SAD = "sad"             # Buồn bã
    CONFUSED = "confused"   # Bối rối


class RelationshipType(Enum):
    """Loại quan hệ"""
    ALLY = "ally"           # Đồng minh
    FRIEND = "friend"       # Bạn bè
    RIVAL = "rival"         # Đối thủ
    ENEMY = "enemy"         # Kẻ thù
    NEUTRAL = "neutral"     # Trung lập
    LOVE = "love"           # Tình cảm
    FAMILY = "family"       # Gia đình
    MENTOR = "mentor"       # Sư phụ
    STUDENT = "student"     # Đệ tử
    MASTER = "master"       # Chủ nhân (cho pet/summmon)
    SERVANT = "servant"     # Tôi tớ


@dataclass
class CharacterRelationship:
    """Quan hệ giữa 2 nhân vật"""
    target: str                     # Tên nhân vật khác
    relation_type: RelationshipType
    trust_level: int = 50           # 0-100
    description: str = ""           # Mô tả ngắn về mối quan hệ hiện tại
    last_interaction_chapter: int = 0


@dataclass
class CharacterState:
    """Trạng thái đầy đủ của một nhân vật"""
    name: str # ID của nhân vật (thường là tên chính)
    
    # Basic info
    role: str = "side"              # main, side, antagonist, npc
    first_appearance: int = 0
    last_seen_chapter: int = 0
    is_alive: bool = True
    current_location_id: Optional[str] = None # Location ID hiện tại
    
    # Emotional/Mental state
    emotional_state: EmotionalState = EmotionalState.CALM
    personality_traits: List[str] = field(default_factory=list)
    
    # Power/Ability
    power_level: int = 0            # 0-100 (Relative score)
    active_powers: List[str] = field(default_factory=list) # Các năng lực đang kích hoạt/sở hữu
    equipment: List[str] = field(default_factory=list)
    
    # Trauma/Growth
    trauma_score: int = 0           # 0-100 (Thay cho trauma_level cũ)
    trauma_events: List[str] = field(default_factory=list) # List các sự kiện gây trauma
    growth_events: List[str] = field(default_factory=list) # List các sự kiện phát triển (powerup)
    
    # Relationships
    relationships: Dict[str, CharacterRelationship] = field(default_factory=dict)
    
    # Voice/Style
    speech_style: str = ""          # Phong cách nói chuyện
    
    # History
    key_moments: List[Dict] = field(default_factory=list)
    
    def to_prompt_context(self) -> str:
        """Tạo context cho prompt"""
        lines = [
            f"👤 {self.name}:",
            f"   Role: {self.role} | Status: {'Alive' if self.is_alive else 'Dead'}",
            f"   Emotion: {self.emotional_state.value}",
            f"   Location: {self.current_location_id or 'Unknown'}",
            f"   Power: {self.power_level}/100 | Trauma: {self.trauma_score}/100",
        ]
        
        if self.active_powers:
            lines.append(f"   Powers: {', '.join(self.active_powers[:3])}")
            
        if self.speech_style:
            lines.append(f"   Voice: {self.speech_style}")
            
        if self.relationships:
            rels = []
            for target, rel in list(self.relationships.items())[:2]:
                rels.append(f"{target}({rel.relation_type.value})")
            if rels:
                lines.append(f"   Relations: {', '.join(rels)}")
        
        return "\n".join(lines)


class CharacterTracker:
    """
    Character State Tracker (AI Version)
    
    Chịu trách nhiệm:
    1. Lưu trữ trạng thái nhân vật.
    2. Cập nhật trạng thái dựa trên AI insights.
    3. Cung cấp context cho PromptBuilder.
    """
    
    def __init__(self, save_dir: str = "character_states"):
        self.save_dir = save_dir
        self.state_file = os.path.join(self.save_dir, "characters.json")
        
        # Main character database
        self.characters: Dict[str, CharacterState] = {}
        
        # Load existing data
        self._load_state()

    def _ensure_save_dir(self):
        """Lazy creation of save directory"""
        if self.save_dir and not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir, exist_ok=True)

    def _load_state(self):
        """Load state từ file"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                for name, char_data in data.items():
                    # Reconstruct Enum and Nested objects
                    
                    # Emotion
                    try:
                        emotion = EmotionalState(char_data.get('emotional_state', 'calm'))
                    except ValueError:
                        emotion = EmotionalState.CALM
                        
                    # Relationships
                    relationships = {}
                    for target, rel_data in char_data.get('relationships', {}).items():
                        try:
                            rtype = RelationshipType(rel_data.get('relation_type', 'neutral'))
                        except ValueError:
                            rtype = RelationshipType.NEUTRAL
                            
                        relationships[target] = CharacterRelationship(
                            target=target,
                            relation_type=rtype,
                            trust_level=rel_data.get('trust_level', 50),
                            description=rel_data.get('description', ''),
                            last_interaction_chapter=rel_data.get('last_interaction_chapter', 0)
                        )
                        
                    self.characters[name] = CharacterState(
                        name=name,
                        role=char_data.get('role', 'side'),
                        first_appearance=char_data.get('first_appearance', 0),
                        last_seen_chapter=char_data.get('last_seen_chapter', 0),
                        is_alive=char_data.get('is_alive', True),
                        current_location_id=char_data.get('current_location_id'),
                        emotional_state=emotion,
                        personality_traits=char_data.get('personality_traits', []),
                        power_level=char_data.get('power_level', 0),
                        active_powers=char_data.get('active_powers', []),
                        equipment=char_data.get('equipment', []),
                        trauma_score=char_data.get('trauma_score', 0),
                        trauma_events=char_data.get('trauma_events', []),
                        growth_events=char_data.get('growth_events', []),
                        relationships=relationships,
                        speech_style=char_data.get('speech_style', ''),
                        key_moments=char_data.get('key_moments', [])
                    )
            except Exception as e:
                print(f"[CharacterTracker] Failed to load state: {e}")

    def save_state(self):
        """Lưu state ra file (Lazy Creation)"""
        self._ensure_save_dir()
        
        # Convert to serializable format
        data = {}
        for name, char in self.characters.items():
            char_dict = asdict(char)
            # Convert enums
            char_dict['emotional_state'] = char.emotional_state.value
            char_dict['relationships'] = {
                k: {
                    'target': v.target,
                    'relation_type': v.relation_type.value,
                    'trust_level': v.trust_level,
                    'description': v.description,
                    'last_interaction_chapter': v.last_interaction_chapter,
                }
                for k, v in char.relationships.items()
            }
            data[name] = char_dict
        
        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def ingest_ai_insights(self, chapter: int, ai_data: Dict[str, Any]):
        """
        Cập nhật trạng thái nhân vật từ AI Insights.
        
        Expected ai_data structure:
        {
            "characters": [
                {
                    "name": "Lâm Nhất",
                    "status": "alive",
                    "emotion": "tense",
                    "location": "City Ruins",
                    "new_powers": ["Fireball"],
                    "trauma_event": "Saw friend die",
                    "relationships": [{"target": "Trương Thành", "type": "ally"}]
                }
            ]
        }
        """
        changes_detected = False
        
        for char_insight in ai_data.get('characters', []):
            name = char_insight.get('name')
            if not name: continue
            
            # Get or Create Character
            if name not in self.characters:
                self.characters[name] = CharacterState(
                    name=name,
                    first_appearance=chapter,
                    last_seen_chapter=chapter
                )
                changes_detected = True
            
            char = self.characters[name]
            char.last_seen_chapter = chapter
            
            # Update Basis Status
            if 'status' in char_insight:
                 if char_insight['status'] == 'dead': char.is_alive = False
            
            # Update Emotion
            if 'emotion' in char_insight:
                try:
                    char.emotional_state = EmotionalState(char_insight['emotion'])
                except ValueError: pass
                
            # Update Location
            if 'location' in char_insight:
                char.current_location_id = char_insight['location']
                
            # Update Powers
            if 'new_powers' in char_insight:
                for p in char_insight['new_powers']:
                    if p not in char.active_powers:
                        char.active_powers.append(p)
                        char.power_level = min(100, char.power_level + 5)
                        char.growth_events.append(f"Chapter {chapter}: Gained {p}")
            
            # Update Trauma
            if 'trauma_event' in char_insight:
                char.trauma_events.append(f"Chapter {chapter}: {char_insight['trauma_event']}")
                char.trauma_score = min(100, char.trauma_score + 10)
                
            # Update Relationships
            if 'relationships' in char_insight:
                for rel in char_insight['relationships']:
                    target = rel.get('target')
                    if not target: continue
                    
                    try:
                        rtype = RelationshipType(rel.get('type', 'neutral'))
                    except ValueError:
                        rtype = RelationshipType.NEUTRAL
                        
                    char.relationships[target] = CharacterRelationship(
                        target=target,
                        relation_type=rtype,
                        last_interaction_chapter=chapter
                    )

            changes_detected = True

        if changes_detected:
            self.save_state()

    def get_character_context(self, chapter_num: int, characters: Optional[List[str]] = None) -> str:
        """
        Lấy context nhân vật cho prompt
        """
        if characters is None:
            # Lấy main characters và những ai xuất hiện gần đây
            characters = [
                name for name, char in self.characters.items()
                if (char.role == "main" or 
                   (char.last_seen_chapter > 0 and chapter_num - char.last_seen_chapter <= 5))
                   and char.is_alive
            ]
        
        context_parts = []
        for name in characters:
            char = self.characters.get(name)
            if char:
                context_parts.append(char.to_prompt_context())
        
        return "\n\n".join(context_parts) if context_parts else ""

