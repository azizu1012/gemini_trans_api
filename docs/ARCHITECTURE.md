# Kiến Trúc Hệ Thống — Novel Translation Engine v3.5

> Tài liệu tham khảo kiến trúc chi tiết cho toàn bộ codebase.
> Dành cho: Contributor, Debug, Extension.

---

## Mục lục

- [Tổng quan kiến trúc](#tổng-quan-kiến-trúc)
- [Core Data Models](#core-data-models)
- [Module Reference](#module-reference)
- [Prompt Engineering](#prompt-engineering)
- [Pipeline Chi Tiết](#pipeline-chi-tiết)
- [Design Decisions](#design-decisions)

---

## Tổng quan kiến trúc

### Nguyên tắc cốt lõi

1. **Tuyến tính tuyệt đối (Strictly Linear Pipeline)** — Đọc, xử lý, và merge dựa trên vị trí vật lý trong file. Loại bỏ dictionary mapping số chương → tránh chapter collision.
2. **Tam Quyền Phân Lập** — Architect (plan) → Writer (execute) → Critic (review).
3. **Ủy thác hạ tầng** — Router API v2 xử lý key pool, rate limit, 429.
4. **Fail-safe Loop** — 3 lượt tự sửa, lượt cuối cưỡng chế temp=0.0.

### Layer Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        INTERFACE LAYER                           │
│  main.py (root) — Interactive CLI                              │
│  tui/app.py — Textual TUI v3.5                                 │
│  main.py — CLI + GUI mode                                      │
├──────────────────────────────────────────────────────────────────┤
│                        WORKFLOW LAYER                            │
│  workflow/workflow_v3.py — AgenticTranslator + WorkflowV3Runner │
│  workflow/expansion_engine.py — SmartExpansionEngine            │
│  workflow/coordinator.py — GenerationCoordinator                │
├──────────────────────────────────────────────────────────────────┤
│                     DOMAIN LOGIC LAYER                           │
│  workflow/translator_core.py — ChapterTranslator + PromptBuilder │
│  plan/ — ChapterDirector, PacingController, SceneDirector       │
│  review/ — QualityAssurance, AIEnhancedQA                       │
│  trackers/ — CharacterTracker, StyleLearner, EntityDB           │
│  world/ — WorldManager, Glossary, AutoLearner, AIPipeline       │
├──────────────────────────────────────────────────────────────────┤
│                     INFRASTRUCTURE LAYER                         │
│  config/config.py — TranslatorConfig                            │
│  config/api_manager.py — APIManagerV2                           │
│  config/model_registry.py — ModelRegistry (model + context)     │
│  data/content_loader.py — ContentLoader + ContentMerger         │
│  data/novel_profile.py — NovelProfile (6 nguồn → 1 JSON)        │
│  memory/memory_manager.py — MemoryManager                       │
│  output/ebook_maker.py — EbookMaker                             │
│  output/genre_mixer.py — GenreMixer                             │
│  state/app_state.py — AppState (Translate/Gen state machine)    │
│  style/style_director.py — Style/Direction/Creativity prompts   │
│  style/smart_director.py — AI analyze profile → suggest         │
└──────────────────────────────────────────────────────────────────┘
```

---

## Core Data Models

```python
# content_loader.py
@dataclass
class ChapterData:
    index: int                  # Chỉ mục vật lý trong file (1, 2, 3...)
    num: int                    # Số chương parse từ tiêu đề (tham khảo)
    title_raw: str              # Tiêu đề gốc
    content: str                # Nội dung thô
    previous_context: str = ""  # 500 từ cuối của chương vật lý trước đó

# workflow_v3.py
@dataclass
class TranslationResult:
    chapter_index: int
    status: str                 # "SUCCESS" | "FAILED" | "SKIPPED"
    translated_text: str
    final_score: int            # 0-100
    review_attempts: List[ReviewResult]
    total_attempts: int
    error_message: str

# quality_assurance.py
@dataclass
class QualityScore:
    glossary_compliance: int    # 0-20
    pacing_score: int           # 0-20
    consistency_score: int      # 0-20
    character_voice: int        # 0-20
    plot_coherence: int         # 0-20
    # + detail error lists
    @property
    def total_score(self) -> int: pass
    @property
    def passed(self) -> bool: pass  # total_score >= 80

# chapter_director.py
@dataclass
class ChapterNote:
    chapter_num: int
    required_events: List[str]
    foreshadowing: List[Dict]
    character_moments: Dict[str, str]
    tone: str                   # dark, hopeful, tense, comedic
    pacing: str                 # slow, medium, fast, climax
```

---

## Module Reference

### 1. INFRASTRUCTURE LAYER

#### `config/config.py` (232 dòng)
- **`TranslatorConfig`** — Dataclass chứa toàn bộ cấu hình (API endpoint, model names, paths, feature flags)
- **`GlossaryEntry`** — Entry cho glossary tĩnh
- **`STATIC_GLOSSARY`** — Dict hardcode các thuật ngữ Trung-Việt (nhân vật, địa danh, xưng hô)
- Key methods: `load_api_config()`, `save_api_config()`

#### `config/api_manager.py` (82 dòng)
- **`APIManagerV2`** — Shell API tối giản:
  - `update_config(endpoint, key)` — Cập nhật endpoint/key
  - `fetch_available_models_async()` — GET `/v1/models` bất đồng bộ
  - `fetch_available_models()` — Đồng bộ
- Không xử lý key pool, không cooldown — ủy thác cho Router upstream

#### `config/model_registry.py` (112 dòng)
- **`ModelRegistry`** — Singleton quản lý danh sách model + context_window:
  - `fetch_async()` — GET `/v1/models`, parse `context_length` từ response
  - `fetch()` — Wrapper đồng bộ (dùng thread cho code sync)
  - `get_context_length(model_id)` — Trả về context window của model
  - `get_model_ids()` — Danh sách model alias
- Fallback: hardcode dict `HARDCODED_CONTEXT` nếu API ko trả context
- Cache TTL: 300s, refresh qua `force=True`

#### `data/content_loader.py` (194 dòng)
- **`ContentLoader`** — Đọc file raw, parse bằng regex `split(r'(### .+? ###)')`, tạo `List[ChapterData]` tuyến tính
  - `load_chapters()` — Parse file, áp dụng Sliding Token Window (500 từ cuối → `previous_context`)
  - `match_chapters()` — Alias tương thích ngược
- **`ContentMerger`** — Gộp file `chap_XXXX.txt` thành output:
  - `merge_chapters()` — Sort theo index, đánh lại số chương, clean markers

#### `data/novel_profile.py` (216 dòng)
- **`NovelProfile`** — Dataclass chứa toàn bộ tri thức đã học:
  - `glossary_terms/characters/species` — từ GlossaryManager
  - `auto_locations/characters/species/terms` — từ AutoWorldLearner
  - `character_states` — từ CharacterTracker
  - `style_examples/patterns/rules` — từ StyleLearner
  - `memory_blocks/cumulative` — từ MemoryManager (file-based)
  - `entities` — từ EntityDatabase
- **`NovelProfileExporter`** — Gom 6 nguồn → `output/novel_profile.json`
- **`get_prompt_section()`** — Trả về text ngắn gọn inject vào system prompt (giảm context)

#### `data/word_stats.py` (70 dòng)
- **`WordStats`** — Auto-scan word count từ temp chapters / raw file
- Cập nhật `config.avg_words_per_chapter` tự động

#### `memory/memory_manager.py` (384 dòng)
- **`MemoryManager`** — Quản lý bộ nhớ context:
  - `get_latest_memory(current_chapter)` — Trả về cumulative + block memory gần nhất
  - `check_and_trigger_memory(completed_chapter)` — Gọi sau mỗi chương, trigger block nếu đủ 10
  - `recover_missing_memories()` — Rà soát và tạo background thread cho block thiếu
  - `wait_for_background_tasks()` — Join tất cả thread
- Memory block: `memory_block_{start:04d}_{end:04d}.txt` (mỗi 10 chương)
- Cumulative: `cumulative_{milestone:04d}.txt` (mỗi 50 chương)
- Background thread an toàn với `threading.Lock()` và `_generation_lock`

#### `memory/enrichment_profiles.py` (138 dòng)
- **`EnrichmentType`** — Enum các kiểu làm giàu (character, environment, action, dialogue, lore)
- **`EnrichmentProfile`** — Profile cho từng scene, tích hợp SceneDirector

#### `output/ebook_maker.py` (369 dòng)
- **`EbookMaker`** — Render PDF A5 bằng WeasyPrint:
  - `parse_novel_file()` — Đọc output file, tách chapter
  - `generate_html(chapters)` — Tạo HTML: Cover → Info → TOC → Content → Ending
  - `build_pdf()` — Gọi `HTML.write_pdf()` với CSS A5
- CSS: Times New Roman, lề 20mm/15mm, bookmark, page counter
- GTK3 Runtime paths: auto-detect cho Windows

#### `output/genre_mixer.py` (141 dòng)
- **`GenreMixer`** — Load genre profile từ JSON, inject vào prompt:
  - `get_prompt_section()` — Trả về section prompt (Remake Engine rules, fusion pairs)
  - `get_qa_rules()` — Rules cho QA check
  - Thiết kế fallback: style_data/genre_profiles/ → data/genre_profile.json

#### `state/app_state.py` (59 dòng)
- **`AppState`** — State machine cho Translate & Generation:
  - `translate_phase`: `TranslatePhase` enum (idle→loading→translating→qa→complete→failed)
  - `gen_phase`: `GenPhase` enum (idle→planning→writing→reviewing→complete→failed)
  - `gen_flow`: `GenFlow` enum (continue, spin-off)
  - `is_busy` property — kiểm tra nếu đang chạy
  - `reset_translation()`, `reset_generation()` — Reset state

#### `style/style_director.py` (96 dòng)
- **`STYLE_PROMPTS`** — Dict 5 văn phong: `balanced`/`action`/`psychological`/`descriptive`/`literary`
- **`DIRECTION_PROMPTS`** — Dict 4 hướng mở rộng: `free`/`world`/`character`/`challenge`
- **`CREATIVITY_PROMPTS`** — Dict 3 mức sáng tạo (1-3)
- **`build_style_section(style, direction, creativity)`** — Ghép prompt section, skip style nếu `giu_nguyen`

#### `style/smart_director.py` (109 dòng)
- **`SmartDirector`** — Phân tích NovelProfile → gợi ý hướng mở rộng có tag:
  - `analyze(profile)` — Gọi AI phân tích, trả về JSON `[{direction, tag, reason, detail}]`
  - `chat(suggestion, profile)` — Chat giải thích 1 suggestion cụ thể
- **Tag system**: `de_xuat`, `co_le`, `on`, `kho`, `khong_kha_thi`, `mauthuan`

---

### 2. WORKFLOW LAYER

#### `workflow/workflow_v3.py` (358 dòng)
- **`AgenticTranslator`** — Translator agentic với 3 vai trò:
  - `_get_architecture_context(chapter)` — [ARCHITECT] Gom memory + world + glossary + sliding window
  - `_translate_with_context(chapter, context, feedback, is_enforcement)` — [WRITER] Gọi API async
  - `_review_translation(chapter, text, context, attempt)` — [CRITIC] Gọi QA review đồng bộ
  - `process_chapter_with_qa_async(chapter)` — Vòng lặp chính:
    1. Skip nếu đã dịch
    2. Architect → Writer → Critic loop (tối đa 3 lượt, trừ lite_critic = 1)
    3. Nếu < 80 → enforcement pass (temp=0.0)
    4. Nếu vẫn < 80 → quarantine + best-of-three
    5. Update memory + world (nếu score >= 60)
- **`WorkflowV3Runner`** — Điều phối async:
  - `run_async(tasks)` — Semaphore-based concurrency, prepare batch frameworks trước
  - `run(tasks)` — Wrapper đồng bộ

#### `workflow/expansion_engine.py` (1,348 dòng)
- **`SmartExpansionEngine`** — Động cơ mở rộng văn học:
  - `calculate_expansion_target(chapter, raw_length)` — Tính target ratio từ config và map potential
  - Quản lý SidePlots (tuyến truyện phụ)
  - CHAPTER_NAMER: Đặt tên chương sáng tạo dựa trên arc context
  - Map potential system: Điều chỉnh ratio theo địa danh (city, dungeon, etc.)
  - Auto-splitting: Tách chương khi output quá dài

#### `workflow/coordinator.py` (608 dòng — MỚI v3.5)
- **`GenerationCoordinator`** — Generation mode controller:
  - `_plan_arc_async()` — Architect lập outline N chương, inject style_section từ config
  - `_suggest_arc_size()` — AI gợi ý số chương cho arc dựa vào NovelProfile
  - `_write_arc()` — Viết tất cả chapters trong 1 arc (scene-level hoặc chapter-level)
  - `_write_chapter_async()` — Writer viết 1 chương (style + direction + creativity injected)
  - `_write_scene_async()` — Writer viết 1 scene (style + enrichment injected)
  - `_review_chapter()` — Critic chấm điểm
  - `run_async()` — Multi-arc loop: while remaining > 0 → suggest → plan → write → checkpoint
- **`ARC_BATCH_SIZE`** = 20 — max chapters mỗi arc
- **`ArcPlan`** — Dataclass arc: start_chapter, num_chapters, arc_title, chapters[]
- **`GenProgress`** — Checkpoint: total_chapters, arcs_completed, completed, current_arc_index

---

### 3. DOMAIN LOGIC LAYER

#### `workflow/translator_core.py` (356 dòng)
- **`PromptBuilder`** — Xây dựng system prompt phức tạp:
  - `build_system_prompt(memory, expansion, character, style, genre, ...)` — Ghép 6 phần prompt
  - Phần 0: Expansion instruction (x2, x3, x4)
  - Phần 1: Memory context
  - Phần 2: Glossary
  - Phần 2.5: Convert error handling (cực kỳ quan trọng)
  - Phần 3: Translation rules (xưng hô, format)
  - Phần 4: Remake Engine (Show Don't Tell, Psychological Rationalization, Logic Bridging)
  - Phần 5: Character states
  - Phần 6: Style guide + Genre profile
- **`ChapterTranslator`** — Gọi API dịch:
  - `call_api(model, system_prompt, user_content, temperature)` — Gọi `google-genai` async
  - `prepare_batch_framework_async(chapters)` — Gọi Architect model để tạo batch framework
  - Monkey-patch: Tắt web_search trong google-genai client

#### `plan/chapter_director.py` (1,460 dòng)
- **`ChapterDirector`** — Outline cho batch 10 chương:
  - `prepare_batch_framework_async(start, end, raw_chapters)` — Gọi API để tạo framework
  - `get_direction_for_translation(chapter_num)` — Lấy direction cho từng chương
  - `build_direction_prompt(raw_chapters, glossary, memory, previous_framework)` — Build prompt gọi Architect model
  - Framework chứa: required_events, foreshadowing, character_moments, pacing

#### `review/quality_assurance.py` (542 dòng)
- **`QualityAssurance`** (THE CRITIC):
  - `check_glossary_compliance(content)` — Kiểm tra từ điển, chữ Hán, xưng hô "Tôi"
  - `check_pacing(content)` — Phân tích nhịp độ qua action_words, dialogue_count, paragraph length
  - `check_consistency(content)` — Check location consistency với summary trước
  - `check_character_voice(content)` — Dialog phù hợp personality
  - `check_narrative_quality(content)` — [REMAKE ENGINE] Phát hiện câu kể phẳng (flat patterns), chuyển cảnh đột ngột
  - `review(content, chapter_num, attempt)` — Tổng hợp điểm 5 tiêu chí + narrative adjustment

#### `review/ai_enhanced_qa.py` (741 dòng)
- **`AIEnhancedQA`** — QA nâng cao:
  - Sampling ngẫu nhiên (không chạy mọi chapter)
  - Gọi API để phân tích plot holes sâu
  - Output feedback actionable cho production

#### `plan/pacing_controller.py` (454 dòng)
- Kiểm soát nhịp độ dựa trên cao trào
- Phân tích action/dialogue/description ratio
- Điều chỉnh prompt instruction theo pacing

#### `plan/scene_director.py` (108 dòng)
- **`SceneDirector`** — Chia chapter thành scenes:
  - `plan_scenes(chapter)` — Planner bẻ chapter → list scenes
  - `merge_scenes(chapters)` — Merge chapters vào arc
- **`EnrichmentProfile`** — Profile enrich cho từng scene

#### `plan/note_utils.py` (80 dòng)
- **Volume Outline**: Chia generation thành volumes (tập), inject volume_context vào prompt
- **Character Lock**: Cấm sinh nhân vật ngoài danh sách cho phép

---

### 4. TRACKERS

#### `trackers/character_tracker.py` (311 dòng)
- **`CharacterState`** — Trạng thái nhân vật: emotion, location, power, trauma, relationships
- **`CharacterTracker`** — Quản lý:
  - `ingest_ai_insights(chapter, ai_data)` — Cập nhật từ AI insights JSON
  - `get_character_context(chapter_num)` — Lấy context cho prompt (main characters + gần đây)
  - `save_state()` / `load_state()` — Persistence qua JSON

#### `trackers/style_learner.py` (538 dòng)
- **`StyleLearner`** — Học pattern dịch từ user:
  - `teach(source_cn, target_vn, category, explanation)` — Thêm ví dụ
  - `translate(text_cn)` — Dịch dựa trên direct + pattern (suffix/prefix)
  - `apply_to_text(text)` — Apply tất cả translations vào text
  - `get_prompt_instruction()` — Tạo instruction cho prompt
  - Pattern engine: `POWER_PATTERNS`, `CRYSTAL_PATTERNS`, `SUFFIX_RULES`, `PREFIX_RULES`
  - Pre-built: 之力 → Sức mạnh {}, 之晶 → Tinh thể {}
  - Singleton qua `get_style_learner()`

#### `trackers/entity_database.py` (447 dòng)
- **`EntityType(Enum)`** — Phân loại: character, creature, power, weapon, item, location
- **`Entity`** — Base dataclass: id, name, type, description, tags
- **`Character(Entity)`**, **`Creature(Entity)`**, **`Power(Entity)`**, **`Weapon(Entity)`** — Subclass chuyên biệt
- **`EntityDatabase`** — Quản lý CRUD + lookup + persistence qua JSON
- Singleton qua `get_entity_database()`
- Pre-built: `MAIN_CHARACTERS`, `CREATURES_DATABASE`, `POWERS_DATABASE`, `WEAPONS_DATABASE`

---

### 5. WORLD SYSTEM

#### `world/manager.py` (168 dòng)
- **`WorldManager`** — Orchestrator:
  - `ingest_ai_insights(chapter, ai_data)` — Update learner + character tracker + glossary
  - `get_full_context(chapter_num)` — Tổng hợp world + character + glossary context
  - `learn_from_translation(chapter, title, translated_text)` — Extract basic insights từ text
  - `export_data()` — Export all learned data

#### `world/glossary.py` (711 dòng)
- **`Glossary`** (alias `GlossaryManager`) — Từ điển động:
  - Storage: `characters`, `terms`, `species` dicts + `pending_*` + `dynamic_terms`
  - Thread-safe với `threading.Lock()`
  - `get_glossary_text()` — Legacy format cho prompt
  - `get_glossary_dict()` — Dict format cho QA
  - `scan_for_new_terms(content, chapter)` — AI auto-scan mỗi 10 chương → detect terms mới
  - `auto_clean_noise(chapter)` — Dọn dẹp term rác (usage_count < 2 && > 20 chapters cũ)
  - `suggest_character/term/species()` — AI suggest → pending → human approve
  - `translate_term()` / `get_character_name()` — Lookup

#### `world/auto_learner.py` (662 dòng)
- **`AutoWorldLearner`** — Tự học thế giới từ AI insights:
  - `LearnedLocation`, `LearnedCharacter`, `LearnedSpecies`, `LearnedTerm`
  - `ingest_ai_insights(chapter, ai_data)` — Cập nhật locations, characters, species, terms, events
  - `get_location_for_chapter(chapter)` / `get_characters_in_chapter(chapter)` — Query
  - `get_needs_review()` — Items cần human review
  - `get_world_summary()` — Text summary

#### `world/ai_analysis_pipeline.py` (932 dòng)
- Pipeline phân tích bối cảnh sâu (RAG): SummaryExtractor, SmartQA, RAGFeeder

#### `world/ai_world_builder.py` (456 dòng)
- **`AIWorldBuilder`** — Tự động detect patterns, suggest world_config updates
- Human review để approve suggestions

#### `world/map_intelligence.py` (494 dòng)
- Bản đồ di chuyển nhân vật, quản lý hierarchy địa danh

---

## Prompt Engineering

### System Prompt Structure (Generation Mode — Coordinator)

Phần được ghép bởi `build_style_section()` + `_plan_arc_async()` / `_write_chapter_async()`:

```
[Phần 0 - Style Section] — build_style_section(style, direction, creativity)
  • Văn phong: action / psychological / descriptive / literary / balanced (hoặc skip nếu giu_nguyen)
  • Hướng mở rộng: world / character / challenge / free
  • Mức sáng tạo: 1 (thấp) / 2 (trung bình) / 3 (cao)

[Enrichment Instruction (nếu enable)] — từ EnrichmentProfile.suggest()
  SceneDirector bẻ chapter → scenes → enrich từng scene với enrichment types cụ thể

[VAI TRÒ] — Nhà văn Mạt thế/Khoa huyễn

[Phần 1 - Memory Context] — Cumulative + Block memory từ MemoryManager

[Phần 2 - Glossary] — Từ điển bắt buộc từ GlossaryManager

[Phần 2.5 - Convert Error Handling] — QUAN TRỌNG NHẤT
  • "Từng cái" → "con" (biệt danh của Lâm Nhất)
  • Mụ mụ → mẹ, Ba ba → ba
  • Thanh âm → giọng nói, Khảo thí → thi cử

[Phần 3 - Translation Rules]
  • Xưng hô: Ta/Tao (KHÔNG dùng Tôi)
  • Biên soạn lại tên chương sáng tạo
  • Format: ### Chương X: [Tên mới] ###

[Phần 4 - Remake Engine] — Nâng cấp biểu đạt
  • Kỹ thuật 1: Psychological Rationalization (hợp lý hóa động cơ)
  • Kỹ thuật 2: Show Don't Tell (Action Beats + Sensory Details)
  • Kỹ thuật 3: Logic Bridging (bắc cầu di chuyển)

[Phần 5 - Character States] — Từ CharacterTracker

[Phần 6 - Style Guide + Genre Profile] — Từ StyleLearner + GenreMixer
```

### QA Scoring System

5 tiêu chí, mỗi tiêu chí 0-20 điểm, tổng 0-100:

| Tiêu chí | Trọng số | Check |
|----------|----------|-------|
| glossary_compliance | 20 | Chữ Hán còn sót, xưng hô sai, tên glossary chưa dịch |
| pacing_score | 20 | Độ dài chapter, action_words, dialogue, truncation check |
| consistency_score | 20 | Location consistency với summary trước |
| character_voice | 20 | Dialog phù hợp personality (cold → không cười haha) |
| plot_coherence | 20 | Format tiêu đề, ending cliffhanger |
| narrative_quality | -5/+5 | Flat pattern phạt, bonus không có |

PASS = tổng >= 80. Truncation (câu bị cắt cụt) → score = -35 (auto-fail).

---

## Pipeline Chi Tiết

### Khởi tạo (WorkflowV3Runner.__init__)
```
1. GlossaryManager(glob từ data/glossary.txt → JSON)
2. MemoryManager(config) → tạo memory_store/
3. ChapterTranslator(config, glossary, memory)
    → PromptBuilder(glossary)
    → ChapterDirector(framework_dir, batch_size=10)
    → QualityAssurance(glossary_dict)
    → CharacterTracker(character_states_dir)
    → WorldManager(temp_folder, auto_learn=True)
    → SmartExpansionEngine (nếu enable_expansion)
    → StyleLearner(style_data/) [nếu có]
    → GenreMixer(profile_path/fallback) [nếu có]
4. AgenticTranslator(config, glossary, memory, translator)
```

### Vòng lặp dịch (process_chapter_with_qa_async)
```
1. CHECK: File chap_XXXX.txt tồn tại và không lỗi → SKIP
2. ARCHITECT: _get_architecture_context()
    - memory.get_latest_memory(chapter.index)
    - director.get_direction_for_translation(chapter.index)
    - world_manager.get_full_context(chapter.index)
    - chapter.previous_context (500 từ cuối chương trước)
3. LOOP (max 3 lượt, hoặc 1 nếu lite_critic):
    a. WRITER: _translate_with_context() → await call_api()
       - Build system prompt (6+ phần)
       - Thêm revision_feedback nếu lượt > 1
       - Enforcement pass (lượt cuối): temp=0.0, thêm cưỡng chế
    b. CRITIC: _review_translation() → QA.review()
       - 5 checks + narrative quality
       - PASS (>=80) → break
       - FAIL → lưu revision_feedback, loop tiếp
4. KẾT QUẢ:
    - PASS: Lưu file, update memory + world
    - FAIL (sau 3 lượt): Lưu + tag lỗi + quarantine log
5. TRIGGER MEMORY (nếu đủ 10 chương):
    - Background thread tóm tắt block
    - Trigger cumulative tại mốc 50
```

### Vòng lặp Generation (coordinator.run_async — multi-arc)
```
1. INIT: Load checkpoint → resume hoặc khởi tạo mới
2. MULTI-ARC LOOP (while remaining > 0):
   a. SUGGEST ARC SIZE: AI gợi ý batch (5-20 chương) dựa trên NovelProfile
   b. ARCHITECT: _plan_arc_async(start_ch, batch, profile)
      - Inject style_section (văn phong + hướng + sáng tạo) vào system prompt
      - Trả về ArcPlan với chapters[]
   c. WRITE ARC: _write_arc(arc)
      - FOR each chapter in arc:
        - Nếu enable_enrichment:
          SceneDirector → EnrichmentProfile → _write_scene_async (style + enrich)
        - Nếu không:
          Loop 2 lượt: _write_chapter_async (style) → _review_chapter
        - Lưu file, update memory, checkpoint
   d. CHECKPOINT: lưu arcs_completed, completed, current_arc_index
   e. Advance: remaining -= batch, current_ch += batch
3. DONE
```

---

## Design Decisions

### 1. Strictly Linear Pipeline (Tuyến Tính Tuyệt Đối)
- **Vấn đề**: File trùng lặp chương 234 (Chapter Collision) do dùng dict mapping
- **Giải pháp**: Dùng index vật lý từ file (1, 2, 3...), bỏ num/ số chương
- **Hệ quả**: ContentLoader dùng Ordered List, merge sort theo index

### 2. Lite Critic Mode
- **Mặc định**: Chỉ chạy 1 lượt, không auto-correction loop
- **Đầy đủ**: 3 lượt + enforcement pass
- **Lý do**: Tiết kiệm API call cho production

### 3. Router API v2
- **Quyết định**: Không quản lý key pool, rate limit, quota local
- **Lý do**: Ủy thác cho upstream để đơn giản hóa code + tận dụng prompt caching
- **Hệ quả**: APIManagerV2 chỉ ~82 dòng (thin shell)

### 4. Remake Engine
- 3 kỹ thuật built-in: Psychological Rationalization, Show Don't Tell, Logic Bridging
- Có thể mở rộng qua GenreProfile JSON
- Đánh giá chất lượng narrative tự động qua `check_narrative_quality()`

### 5. Glossary Architecture
- **3 tầng**: Locked (hardcode) > AI Learned (dynamic) > Auto-detected (scan)
- **Pending review workflow**: AI suggest → human approve → locked
- **Auto-clean**: Xóa term rác (usage_count < 2, quá 20 chương)
- **Scan interval**: Mỗi 10 chương

### 6. Prompt Caching tối ưu
- System prompt lớn, user content thay đổi
- Router v2 xử lý sticky sessions để cache
- Tắt Google Search Grounding (tools=[]) để tránh lẫn link

---

*Maintained by: Senior Architect & AI Platform Engineer*
*Last updated: 2026-06-27 (line counts synced with codegraph)*
