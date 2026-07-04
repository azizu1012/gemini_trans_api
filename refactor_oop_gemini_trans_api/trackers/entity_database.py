"""
Entity Database - Từ Điển Mở Rộng
=================================
Quản lý nhân vật, sinh vật (dị loại), năng lực, vũ khí

Categories:
1. CHARACTERS - Nhân vật (tên, vai trò, năng lực)
2. CREATURES - Dị loại/Quái vật (tên, cấp độ, đặc điểm)
3. POWERS - Năng lực/Hệ thống sức mạnh
4. WEAPONS - Vũ khí/Thần khí
5. ITEMS - Vật phẩm đặc biệt
6. LOCATIONS - Địa danh (bổ sung cho WorldBuilder)
7. FACTIONS - Tổ chức/Phe phái
"""

import os
import json
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime


class EntityType(Enum):
    """Loại entity"""
    CHARACTER = "character"
    CREATURE = "creature"
    POWER = "power"
    WEAPON = "weapon"
    ITEM = "item"
    LOCATION = "location"
    FACTION = "faction"


@dataclass
class Entity:
    """Base entity"""
    id: str                          # Unique ID (auto-gen hoặc manual)
    name_cn: str                     # Tên gốc tiếng Trung
    name_vn: str                     # Tên tiếng Việt (đã dịch)
    aliases: List[str] = field(default_factory=list)  # Tên khác/biệt danh
    
    entity_type: EntityType = EntityType.CHARACTER
    description: str = ""
    
    # Tracking
    first_seen_chapter: int = 0
    last_seen_chapter: int = 0
    mention_count: int = 0
    
    # Relations
    related_entities: List[str] = field(default_factory=list)  # List of entity IDs
    
    # Tags for search
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        data = asdict(self)
        data['entity_type'] = self.entity_type.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Entity':
        data['entity_type'] = EntityType(data.get('entity_type', 'character'))
        return cls(**data)


@dataclass
class Character(Entity):
    """Nhân vật"""
    role: str = "supporting"  # protagonist, antagonist, supporting, minor
    affiliation: str = ""     # Thuộc tổ chức nào
    
    # Abilities
    powers: List[str] = field(default_factory=list)  # List power IDs
    weapons: List[str] = field(default_factory=list)  # List weapon IDs
    
    # Status
    status: str = "alive"  # alive, dead, unknown, transformed
    power_level: int = 0   # 0-100
    
    def __post_init__(self):
        self.entity_type = EntityType.CHARACTER


@dataclass
class Creature(Entity):
    """Dị loại / Quái vật"""
    creature_class: str = "unknown"   # anomaly, beast, spirit, god, etc.
    danger_level: str = "unknown"     # D, C, B, A, S, SS, SSS
    
    # Abilities
    abilities: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    
    # Origin
    origin: str = ""  # Nguồn gốc
    habitat: str = ""  # Nơi sinh sống
    
    def __post_init__(self):
        self.entity_type = EntityType.CREATURE


@dataclass
class Power(Entity):
    """Năng lực / Hệ thống sức mạnh"""
    power_type: str = "unknown"  # aether, divine, mutation, psychic, etc.
    source: str = ""             # Nguồn sức mạnh
    
    # Requirements
    requirements: List[str] = field(default_factory=list)
    side_effects: List[str] = field(default_factory=list)
    
    # Users
    known_users: List[str] = field(default_factory=list)  # Character IDs
    
    def __post_init__(self):
        self.entity_type = EntityType.POWER


@dataclass
class Weapon(Entity):
    """Vũ khí / Thần khí"""
    weapon_type: str = "unknown"  # sword, gun, artifact, divine_weapon
    material: str = ""
    
    # Properties
    abilities: List[str] = field(default_factory=list)
    requirements: List[str] = field(default_factory=list)  # Yêu cầu sử dụng
    
    # Owner
    current_owner: str = ""  # Character ID
    previous_owners: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        self.entity_type = EntityType.WEAPON


# =============================================================================
# PRE-BUILT DATABASE - "Đừng Chạy, Nơi Này Khắp Nơi Là Quái Vật"
# =============================================================================

