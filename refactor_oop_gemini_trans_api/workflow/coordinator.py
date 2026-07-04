"""
Generation Coordinator Loop — mượn design ainovel-cli
Architect (plan) → Writer (draft) → Critic (review) → checkpoint
YAGNI: chapter-level checkpoint, rolling arc plan, reuse existing QA/API
"""

import os, json, asyncio, time
from typing import Optional, Dict, List, Tuple, Callable
from dataclasses import dataclass, field, asdict

from ..config.config import TranslatorConfig
from ..memory.memory_manager import MemoryManager
from ..data.novel_profile import NovelProfileExporter, NovelProfile
from ..state.app_state import AppState, GenPhase, GenFlow
from ..memory.enrichment_profiles import EnrichmentProfile, EnrichmentType
from ..style.style_director import build_style_section
from ..data.word_stats import scan_novel_file, scan_temp_chapters
from .translator_core import ChapterTranslator
from ..review.quality_assurance import QualityAssurance
from ..plan.scene_director import SceneDirector, SceneBeat
from ..plan.note_utils import save_chapter_note, load_chapter_note, build_constraint_section
from ..world.glossary import GlossaryManager
ARC_BATCH_SIZE = 20  # Max chapters per arc plan

@dataclass
class ArcPlan:
    """Kế hoạch 1 arc — Architect sinh ra"""
    start_chapter: int
    num_chapters: int
    arc_title: str
    chapters: List[Dict] = field(default_factory=list)
    # Mỗi chapter: {"num": int, "title": str, "outline": str, "events": [str], "characters": [str]}


@dataclass
class GenProgress:
    """Checkpoint generation — lưu theo arc + chapter"""
    flow: str = "continue"
    spinoff_character: str = ""
    start_chapter: int = 0
    total_chapters: int = 0
    completed: int = 0
    current_arc_index: int = 0
    arcs_completed: int = 0
    arc_plans: List[Dict] = field(default_factory=list)
    chapter_titles: Dict[int, str] = field(default_factory=dict)
    last_model: str = ""
    # Volume Outline
    volumes: List[Dict] = field(default_factory=list)
    current_volume_index: int = 0


