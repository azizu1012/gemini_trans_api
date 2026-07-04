"""
OOP Gemini Translator Package V3.5
==================================
Hệ thống dịch tiểu thuyết hướng đối tượng với workflow "Tam Quyền Phân Lập" sử dụng Router API v2.
Tích hợp Textual TUI, NovelProfile, ModelRegistry, AppState.
"""

# === CONFIG ===
from .config.config import TranslatorConfig, STATIC_GLOSSARY
from .config.api_manager import APIManagerV2
from .config.model_registry import ModelRegistry, model_registry

# === DATA ===
from .data.content_loader import ChapterData, ContentLoader, ContentMerger
from .data.novel_profile import NovelProfile, NovelProfileExporter, export_novel_profile
from .data.word_stats import scan_novel_file, scan_temp_chapters
from .data.novel_importer import (
    NovelImporter, ExtractionResult, ImportReview,
)

# === MEMORY ===
from .memory.memory_manager import MemoryManager
from .memory.enrichment_profiles import (
    EnrichmentType, EnrichmentProfile, EnrichmentSuggestion,
)

# === STATE ===
from .state.app_state import AppState, TranslatePhase, GenPhase, GenFlow

# === OUTPUT ===
from .output.ebook_maker import EbookMaker

# === STYLE ===
from .style.style_director import (
    build_style_section, STYLE_LABELS, DIRECTION_LABELS,
    CREATIVITY_LABELS, TAG_LABELS,
)
from .style.smart_director import SmartDirector

# === PLAN ===
from .plan.chapter_director import (
    ChapterDirector, ChapterNote, BatchFramework,
    EnhancedChapterDirector,
)
from .plan.pacing_controller import (
    PacingController, PacingType, PacingRule,
    ContentRestriction, ChapterPacingPlan, PACING_RULES,
)
from .plan.scene_director import (
    SceneBeat, SceneDirector,
)
from .plan.note_utils import (
    save_chapter_note, load_chapter_note, build_constraint_section,
    check_forbidden_characters_in_text,
)

# === REVIEW ===
from .review.quality_assurance import (
    QualityAssurance, QualityLevel, QualityScore,
    ReviewResult,
)
from .review.ai_enhanced_qa import AIEnhancedQA

# === TRACKERS ===
from .trackers import CharacterTracker

# === WORKFLOW ===
from .workflow.translator_core import PromptBuilder, ChapterTranslator
from .workflow.workflow_v3 import AgenticTranslator, TranslationResult, WorkflowV3Runner
from .workflow.coordinator import (
    GenerationCoordinator, ArcPlan, GenProgress,
)
from .workflow.expansion_engine import (
    SmartExpansionEngine, ExpansionTarget, ExpansionResult,
    MAP_POTENTIALS,
    STORY_MAPS, StoryMap, StoryAnalyzer, SmartChapterNamer, CHAPTER_NAMER,
    estimate_final_chapter_count,
)

# === WORLD ===
from .world import WorldManager, Glossary, GlossaryManager

__all__ = [
    # Config
    'TranslatorConfig', 'STATIC_GLOSSARY',
    'APIManagerV2',
    'ModelRegistry', 'model_registry',

    # Data
    'ChapterData', 'ContentLoader', 'ContentMerger',
    'NovelProfile', 'NovelProfileExporter', 'export_novel_profile',
    'NovelImporter', 'ExtractionResult', 'ImportReview',
    'scan_novel_file', 'scan_temp_chapters',

    # Memory
    'MemoryManager',
    'EnrichmentType', 'EnrichmentProfile', 'EnrichmentSuggestion',

    # State
    'AppState', 'TranslatePhase', 'GenPhase', 'GenFlow',

    # Output
    'EbookMaker',

    # Style
    'build_style_section', 'STYLE_LABELS', 'DIRECTION_LABELS',
    'CREATIVITY_LABELS', 'TAG_LABELS',
    'SmartDirector',

    # Plan
    'ChapterDirector', 'ChapterNote', 'BatchFramework',
    'EnhancedChapterDirector',
    'PacingController', 'PacingType', 'PacingRule',
    'ContentRestriction', 'ChapterPacingPlan', 'PACING_RULES',
    'SceneBeat', 'SceneDirector',
    'save_chapter_note', 'load_chapter_note', 'build_constraint_section',
    'check_forbidden_characters_in_text',

    # Review
    'QualityAssurance', 'QualityLevel', 'QualityScore',
    'ReviewResult', 'AIEnhancedQA',

    # Trackers
    'CharacterTracker',

    # Workflow
    'PromptBuilder', 'ChapterTranslator',
    'AgenticTranslator', 'TranslationResult', 'WorkflowV3Runner',
    'GenerationCoordinator', 'ArcPlan', 'GenProgress',
    'SmartExpansionEngine', 'ExpansionTarget', 'ExpansionResult',
    'MAP_POTENTIALS',
    'STORY_MAPS', 'StoryMap', 'StoryAnalyzer', 'SmartChapterNamer', 'CHAPTER_NAMER',
    'estimate_final_chapter_count',

    # World
    'WorldManager', 'Glossary', 'GlossaryManager',
]

__version__ = "3.5.0"