# Nhân vật chính
MAIN_CHARACTERS: Dict[str, Character] = {
    "lam_nhat": Character(
        id="lam_nhat",
        name_cn="林一",
        name_vn="Lâm Nhất",
        aliases=["Lâm ca", "Số 1"],
        role="protagonist",
        description="Nhân vật chính, có khả năng đặc biệt liên quan đến dị loại",
        powers=["aether_vision", "mutation_control"],
        status="alive",
        tags=["protagonist", "mutant", "special_ability"]
    ),
    "truong_thanh": Character(
        id="truong_thanh",
        name_cn="张城",
        name_vn="Trương Thành",
        aliases=["Thành ca", "Búa Sắt"],
        role="supporting",
        description="Đồng đội thân thiết của Lâm Nhất, chiến binh mạnh mẽ",
        powers=["enhanced_strength"],
        weapons=["iron_hammer"],
        status="alive",
        tags=["ally", "warrior", "strength"]
    ),
    "so_lang": Character(
        id="so_lang",
        name_cn="楚狼",
        name_vn="Sở Lang",
        aliases=["Lang ca", "Sói Cô Đơn"],
        role="supporting",
        description="Thành viên đội, có quá khứ bí ẩn",
        status="alive",
        tags=["ally", "mysterious", "lone_wolf"]
    ),
}

# Dị loại / Quái vật
CREATURES_DATABASE: Dict[str, Creature] = {
    "common_anomaly": Creature(
        id="common_anomaly",
        name_cn="普通异类",
        name_vn="Dị loại thường",
        creature_class="anomaly",
        danger_level="D",
        description="Dị loại cấp thấp, số lượng lớn",
        abilities=["basic_attack"],
        tags=["common", "low_level"]
    ),
    "elite_anomaly": Creature(
        id="elite_anomaly",
        name_cn="精英异类",
        name_vn="Dị loại tinh anh",
        creature_class="anomaly",
        danger_level="B",
        description="Dị loại cấp cao hơn, có năng lực đặc biệt",
        abilities=["special_attack", "enhanced_durability"],
        tags=["elite", "mid_level"]
    ),
    "boss_anomaly": Creature(
        id="boss_anomaly",
        name_cn="领主异类",
        name_vn="Dị loại Lãnh Chủ",
        aliases=["Boss", "Chúa tể"],
        creature_class="anomaly",
        danger_level="S",
        description="Dị loại cấp boss, cai quản một vùng",
        abilities=["domain_control", "minion_summon", "enhanced_all"],
        tags=["boss", "high_level", "territory"]
    ),
}

# Năng lực
POWERS_DATABASE: Dict[str, Power] = {
    "aether_power": Power(
        id="aether_power",
        name_cn="以太之力",
        name_vn="Sức mạnh Aether",  # KHÔNG phải "Aether chi lực"
        aliases=["Linh lực Aether", "Năng lượng Aether"],
        power_type="aether",
        source="Aether (nguồn năng lượng vũ trụ)",
        description="Năng lượng cơ bản của thế giới, nguồn sức mạnh cho nhiều năng lực khác",
        tags=["basic", "energy", "universal"]
    ),
    "divine_power": Power(
        id="divine_power",
        name_cn="神赐之力",
        name_vn="Thần lực",  # KHÔNG phải "Thần ban chi lực"
        aliases=["Sức mạnh Thần ban", "Lực lượng thần thánh"],
        power_type="divine",
        source="Thần linh",
        description="Sức mạnh được thần linh ban tặng",
        requirements=["Được thần linh chọn", "Có thể chất đặc biệt"],
        tags=["divine", "blessed", "rare"]
    ),
    "spring_power": Power(
        id="spring_power",
        name_cn="神泉者",
        name_vn="Thần Tuyền Giả",  # Người sở hữu Suối Thần
        aliases=["Kẻ sở hữu Suối Thần"],
        power_type="divine",
        source="Suối Thần (Divine Spring)",
        description="Người được Suối Thần chọn, sở hữu năng lực tái sinh và hồi phục",
        known_users=["lam_nhat"],
        tags=["divine", "regeneration", "chosen"]
    ),
}

