# Novel Translation System v3.5

Hệ thống dịch thuật tiểu thuyết Trung-Việt theo mô hình **Tam Quyền Phân Lập (Architect - Writer - Critic)**, tích hợp bộ nhớ ngữ cảnh RAG, quản lý thế giới động, và biên soạn Ebook PDF tự động.

> **Status**: Production Ready
> **Python**: 3.10+
> **TUI**: Textual 8.x

---

## Mục lục

- [Tính năng](#tính-năng)
- [Cấu trúc thư mục](#cấu-trúc-thư-mục)
- [Yêu cầu hệ thống](#yêu-cầu-hệ-thống)
- [Hướng dẫn sử dụng](#hướng-dẫn-sử-dụng)
- [Kiến trúc hệ thống](#kiến-trúc-hệ-thống)
- [Luồng dữ liệu](#luồng-dữ-liệu)
- [Cấu hình](#cấu-hình)
- [Xử lý lỗi & Fallback](#xử-lý-lỗi--fallback)
- [Khắc phục sự cố](#khắc-phục-sự-cố)

---

## Tính năng

| Tính năng | Mô tả |
|-----------|-------|
| **Tam Quyền Phân Lập** | 3 Agent chuyên biệt: Architect (lập kế hoạch) → Writer (dịch thuật) → Critic (đánh giá chất lượng) |
| **Interactive TUI** | Giao diện Textual 6 tabs: Dashboard, Translate, Generate, Style, Models, Log |
| **Style Director** | Chọn văn phong (6 options), hướng mở rộng (4 options), mức sáng tạo (1-3) → inject vào prompt |
| **Smart Director** | AI đọc NovelProfile → gợi ý hướng mở rộng kèm tag (Đề xuất/Có lẽ/Ổn/Khó/Không khả thi/Mâu thuẫn) + chat giải thích |
| **Multi-Arc Generation** | Tự động chia generation 500+ chương thành nhiều arc nhỏ (mỗi arc ~20 chương), checkpoint theo arc |
| **Router API v2** | Ủy thác xoay vòng key, xử lý 429, quota cho upstream router |
| **Fail-safe Loop** | Tự sửa lỗi 3 lượt (lượt 1-2 sáng tạo, lượt 3 cưỡng chế temp=0.0). Nếu vẫn lỗi → cách ly vào quarantine log |
| **RAG Context Engine** | Bộ nhớ ngữ cảnh tích lũy (Memory Block 10 chương, Milestone 50 chương) |
| **Dynamic Glossary** | Từ điển thuật ngữ động tự học từ chương đã dịch |
| **Character Tracking** | Theo dõi trạng thái tâm lý, chấn thương, xưng hô nhân vật |
| **World Manager** | Quản lý địa danh, bản đồ di chuyển, phân tích bối cảnh RAG |
| **Ebook Maker** | Biên soạn PDF khổ A5 (WeasyPrint) kèm bìa, mục lục, ảnh ending |
| **Genre Mixer** | Pha trộn thể loại (Sci-fi + Huyền học phương Đông) |
| **AI World Builder** | Tự động phát hiện patterns, đề xuất cập nhật world_config |
| **NovelProfile** | Export 6 nguồn dữ liệu → 1 JSON compact, inject vào prompt thay vì context khủng |
| **ModelRegistry** | Singleton quản lý model + context window từ Router API, fallback hardcode |
| **AppState** | State machine cho Translation & Generation (idle → loading → translating → complete) |
| **Coordinator Loop** | Generation mode: continue từ chương cuối hoặc spin-off nhân vật |

---

## Cấu trúc thư mục

```
├── main.py                          # Entry point (Interactive CLI UI v3.5)
├── run.ps1                          # Script PowerShell kích hoạt .venv và chạy
├── run_tui.ps1                      # Script chạy Textual TUI v3.5
│
├── docs/                            # [Tài liệu] Toàn bộ documentation tập trung tại đây
│   ├── README.md                    # Master document (file này - tổng quan, usage, cấu hình)
│   └── ARCHITECTURE.md              # Kiến trúc chi tiết (module, prompt, design decisions)
│
├── refactor_oop_gemini_trans_api/   # [OOP Core] Toàn bộ logic dịch thuật
│   ├── __init__.py                  # Package root, re-export key classes
│   ├── main.py                      # CLI entry point (legacy)
│   │
│   ├── config/                      # [Cấu hình] API, model, endpoint
│   │   ├── config.py                # TranslatorConfig - cấu hình toàn cục
│   │   ├── api_manager.py           # Shell API mỏng (APIManagerV2)
│   │   └── model_registry.py        # Singleton model + context window
│   │
│   ├── data/                        # [Dữ liệu] Load/export profile
│   │   ├── content_loader.py        # ContentLoader & ContentMerger
│   │   ├── novel_profile.py         # NovelProfile exporter (6 nguồn → 1 JSON)
│   │   └── word_stats.py            # Word count auto-scan
│   │
│   ├── memory/                      # [Bộ nhớ] Context RAG
│   │   ├── memory_manager.py        # Block Memory & Cumulative Memory
│   │   └── enrichment_profiles.py   # EnrichmentType + EnrichmentProfile
│   │
│   ├── output/                      # [Đầu ra] Ebook + Genre
│   │   ├── ebook_maker.py           # Ebook PDF (WeasyPrint A5)
│   │   └── genre_mixer.py           # Runtime genre profile injection
│   │
│   ├── plan/                        # [Lập kế hoạch] Director & Pacing
│   │   ├── chapter_director.py      # Outline batch 10 chương + Extra chapters
│   │   ├── note_utils.py            # Volume outline + character lock
│   │   ├── pacing_controller.py     # Điều khiển nhịp độ
│   │   └── scene_director.py        # SceneDirector plan_scenes + merge_scenes
│   │
│   ├── review/                      # [Đánh giá] QA & Critic
│   │   ├── quality_assurance.py     # QA chấm điểm & tự sửa
│   │   └── ai_enhanced_qa.py        # QA nâng cao sampling
│   │
│   ├── state/                       # [Trạng thái] State machine
│   │   └── app_state.py             # State machine Translate/Generation
│   │
│   ├── style/                       # [Văn phong] Style & Smart Director
│   │   ├── style_director.py        # Prompt templates style/direction/creativity
│   │   └── smart_director.py        # AI analyze profile → suggest direction
│   │
│   ├── trackers/                    # [Theo dõi] Nhân vật, phong cách, thực thể
│   │   ├── character_tracker.py     # Tâm lý, chấn thương, xưng hô
│   │   ├── style_learner.py         # Học phong cách dịch từ ví dụ
│   │   └── entity_database.py       # CSDL thực thể (Entity, Creature, Power, Weapon)
│   │
│   ├── tui/                         # [TUI] Textual-based interface
│   │   └── app.py                   # NovelTranslatorApp (6 tabs)
│   │
│   ├── workflow/                    # [Quy trình] Dịch thuật & Generation
│   │   ├── translator_core.py       # Nhân dịch thuật Async OpenAI + PromptBuilder
│   │   ├── workflow_v3.py           # Workflow Tam Quyền + Fail-safe
│   │   ├── coordinator.py           # GenerationCoordinator multi-arc loop + checkpoint
│   │   └── expansion_engine.py      # Smart Expansion Engine + StoryMap + ChapterNamer
│   │
│   └── world/                       # [Thế giới] Quản lý bối cảnh
│       ├── manager.py               # World orchestrator
│       ├── glossary.py              # Từ điển thuật ngữ động
│       ├── auto_learner.py          # Tự học địa danh, bối cảnh
│       ├── ai_analysis_pipeline.py  # Phân tích bối cảnh sâu (RAG)
│       ├── ai_world_builder.py      # AI detect patterns, suggest world updates
│       └── map_intelligence.py      # Bản đồ di chuyển nhân vật
│
├── data/                            # [Input] Dữ liệu đầu vào
│   ├── Truyen_Hoan_Chinh_Fixed.txt  # Truyện thô đầu vào
│   ├── Danh_sach_ten_chuong.txt     # Danh sách tên chương gốc
│   ├── glossary.txt                 # Từ điển thuật ngữ gốc
│   ├── cover.jpg                    # Ảnh bìa
│   ├── end_cover.png, end_588.png   # Ảnh ending
│   ├── part 1-5.txt                 # Các phần phụ trợ
│   └── Truyen_Dich_Hoan_Chinh.txt   # Bản dịch hoàn chỉnh (có thể copy từ output)
│
├── output/                          # [Output] Dữ liệu đầu ra
│   ├── api_config.json              # Cấu hình API đã lưu
│   ├── temp_chapters/               # Chương dịch tạm thời
│   ├── memory_store/                # Bộ nhớ ngữ cảnh tích lũy
│   ├── memory_store_old/            # Bộ nhớ cũ (archive)
│   └── temp_chapters_old/           # Chương tạm cũ (archive)
│
└── legacy/                          # [Legacy] Mã nguồn cũ - không chạy
    ├── gemini_translator_2_oneshot.py
    ├── clean_and_refill_chapters.py
    ├── main_s4.py, workflow_s4.py
    ├── s4_director.py, s4_context_builder.py
    └── ...
```

---

## Yêu cầu hệ thống

- **Python 3.10+**
- **Môi trường ảo** (`.venv`) với:
  ```
  pip install google-genai textual
  ```
- **Router API v2** upstream (xử lý pool key, 429, quota)

---

## Hướng dẫn sử dụng

### Khởi chạy nhanh

**Tự động (khuyên dùng):** script tự tạo `.venv` + cài deps + chạy:
```powershell
./run.ps1               # Textual TUI (mặc định)
./run.ps1 -Cli          # CLI mode (legacy)
```

### Textual TUI Hotkeys

| Phím | Chức năng |
|------|-----------|
| `1` | Dashboard - thông tin project, export NovelProfile |
| `2` | Translate - nhập dải chương, số luồng, progress bar, log |
| `3` | Generate - continue/spin-off, chọn nhân vật, arc preview |
| `4` | Style - chọn văn phong, AI phân tích hướng mở rộng, chat, mức sáng tạo |
| `5` | Models - xem danh sách model + context window, chọn per-role |
| `6` | Log - hệ thống log streaming |
| `q` | Thoát |

### CLI mode (refactor_oop_gemini_trans_api/main.py)

```powershell
python refactor_oop_gemini_trans_api/main.py --cli -s 100 -e 200 -t 3
python refactor_oop_gemini_trans_api/main.py --cli --merge               # Chỉ merge
python refactor_oop_gemini_trans_api/main.py --cli --expand               # Bật expansion mode
```

Tham số:
- `-s/--start`, `-e/--end`: Dải chương
- `-t/--threads`: Số luồng song song
- `--expand`: Bật expansion mode
- `--no-glossary`: Tắt dynamic glossary
- `--no-memory`: Tắt memory system
- `--no-lite-critic`: Tắt chế độ Critic thu gọn
- `--merge`: Chỉ gộp output, không dịch

---

## Kiến trúc hệ thống

> Chi tiết: `docs/ARCHITECTURE.md` — module reference, prompt engineering, data schemas.

### Tam Quyền Phân Lập (Three-Power Separation)

```
┌──────────────────────────────────────────────────────────────┐
│                     VÒNG LẶP DỊCH THUẬT                      │
│                                                              │
│   [Architect]              [Writer]              [Critic]    │
│   Lập kế hoạch    ───►    Thực thi dịch  ───►   Đánh giá QA │
│   + Memory, World          Temp=0.3 (lượt 1-2)  Chấm điểm   │
│   + Glossary, Style        Temp=0.0 (lượt 3)    Phản hồi    │
│       ▲                                        lỗi chi tiết  │
│       └───────────────────────────────────────────┘          │
│                 (Nếu Score < 80, quay lại Writer)            │
└──────────────────────────────────────────────────────────────┘
```

### Call Graph

```
main.py
  ├── config/api_manager.py          (APIManagerV2.fetch_available_models_async)
  ├── output/ebook_maker.py          (EbookMaker.build_pdf)
  │     └── data/content_loader.py   (ContentMerger.merge_chapters)
  └── workflow/workflow_v3.py        (WorkflowV3Runner.run_async)
        └── AgenticTranslator.process_chapter_with_qa_async
              ├── plan/chapter_director.py   (prepare_batch_framework_async)
              ├── workflow/translator_core.py (ChapterTranslator.call_api)
              ├── review/quality_assurance.py (QualityAssurance.review)
              ├── memory/memory_manager.py    (save_chapter_summary)
              └── world/manager.py            (WorldManager.learn_chapter)
```

---

## Luồng dữ liệu

```
[data/]                    [refactor_oop_gemini_trans_api/]           [output/]
   │                              │                                        │
   ├─ Truyen_Hoan_Chinh_Fixed.txt │                                        │
   ├─ Danh_sach_ten_chuong.txt   ─► ContentLoader                         │
   ├─ glossary.txt                │                                        │
   │                              ▼                                        │
   │                       ChapterDirector                                 │
   │                       (Batch Framework 10 chương)                     │
   │                              │                                        │
   │                              ▼                                        │
   │                       AgenticTranslator                               │
   │                       ┌──────────────┐                               │
   │                       │  Architect   │ ◄── Memory + World + Glossary │
   │                       ├──────────────┤                               │
   │                       │   Writer     │ ──► temp_chapters/chap_X.txt  │
   │                       ├──────────────┤                               │
   │                       │   Critic     │ ──► quarantine_chapters.log   │
   │                       └──────────────┘                               │
   │                              │                                        │
   │                              ▼                                        │
   │                       MemoryManager                                   │
   │                       (save_chapter_summary)                          │
   │                              │                                        │
   │                              ▼                                        │
   │                       EbookMaker                                      │
   │                       (merge → HTML → WeasyPrint)                    │
   │                              │                                        │
   └──────────────────────────────┼────────────────────────────────────────┘
                                  ▼
                     output/Dung_Chay_Noi_Nay_Khap_Noi_La_Quai_Vat.pdf
```

---

## Cấu hình

### Config keys (config/config.py)

| Key | Default | Mô tả |
|-----|---------|-------|
| `api_endpoint` | `http://127.0.0.1:58100/v1` | Endpoint Router API v2 |
| `auth_key` | `""` | Key xác thực (sticky sessions) |
| `model_architect` | `gemini-flash-lite` | Model cho Architect |
| `model_writer` | `gemini-flash` | Model cho Writer |
| `model_critic` | `gemini-flash` | Model cho Critic |
| `max_threads` | `1` | Số luồng song song |
| `retry_limit` | `6` | Số lần retry API |
| `enable_dynamic_glossary` | `True` | Bật/tắt glossary động |
| `enable_memory` | `True` | Bật/tắt bộ nhớ ngữ cảnh |
| `enable_enrichment` | `False` | Bật/tắt làm giàu có chủ đích (Generation Mode) |
| `enable_expansion` | `False` | Bật/tắt Expansion Mode |
| `expansion_style` | `giu_nguyen` | Văn phong: `balanced`/`action`/`psychological`/`descriptive`/`literary`/`giu_nguyen` |
| `hallucination_direction` | `free` | Hướng mở rộng: `free`/`world`/`character`/`challenge` |
| `creativity_level` | `2` | Mức sáng tạo: `1`/`2`/`3` |

Cấu hình được lưu tại `output/api_config.json`.

---

## Xử lý lỗi & Fallback

### Fail-safe Auto-Correction Loop

```
Score >= 80 ──► Lưu vào temp_chapters/
Score < 80  ──►
  ├── Lượt 1-2: Quay lại Writer (Temp=0.3, sáng tạo)
  └── Lượt 3: CƯỠNG CHẾ (Temp=0.0, dịch sát nghĩa)
        └── Vẫn < 80:
              ├── Chọn bản tốt nhất (Best-of-Three)
              ├── Chèn tag [QA_STATUS: FAILED]
              └── Đẩy vào quarantine_chapters.log
```

### Quarantine Log

Các chương không đạt QA sau 3 lượt được ghi vào `output/quarantine_chapters.log` kèm điểm số và phản hồi chi tiết để chỉnh sửa thủ công.

---

## Khắc phục sự cố

| Vấn đề | Giải pháp |
|--------|-----------|
| **429 Rate Limit** | Router API v2 xử lý tự động, hệ thống không tự quản lý cooldown |
| **WeasyPrint lỗi** | Đảm bảo GTK3 Runtime được cài đặt và trong PATH |
| **ImportError** | Chạy từ thư mục gốc project, đảm bảo `.venv` đã active |
| **API không kết nối** | Dùng menu `[5]` để cấu hình lại endpoint/key |
| **Dịch chậm** | Tăng `max_threads` |

### Debug

Kiểm tra file cấu hình: `output/api_config.json`
Kiểm tra model + context window: TUI tab Models `[5]`
Kiểm tra chương lỗi: tab Log `[6]` hoặc đọc `output/quarantine_chapters.log`
Export NovelProfile: Dashboard tab `[1]` → nút Export
Dịch lại từ đầu: tab Translate `[2]` → nhập dải chương mới

---

*Maintained by: Senior Architect & AI Platform Engineer*
*Last updated: 2026-06-27*
