"""
Trackers Module - Theo dõi nhân vật, phong cách, thực thể
"""
from .character_tracker import (
    CharacterTracker, CharacterState,
    CharacterRelationship, EmotionalState, RelationshipType,
)
from .entity_database import (
    EntityDatabase, Entity, EntityType, Character, Creature,
    Power, Weapon, get_entity_database,
    MAIN_CHARACTERS, CREATURES_DATABASE, POWERS_DATABASE, WEAPONS_DATABASE,
)
from .style_learner import (
    StyleLearner, TranslationExample, LearnedPattern,
    StyleRule, PatternType, get_style_learner,
    POWER_PATTERNS, CRYSTAL_PATTERNS, SPECIAL_TERMS,
    SUFFIX_RULES, PREFIX_RULES,
)

__all__ = [
    # Character Tracker
    'CharacterTracker', 'CharacterState',
    'CharacterRelationship', 'EmotionalState', 'RelationshipType',
    # Entity Database
    'EntityDatabase', 'Entity', 'EntityType', 'Character', 'Creature',
    'Power', 'Weapon', 'get_entity_database',
    'MAIN_CHARACTERS', 'CREATURES_DATABASE', 'POWERS_DATABASE', 'WEAPONS_DATABASE',
    # Style Learner
    'StyleLearner', 'TranslationExample', 'LearnedPattern',
    'StyleRule', 'PatternType', 'get_style_learner',
    'POWER_PATTERNS', 'CRYSTAL_PATTERNS', 'SPECIAL_TERMS',
    'SUFFIX_RULES', 'PREFIX_RULES',
]