# Vũ khí / Thần khí
WEAPONS_DATABASE: Dict[str, Weapon] = {
    "divine_weapon": Weapon(
        id="divine_weapon",
        name_cn="噬神器",
        name_vn="Thần Khí",  # Vũ khí sử dụng Thần lực
        aliases=["Vũ khí Thần lực", "Divine Weapon"],
        weapon_type="divine_weapon",
        description="Vũ khí được chế tạo để sử dụng Thần lực, không phải vũ khí diệt thần",
        requirements=["Phải có Thần lực để kích hoạt"],
        tags=["divine", "requires_power"]
    ),
    "divine_crystal": Weapon(
        id="divine_crystal",
        name_cn="神赐之晶",
        name_vn="Tinh thể Thần lực",  # KHÔNG phải "Thần ban chi tinh"
        aliases=["Thần tinh", "Divine Crystal"],
        weapon_type="artifact",
        description="Tinh thể chứa Thần lực cô đọng, dùng để tăng cường sức mạnh",
        tags=["consumable", "power_boost", "rare"]
    ),
}


class EntityDatabase:
    """
    Quản lý tất cả entities
    
    Features:
    - Load/Save từ file JSON
    - Search by name, type, tags
    - Auto-update từ chapter content
    - Export to glossary format
    """
    
    def __init__(self, save_dir: str = "entity_data"):
        self.save_dir = save_dir
        self.save_dir = save_dir
        # os.makedirs(save_dir, exist_ok=True)  <-- REMOVED: lazy creation
        
        # Databases
        self.characters: Dict[str, Character] = {}
        self.creatures: Dict[str, Creature] = {}
        self.powers: Dict[str, Power] = {}
        self.weapons: Dict[str, Weapon] = {}
        self.items: Dict[str, Entity] = {}
        self.locations: Dict[str, Entity] = {}
        self.factions: Dict[str, Entity] = {}
        
        # Load pre-built data
        self._init_default_data()
        
        # Load saved data
        self._load_from_files()

    def _ensure_save_dir(self):
        """Đảm bảo thư mục lưu trữ tồn tại"""
        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir, exist_ok=True)
    
    def _init_default_data(self):
        """Initialize với data mặc định"""
        self.characters.update(MAIN_CHARACTERS)
        self.creatures.update(CREATURES_DATABASE)
        self.powers.update(POWERS_DATABASE)
        self.weapons.update(WEAPONS_DATABASE)
    
    def _load_from_files(self):
        """Load data từ files"""
        for entity_type in EntityType:
            filepath = os.path.join(self.save_dir, f"{entity_type.value}s.json")
            if os.path.exists(filepath):
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    self._merge_loaded_data(entity_type, data)
                except Exception as e:
                    print(f"⚠️ Failed to load {filepath}: {e}")
    
    def _merge_loaded_data(self, entity_type: EntityType, data: Dict):
        """Merge loaded data vào database"""
        db = self._get_db(entity_type)
        class_mapping = {
            EntityType.CHARACTER: Character,
            EntityType.CREATURE: Creature,
            EntityType.POWER: Power,
            EntityType.WEAPON: Weapon,
            EntityType.ITEM: Entity,
            EntityType.LOCATION: Entity,
            EntityType.FACTION: Entity,
        }
        cls = class_mapping.get(entity_type, Entity)
        for entity_id, entity_data in data.items():
            if entity_id not in db:
                try:
                    db[entity_id] = cls.from_dict(entity_data)
                except Exception as e:
                    print(f"⚠️ Failed to parse {entity_id} as {entity_type.value}: {e}")
    
    def _get_db(self, entity_type: EntityType) -> Dict:
        """Lấy database theo type"""
        mapping = {
            EntityType.CHARACTER: self.characters,
            EntityType.CREATURE: self.creatures,
            EntityType.POWER: self.powers,
            EntityType.WEAPON: self.weapons,
            EntityType.ITEM: self.items,
            EntityType.LOCATION: self.locations,
            EntityType.FACTION: self.factions,
        }
        return mapping.get(entity_type, self.items)
    
    def save_all(self):
        """Lưu tất cả data ra files"""
        self._ensure_save_dir()
        for entity_type in EntityType:
            db = self._get_db(entity_type)
            if db:
                filepath = os.path.join(self.save_dir, f"{entity_type.value}s.json")
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(
                        {k: v.to_dict() for k, v in db.items()},
                        f, ensure_ascii=False, indent=2
                    )
    
    def add_entity(self, entity: Entity) -> bool:
        """Thêm entity mới"""
        db = self._get_db(entity.entity_type)
        if entity.id in db:
            return False  # Already exists
        db[entity.id] = entity
        self.save_all()
        return True
    
    def get_entity(self, entity_id: str) -> Optional[Entity]:
        """Lấy entity theo ID"""
        for entity_type in EntityType:
            db = self._get_db(entity_type)
            if entity_id in db:
                return db[entity_id]
        return None
    
    def search_by_name(self, name: str, entity_type: Optional[EntityType] = None) -> List[Entity]:
        """Tìm entity theo tên (CN hoặc VN)"""
        results = []
        name_lower = name.lower()
        
        dbs = [self._get_db(entity_type)] if entity_type else [
            self.characters, self.creatures, self.powers, 
            self.weapons, self.items, self.locations, self.factions
        ]
        
        for db in dbs:
            for entity in db.values():
                if (name_lower in entity.name_cn.lower() or 
                    name_lower in entity.name_vn.lower() or
                    any(name_lower in alias.lower() for alias in entity.aliases)):
                    results.append(entity)
        
        return results
    
    def search_by_tags(self, tags: List[str]) -> List[Entity]:
        """Tìm entity theo tags"""
        results = []
        tags_set = set(t.lower() for t in tags)
        
        for db in [self.characters, self.creatures, self.powers, 
                   self.weapons, self.items, self.locations, self.factions]:
            for entity in db.values():
                entity_tags = set(t.lower() for t in entity.tags)
                if tags_set & entity_tags:  # Intersection
                    results.append(entity)
        
        return results
    
    def export_to_glossary(self) -> str:
        """Export thành format glossary cho prompt"""
        lines = ["[TỪ ĐIỂN ENTITY MỞ RỘNG]", ""]
        
        # Characters
        if self.characters:
            lines.append("👤 NHÂN VẬT:")
            for char in self.characters.values():
                aliases = f" ({', '.join(char.aliases)})" if char.aliases else ""
                lines.append(f"  • {char.name_cn} → {char.name_vn}{aliases}")
        
        # Creatures
        if self.creatures:
            lines.append("\n👹 DỊ LOẠI:")
            for creature in self.creatures.values():
                lines.append(f"  • {creature.name_cn} → {creature.name_vn} [{creature.danger_level}]")
        
        # Powers
        if self.powers:
            lines.append("\n⚡ NĂNG LỰC:")
            for power in self.powers.values():
                aliases = f" (hoặc: {', '.join(power.aliases[:2])})" if power.aliases else ""
                lines.append(f"  • {power.name_cn} → {power.name_vn}{aliases}")
        
        # Weapons
        if self.weapons:
            lines.append("\n🗡️ VŨ KHÍ/VẬT PHẨM:")
            for weapon in self.weapons.values():
                lines.append(f"  • {weapon.name_cn} → {weapon.name_vn}")
        
        return "\n".join(lines)
    
    def get_context_for_chapter(self, chapter_num: int) -> str:
        """Lấy entity context cho một chương"""
        # Lấy các entity đã xuất hiện đến chương này
        relevant = []
        
        for db in [self.characters, self.creatures, self.powers, self.weapons]:
            for entity in db.values():
                if entity.first_seen_chapter <= chapter_num:
                    relevant.append(entity)
        
        if not relevant:
            return ""
        
        lines = ["[ENTITY CONTEXT]"]
        for entity in relevant[:20]:  # Limit 20
            lines.append(f"  • {entity.name_vn}: {entity.description[:50]}...")
        
        return "\n".join(lines)


# Global instance
_entity_db: Optional[EntityDatabase] = None

def get_entity_database(save_dir: str = "entity_data") -> EntityDatabase:
    """Lấy global entity database"""
    global _entity_db
    if _entity_db is None:
        _entity_db = EntityDatabase(save_dir)
    return _entity_db