class GenerationCoordinator:

    def __init__(self, config: TranslatorConfig,
                 glossary: Optional[GlossaryManager],
                 memory: MemoryManager,
                 translator: ChapterTranslator,
                 app_state: Optional[AppState] = None):
        self.config = config
        self.glossary = glossary
        self.memory = memory
        self.translator = translator
        self.qa = translator.qa
        self.app_state = app_state
        self.scene_director = SceneDirector()
        self._stop_flag = False
        self.log_callback: Optional[Callable[[str], None]] = None  # callable(msg) for TUI integration
        self.steer_queue: Optional[asyncio.Queue] = None  # asyncio.Queue[str] for real-time steer

        self.checkpoint_path = os.path.join(config.output_dir, "generation_progress.json")
        self.temp_folder = config.temp_folder
        os.makedirs(self.temp_folder, exist_ok=True)

        # Auto-scan word count từ dữ liệu có sẵn (Hỗ trợ cả chuỗi "auto" và số legacy 2500 / <= 0)
        val = self.config.avg_words_per_chapter
        is_auto = False
        if isinstance(val, str) and val.strip().lower() == "auto":
            is_auto = True
        else:
            try:
                num = int(val)
                if num <= 0 or num == 2500:
                    is_auto = True
                else:
                    self.config.avg_words_per_chapter = num
            except (ValueError, TypeError):
                is_auto = True

        if is_auto:
            try:
                stats = scan_temp_chapters(self.temp_folder)
                if stats["count"] < 3:
                    stats = scan_novel_file(config.raw_content_file)
                if stats["count"] >= 3:
                    self.config.avg_words_per_chapter = int(stats["avg"])
                    self.log(f"📊 Auto-scanned word count: ~{int(stats['avg'])} words/chapter "
                             f"(from {stats['count']} chapters)")
                else:
                    self.config.avg_words_per_chapter = 3000  # Fallback
            except Exception:
                self.config.avg_words_per_chapter = 3000

    def log(self, msg: str):
        if self.log_callback:
            self.log_callback(msg)
        else:
            print(f"[Coordinator] {msg}")

    # ── Checkpoint ──

    def _save_checkpoint(self, progress: GenProgress):
        try:
            with open(self.checkpoint_path, "w", encoding="utf-8") as f:
                json.dump(asdict(progress), f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.log(f"⚠️ Checkpoint save failed: {e}")

    def _load_checkpoint(self) -> Optional[GenProgress]:
        if not os.path.exists(self.checkpoint_path):
            return None
        try:
            with open(self.checkpoint_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return GenProgress(**data)
        except Exception:
            return None

    def clear_checkpoint(self):
        if os.path.exists(self.checkpoint_path):
            os.remove(self.checkpoint_path)

    # ── Architect: lập kế hoạch tổng thể (volume outline) ──

    async def _plan_volumes_async(self, start_ch: int, total_ch: int,
                                   profile: Optional[NovelProfile]) -> List[Dict]:
        """AI phân chia các chương còn lại thành các volume theo chủ đề"""
        if total_ch <= ARC_BATCH_SIZE:
            return [{"title": "Toàn bộ", "start_chapter": start_ch,
                      "num_chapters": total_ch, "theme": "free"}]

        profile_section = profile.get_prompt_section() if profile else ""
        self.log(f"🏗️  Architect: planning volumes for {total_ch} chapters from {start_ch}")

        system_prompt = f"""Bạn là Architect — kiến trúc sư tổng thể cốt truyện.
    Nhiệm vụ: chia {total_ch} chương tiếp theo thành các volume (tập) nhỏ hơn theo chủ đề.

    Mỗi volume là một cụm chapters có cùng chủ đề/cảm hứng, giống một "hồi" trong tiểu thuyết.

    {profile_section}

    YÊU CẦU:
    - Mỗi volume 15-50 chapters
    - Volume có title sáng tạo, theme rõ ràng (world|character|challenge|free)
    - Volume kế tiếp phải nối tiếp mạch truyện

    Trả về JSON array volumes, mỗi item:
    {{"title": "Tên Volume", "start_chapter": N, "num_chapters": N, "theme": "world|character|challenge|free"}}

    Định dạng JSON, không markdown."""

        model = self.config.role_models.get("coordinator", "gemini-flash")
        raw, error = await self.translator.call_api(
            model=model,
            system_prompt=system_prompt,
            user_content=f"Hãy chia {total_ch} chương từ {start_ch} thành các volume.",
            temperature=0.5
        )

        if error:
            self.log(f"⚠️ Volume planning error: {error}, using single volume")
            return [{"title": "Toàn bộ", "start_chapter": start_ch,
                      "num_chapters": total_ch, "theme": "free"}]

        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        try:
            volumes = json.loads(raw)
            if isinstance(volumes, dict) and "volumes" in volumes:
                volumes = volumes["volumes"]
            if not isinstance(volumes, list):
                raise ValueError("not a list")
            # Validate
            total = sum(v.get("num_chapters", 0) for v in volumes)
            if total != total_ch:
                self.log(f"⚠️ Volume total ({total}) != ({total_ch}), adjusting")
                volumes[-1]["num_chapters"] += total_ch - total
            self.log(f"📚 Planned {len(volumes)} volumes: {[v.get('title','') for v in volumes]}")
            return volumes
        except Exception as e:
            self.log(f"⚠️ Volume parse error: {e}, using single volume")
            return [{"title": "Toàn bộ", "start_chapter": start_ch,
                      "num_chapters": total_ch, "theme": "free"}]

    # ── Architect: lập kế hoạch arc ──

    async def _plan_arc_async(self, start_ch: int, num_ch: int,
                               flow: str = "continue",
                               spinoff_char: str = "",
                               profile: Optional[NovelProfile] = None,
                               volume_context: str = "") -> ArcPlan:
        """Gọi Architect model để lập outline cho N chương"""
        self.log(f"🏗️  Architect: planning arc from chapter {start_ch} ({num_ch} chapters)")

        profile_section = profile.get_prompt_section() if profile else ""

        if flow == "spin-off":
            user_prompt = f"""Hãy lập kế hoạch cho {num_ch} chương spin-off tập trung vào nhân vật {spinoff_char}.

    YÊU CẦU:
    - Mỗi chương có: tên chương (sáng tạo), outline ngắn (2-3 câu), sự kiện chính, nhân vật xuất hiện
    - Spin-off phải bám sát thế giới và cốt truyện gốc
    - Trả về JSON array chapters, mỗi item: {{"num", "title", "outline", "events":[], "characters":[]}}

    Định dạng JSON, không markdown."""
        else:
            user_prompt = f"""Hãy lập kế hoạch cho {num_ch} chương tiếp theo của tiểu thuyết, bắt đầu từ chương {start_ch}.

    YÊU CẦU:
    - Mỗi chương có: tên chương (sáng tạo, khác biệt), outline ngắn (2-3 câu), sự kiện chính, nhân vật xuất hiện
    - Duy trì mạch truyện, phát triển nhân vật, thế giới
    - Trả về JSON array chapters, mỗi item: {{"num", "title", "outline", "events":[], "characters":[]}}

    Định dạng JSON, không markdown."""

        style_section = build_style_section(
            self.config.expansion_style,
            self.config.hallucination_direction,
            self.config.creativity_level
        )

        system_prompt = f"""Bạn là Architect — kiến trúc sư cốt truyện.
    Nhiệm vụ: lập kế hoạch chi tiết cho các chương tiếp theo dựa trên bối cảnh hiện tại.

    {profile_section}

    {style_section}

    {"BỐI CẢNH VOLUME HIỆN TẠI: " + volume_context if volume_context else ""}

    QUY TẮC:
    - Luôn giữ mạch truyện logic, không tạo plot hole
    - Phát triển nhân vật nhất quán
    - Mỗi chương phải có sự kiện đáng kể (không chapter đệm vô nghĩa)
    - Kết chương bằng cliffhanger hoặc câu hỏi mở"""

        model = self.config.role_models.get("coordinator", "gemini-flash")
        raw, error = await self.translator.call_api(
            model=model,
            system_prompt=system_prompt,
            user_content=user_prompt,
            temperature=0.5
        )

        if error:
            self.log(f"⚠️ Architect error: {error}, using fallback plan")
            return self._fallback_plan(start_ch, num_ch, flow, spinoff_char)

        chapters = self._parse_plan(raw, start_ch, num_ch)
        plan = ArcPlan(
            start_chapter=start_ch,
            num_chapters=len(chapters),
            arc_title=f"Arc từ chương {start_ch}",
            chapters=chapters
        )
        self.log(f"✅ Architect planned {len(chapters)} chapters")
        return plan

    def _fallback_plan(self, start_ch: int, num_ch: int,
                       flow: str, spinoff_char: str) -> ArcPlan:
        """Fallback khi Architect API lỗi"""
        chapters = []
        for i in range(num_ch):
            ch_num = start_ch + i
            title = f"Chương {ch_num}: {'Spin-off: ' + spinoff_char if flow == 'spin-off' else 'Tiếp diễn'}"
            chapters.append({
                "num": ch_num,
                "title": title,
                "outline": f"Tiếp tục câu chuyện tại chương {ch_num}",
                "events": [],
                "characters": [spinoff_char] if flow == "spin-off" else []
            })
        return ArcPlan(
            start_chapter=start_ch,
            num_chapters=num_ch,
            arc_title=f"Arc từ chương {start_ch} (fallback)",
            chapters=chapters
        )

    def _parse_plan(self, raw: str, start_ch: int, num_ch: int) -> List[Dict]:
        """Parse JSON từ response Architect, fallback nếu lỗi"""
        raw = raw.strip()
        # Xoá markdown code block nếu có
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
            raw = raw.rsplit("```", 1)[0]
        raw = raw.strip()

        chapters = None
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                chapters = data
            elif isinstance(data, dict) and "chapters" in data:
                chapters = data["chapters"]
        except json.JSONDecodeError:
            pass

        if not chapters or not isinstance(chapters, list):
            self.log("⚠️ Could not parse Architect JSON, using linear fallback")
            return self._fallback_plan(start_ch, num_ch, "", "").chapters

        result = []
        for i, ch in enumerate(chapters):
            result.append({
                "num": start_ch + i,
                "title": ch.get("title", f"Chương {start_ch + i}"),
                "outline": ch.get("outline", ""),
                "events": ch.get("events", []),
                "characters": ch.get("characters", []),
            })
        return result

    # ── Writer: viết 1 chương ──

    async def _write_chapter_async(self, chapter_plan: Dict,
                                   arc_context: str,
                                   is_enforcement: bool = False) -> Tuple[str, str]:
        """Gọi Writer model để viết 1 chương dựa trên outline + chapter note"""
        ch_num = chapter_plan["num"]
        title = chapter_plan["title"]
        outline = chapter_plan["outline"]
        events = "\n".join(f"- {e}" for e in chapter_plan.get("events", []))
        chars = ", ".join(chapter_plan.get("characters", []))

        # Load chapter note for constraints
        note = load_chapter_note(self.temp_folder, ch_num)
        known_list = list(self.glossary.get_glossary_dict().keys()) if self.glossary else []

        constraint_section = build_constraint_section(
            note,
            forbidden_new_chars=self.config.forbidden_new_characters,
            known_characters=known_list,
            avg_words=self.config.avg_words_per_chapter,
        )

        style_section = build_style_section(
            self.config.expansion_style,
            self.config.hallucination_direction,
            self.config.creativity_level
        )

        system_prompt = f"""Bạn là Writer — nhà văn chuyên viết tiểu thuyết Mạt thế/Khoa huyễn.

    {style_section}

    QUY TẮC VIẾT:
    - Xưng hô: Ta/Tao (KHÔNG dùng tôi)
    - Diễn đạt bằng hành động và chi tiết cảm giác
    - Kết hợp hội thoại và hành động (action beats)
    - Mô tả môi trường bằng âm thanh, mùi, ánh sáng
    - Kết chương bằng cliffhanger nhẹ hoặc câu hỏi mở

    {constraint_section}

    ĐỊNH DẠNG:
### Chương {ch_num}: {title} ###
    [nội dung...]"""

        if is_enforcement:
            system_prompt += """

    ⚠️ CƯỠNG CHẾ: Viết sát outline, không thêm tình tiết phụ, giữ dung lượng vừa phải."""

        user_content = f"""OUTLINE CHƯƠNG {ch_num}: {title}
    {outline}

    {arc_context}

    {"SỰ KIỆN CHÍNH:" + events if events else ""}
    {"NHÂN VẬT: " + chars if chars else ""}

    Hãy viết chương này bằng tiếng Việt, độ dài phù hợp (khoảng 2000-4000 từ)."""

        model = self.config.role_models.get("writer", "gemini-flash")
        temp = 0.0 if is_enforcement else 0.4

        try:
            text = await self.translator.call_api(
                model=model,
                system_prompt=system_prompt,
                user_content=user_content,
                temperature=temp
            )
            return text, ""
        except Exception as e:
            return "", str(e)

    # ── Writer: viết 1 scene (có enrichment) ──

    async def _write_scene_async(self, scene: 'SceneBeat',
                                   enrichment_section: str) -> Tuple[str, str]:
        """Viết 1 scene với enrichment types cụ thể"""
        style_section = build_style_section(
            self.config.expansion_style,
            self.config.hallucination_direction,
            self.config.creativity_level
        )

        avg_wc = self.config.avg_words_per_chapter
        scene_target = max(300, avg_wc // 4) if avg_wc > 0 else 500

        system_prompt = f"""Bạn là Writer — nhà văn chuyên viết tiểu thuyết Mạt thế/Khoa huyễn.

    {style_section}

    QUY TẮC VIẾT:
    - Xưng hô: Ta/Tao (KHÔNG dùng tôi)
    - Diễn đạt bằng hành động và chi tiết cảm giác
    - Kết hợp hội thoại và hành động (action beats)
    - Mô tả môi trường bằng âm thanh, mùi, ánh sáng
    - Kết scene bằng chuyển tiếp tự nhiên

    {enrichment_section}

    ĐỊNH DẠNG: Viết tự nhiên, không cần tiêu đề scene."""

        user_content = f"""CẢNH {scene.scene_index}
    Địa điểm: {scene.location}
    Nhân vật: {', '.join(scene.characters_present)}
    Mục tiêu: {scene.plot_goal}
    Giọng điệu: {scene.tone}
    Nhịp độ: {scene.pacing}
    {"Hội thoại chính: " + "; ".join(scene.key_dialogue_topics) if scene.key_dialogue_topics else ""}

    Hãy viết cảnh này bằng tiếng Việt (khoảng {scene_target} từ)."""

        model = self.config.role_models.get("writer", "gemini-flash")
        try:
            text = await self.translator.call_api(
                model=model,
                system_prompt=system_prompt,
                user_content=user_content,
                temperature=0.4
            )
            return text, ""
        except Exception as e:
            return "", str(e)

    # ── Critic: review 1 chương ──

    def _review_chapter(self, ch_num: int, text: str,
                        chapter_plan: Dict, attempt: int) -> Tuple[int, str]:
        """Review chương vừa viết, trả về (score, feedback)"""
        self.qa.update_context(
            previous_summary=chapter_plan.get("outline", ""),
            character_allowed_list=chapter_plan.get("characters", []),
            known_characters=list(self.glossary.get_glossary_dict().keys()) if self.glossary else [],
            forbidden_new_chars=self.config.forbidden_new_characters,
            avg_word_count_target=self.config.avg_words_per_chapter,
        )
        self.qa.system_instruction = f"""Bạn là Critic — phản biện chất lượng văn chương.
    Hãy chấm điểm chương {ch_num} trên thang 0-100.
    5 tiêu chí (mỗi tiêu chí 0-20):
    1. glossary_compliance: xưng hô, format tiêu đề
    2. pacing_score: nhịp độ, không lê thê
    3. consistency_score: nhất quán với outline
    4. character_voice: hội thoại phù hợp tính cách
    5. plot_coherence: cốt truyện logic, không plot hole"""

        review = self.qa.review(
            content=text,
            chapter_num=ch_num,
            attempt=attempt
        )
        return review.score.total_score, review.feedback

    # ── Arc: gợi ý kích thước arc ──

    async def _suggest_arc_size(self, start_ch: int, max_ch: int,
                                flow: str, profile: Optional[NovelProfile]) -> int:
        """AI gợi ý số chương cho arc này (optional, fallback = max_ch)"""
        if not profile:
            return min(max_ch, ARC_BATCH_SIZE)
        try:
            profile_section = profile.get_prompt_section()
            style_section = build_style_section(
                self.config.expansion_style,
                self.config.hallucination_direction,
                self.config.creativity_level
            )
            sp = f"""Bạn là Architect. Dựa vào profile và style đã chọn,
    hãy gợi ý số chương phù hợp cho arc bắt đầu từ chương {start_ch}
    (tối đa {max_ch}, tối thiểu 5).

    {profile_section}
    {style_section}

    Trả về JSON: {{"suggested": N, "reason": "..."}}"""
            raw, err = await self.translator.call_api(
                model=self.config.role_models.get("coordinator", "gemini-flash"),
                system_prompt=sp,
                user_content="Hãy gợi ý số chương.",
                temperature=0.3
            )
            if err:
                return min(max_ch, ARC_BATCH_SIZE)
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0]
            data = json.loads(raw.strip())
            suggested = int(data.get("suggested", ARC_BATCH_SIZE))
            reason = data.get("reason", "")
            self.log(f"📐 AI gợi ý: arc này {suggested} chương ({reason})")
            return max(5, min(suggested, max_ch))
        except Exception:
            return min(max_ch, ARC_BATCH_SIZE)

    # ── Write 1 arc (nhiều chapters) ──

    async def _write_arc(self, arc: ArcPlan, progress: GenProgress) -> int:
        """Viết tất cả chapters trong 1 arc, trả về số chapter thành công"""
        if self.app_state:
            self.app_state.gen_phase = GenPhase.WRITING

        # Lưu chapter notes (constraints) cho tất cả chapters trong arc
        for ch_plan in arc.chapters:
            save_chapter_note(self.temp_folder, ch_plan)

        arc_context = f"Arc: {arc.arc_title}, {len(arc.chapters)} chapters"
        success = 0

        for i, ch_plan in enumerate(arc.chapters):
            if self._stop_flag:
                self.log("⏹ Generation stopped by user")
                break

            # ── Real-time steer: check queue ──
            if self.steer_queue is not None:
                try:
                    while not self.steer_queue.empty():
                        cmd = self.steer_queue.get_nowait()
                        if cmd == "stop":
                            self._stop_flag = True
                            self.log("⏹ Steer: stop requested")
                            break
                        elif cmd.startswith("note:"):
                            note = cmd[5:].strip()
                            ch_plan["steer_note"] = note
                            self.log(f"📝 Steer note: {note}")
                        elif cmd == "slow" and self.config.expansion_style == "free":
                            self.config.expansion_style = "psychological"
                            self.log("🎯 Steer: pacing → slow (psychological)")
                        elif cmd == "fast" and self.config.expansion_style != "action":
                            self.config.expansion_style = "action"
                            self.log("🎯 Steer: pacing → fast (action)")
                        elif cmd.startswith("focus:"):
                            direction = cmd[6:].strip()
                            if direction in ("world", "character", "challenge", "free"):
                                self.config.hallucination_direction = direction
                                self.log(f"🎯 Steer: focus → {direction}")
                        else:
                            self.log(f"📋 Steer received: {cmd}")
                except asyncio.QueueEmpty:
                    pass
                except Exception as e:
                    self.log(f"⚠️ Steer error: {e}")
                if self._stop_flag:
                    break

            ch_num = ch_plan["num"]
            title = ch_plan["title"]
            display = f"Chương {ch_num:04d}: {title}"

            translated_dir = os.path.join(self.temp_folder, "translated")
            os.makedirs(translated_dir, exist_ok=True)
            out_path = os.path.join(translated_dir, f"chap_{ch_num:04d}.txt")
            if os.path.exists(out_path):
                try:
                    with open(out_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    if len(content) > 100:
                        self.log(f"⏭️  [{display}] Already written")
                        success += 1
                        progress.completed += 1
                        self._save_checkpoint(progress)
                        continue
                except Exception:
                    pass

            if self.app_state:
                self.app_state.current_chapter = ch_num

            if self.config.enable_enrichment:
                self.log(f"🎬  [{display}] Planning scenes...")
                scenes = self.scene_director.plan_scenes(
                    chapter_title=title,
                    chapter_num=ch_num,
                    required_events=ch_plan.get("events", [ch_plan.get("outline", "")]),
                    character_moments={c: "" for c in ch_plan.get("characters", [])},
                    tone="dark",
                    pacing="medium",
                    current_location=""
                )
                scenes_texts = []
                for scene in scenes:
                    if self._stop_flag:
                        break
                    enrich = EnrichmentProfile.suggest(
                        plot_goal=scene.plot_goal,
                        location_is_new=False,
                        has_dialogue=scene.sensory_focus == "auditory",
                        has_action=scene.sensory_focus == "action",
                        has_emotional_stakes=scene.sensory_focus == "psychological",
                        sensory_focus=scene.sensory_focus
                    )
                    scene.enrichment_types = [t.value for t in enrich.types]
                    enrich_section = EnrichmentProfile.get_prompt_section(enrich.types)
                    scene_text, scene_err = await self._write_scene_async(scene, enrich_section)
                    if scene_err:
                        self.log(f"   ⚠️ Scene {scene.scene_index} error: {scene_err}")
                        scene_text = f"[Scene {scene.scene_index} failed]"
                    scenes_texts.append((scene.scene_index, "", scene_text))
                best_text = SceneDirector.merge_scenes(scenes_texts)
                best_score = 70
            else:
                self.log(f"✍️  [{display}] Writing...")
                best_text = ""
                best_score = -1
                for attempt in range(1, 3):
                    if self._stop_flag:
                        break
                    is_enforcement = (attempt == 2)
                    text, error = await self._write_chapter_async(ch_plan, arc_context, is_enforcement)
                    if error:
                        self.log(f"   ❌ Writer error: {error}")
                        if attempt == 1:
                            await asyncio.sleep(2)
                            continue
                        break
                    if self.app_state:
                        self.app_state.gen_phase = GenPhase.REVIEWING
                    score, feedback = self._review_chapter(ch_num, text, ch_plan, attempt)
                    self.log(f"   📊 Score: {score}/100" + (" (PASS)" if score >= 70 else " (FAIL)"))
                    if score > best_score:
                        best_score = score
                        best_text = text
                    if score >= 70:
                        break

            if best_text and best_score >= 0:
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(best_text)
                success += 1
                if best_score >= 60:
                    try:
                        self.memory.save_chapter_summary(ch_num, best_text)
                    except Exception:
                        pass
                status = "✅" if best_score >= 70 else "⚠️"
                self.log(f"{status} [{display}] Saved (score={best_score})")
            else:
                self.log(f"❌ [{display}] Failed to write")

            progress.completed += 1
            progress.chapter_titles[ch_num] = title
            self._save_checkpoint(progress)

        return success

    # ── Main loop (multi-arc) ──

    async def run_async(self, start_chapter: int, num_chapters: int,
                        flow: str = "continue",
                        spinoff_character: str = "",
                        profile: Optional[NovelProfile] = None) -> Tuple[int, int]:
        """Main coordinator loop: multi-arc → mỗi arc plan + write + checkpoint"""
        self.log(f"🚀 Generation started: {flow}, {num_chapters} chapters from {start_chapter}")

        # Resume từ checkpoint nếu có
        progress = self._load_checkpoint()
        if progress:
            self.log(f"📦 Resuming from checkpoint: arcs={progress.arcs_completed}, "
                     f"chaps={progress.completed}/{progress.total_chapters}")
            remaining = progress.total_chapters - progress.completed
            current_ch = progress.start_chapter + progress.completed
            completed_base = progress.completed
            if remaining <= 0:
                self.log("✅ All chapters already generated")
                return progress.total_chapters, progress.total_chapters
        else:
            progress = GenProgress(
                flow=flow,
                spinoff_character=spinoff_character,
                start_chapter=start_chapter,
                total_chapters=num_chapters
            )
            self._save_checkpoint(progress)
            remaining = num_chapters
            current_ch = start_chapter
            completed_base = 0

        total_done = completed_base
        total_attempted = completed_base

        # ── Volume Outline: lazy — chỉ plan 2 volume đầu ──
        if not progress.volumes:
            initial_plan = await self._plan_volumes_async(start_chapter, num_chapters, profile)
            progress.volumes = initial_plan[:2]
            self._save_checkpoint(progress)
        volumes = progress.volumes

        # Multi-arc loop
        while remaining > 0:
            # Rolling plan: plan thêm volume nếu sắp hết
            total_planned = sum(v.get("num_chapters", 0) for v in volumes)
            planned_end = start_chapter + total_planned
            if current_ch >= planned_end - ARC_BATCH_SIZE * 2 and remaining > 0:
                more = await self._plan_volumes_async(current_ch, remaining, profile)
                if more:
                    volumes.extend(more)
                    progress.volumes = volumes
                    self._save_checkpoint(progress)
                    self.log(f"📚 Extended: +{len(more)} volumes ({total_planned}→{sum(v.get('num_chapters',0) for v in volumes)} ch)")

            if self._stop_flag:
                self.log("⏹ Generation stopped by user")
                break

            # Xác định volume hiện tại
            vol_context = ""
            for v in volumes:
                v_start = v.get("start_chapter", start_chapter)
                v_end = v_start + v.get("num_chapters", 0)
                if v_start <= current_ch < v_end:
                    vol_title = v.get("title", "")
                    vol_theme = v.get("theme", "")
                    vol_context = f"{vol_title} (theme: {vol_theme})" if vol_title else ""
                    break

            batch = min(remaining, ARC_BATCH_SIZE)

            # Gợi ý arc size từ AI
            if self.app_state:
                self.app_state.gen_phase = GenPhase.PLANNING
            suggested = await self._suggest_arc_size(current_ch, batch, flow, profile)
            actual_batch = min(suggested, remaining)
            self.log(f"📐 Arc batch: {actual_batch} chapters (suggested {suggested}, remaining {remaining})")

            # Plan arc với volume context
            arc = await self._plan_arc_async(current_ch, actual_batch, flow, spinoff_character, profile, volume_context=vol_context)
            progress.arc_plans.append(asdict(arc))
            self._save_checkpoint(progress)
            self.log(f"📋 Arc: {arc.arc_title} ({len(arc.chapters)} chapters)")

            # Write arc
            arc_success = await self._write_arc(arc, progress)
            total_done += arc_success
            total_attempted += len(arc.chapters)
            progress.arcs_completed += 1
            self._save_checkpoint(progress)

            # Advance cho arc tiếp theo
            remaining -= actual_batch
            current_ch += actual_batch

            self.log(f"📊 Progress: {total_done}/{num_chapters} chapters done")

        if self.app_state:
            self.app_state.gen_phase = GenPhase.COMPLETE
        self.log(f"🎉 Generation complete: {total_done}/{num_chapters} chapters")
        return total_done, total_attempted

    def run(self, start_chapter: int, num_chapters: int,
            flow: str = "continue",
            spinoff_character: str = "",
            profile: Optional[NovelProfile] = None) -> Tuple[int, int]:
        """Wrapper đồng bộ"""
        return asyncio.run(self.run_async(
            start_chapter, num_chapters, flow, spinoff_character, profile
        ))
