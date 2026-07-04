"""
AppState — State Machine cho Translation & Generation
"""

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class TranslatePhase(str, Enum):
    IDLE = "idle"
    LOADING = "loading"
    TRANSLATING = "translating"
    QA = "qa"
    COMPLETE = "complete"
    FAILED = "failed"


class GenPhase(str, Enum):
    IDLE = "idle"
    PLANNING = "planning"
    WRITING = "writing"
    REVIEWING = "reviewing"
    COMPLETE = "complete"
    FAILED = "failed"


class GenFlow(str, Enum):
    CONTINUE = "continue"
    SPINOFF = "spin-off"


@dataclass
class AppState:
    translate_phase: TranslatePhase = TranslatePhase.IDLE
    gen_phase: GenPhase = GenPhase.IDLE
    gen_flow: GenFlow = GenFlow.CONTINUE

    current_chapter: int = 0
    total_chapters: int = 0
    translated_count: int = 0
    failed_count: int = 0

    novel_profile_path: str = ""
    current_model: str = "gemini-flash"
    context_usage_pct: float = 0.0

    error_message: str = ""

    @property
    def is_busy(self) -> bool:
        return (
            self.translate_phase not in (TranslatePhase.IDLE, TranslatePhase.COMPLETE, TranslatePhase.FAILED)
            or self.gen_phase not in (GenPhase.IDLE, GenPhase.COMPLETE, GenPhase.FAILED)
        )

    def reset_translation(self):
        self.translate_phase = TranslatePhase.IDLE
        self.current_chapter = 0
        self.translated_count = 0
        self.failed_count = 0
        self.error_message = ""

    def reset_generation(self):
        self.gen_phase = GenPhase.IDLE
        self.gen_flow = GenFlow.CONTINUE
        self.error_message = ""

    def status_line(self) -> str:
        if self.translate_phase != TranslatePhase.IDLE:
            pct = (self.translated_count / max(self.total_chapters, 1)) * 100
            return f"Dịch {self.translated_count}/{self.total_chapters} ({pct:.0f}%) | Fail: {self.failed_count}"
        if self.gen_phase != GenPhase.IDLE:
            return f"Sinh: {self.gen_phase.value} | Chương {self.current_chapter}"
        return "Sẵn sàng"
