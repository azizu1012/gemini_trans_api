import os, sys, contextlib, asyncio, time, json, glob, re
from typing import Optional, Dict, List, Any, cast

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.screen import Screen, ModalScreen
from textual.widgets import (
    Header, Footer, Button, Input, Select, Label, RichLog,
    ProgressBar, Static, DataTable, Checkbox, RadioSet, RadioButton,
    TabbedContent, TabPane,
)

from ..config.config import TranslatorConfig
from ..config.api_manager import APIManagerV2
from ..config.model_registry import ModelRegistry, model_registry, HARDCODED_CONTEXT
from ..data.novel_profile import NovelProfileExporter, NovelProfile
from ..state.app_state import AppState, TranslatePhase, GenPhase, GenFlow
from ..data.content_loader import ContentLoader, ContentMerger
from ..style.smart_director import SmartDirector
from ..style.style_director import (
    build_style_section, STYLE_LABELS, DIRECTION_LABELS,
    CREATIVITY_LABELS, TAG_LABELS, STYLE_PROMPTS, DIRECTION_PROMPTS,
)
from ..workflow.workflow_v3 import WorkflowV3Runner, AgenticTranslator
from ..output.ebook_maker import EbookMaker
from ..workflow.coordinator import GenerationCoordinator, ArcPlan
from ..data.novel_importer import NovelImporter


class TUILogRedirector:
    def __init__(self, app, log_widget_id: str):
        self.app = app
        self.log_widget_id = log_widget_id
        self.stdout = sys.stdout
        self.buffer = ""

    def write(self, string):
        self.stdout.write(string)
        self.buffer += string
        if "\n" in self.buffer:
            lines = self.buffer.split("\n")
            for line in lines[:-1]:
                self.app.call_from_thread(self._write_to_widgets, line)
            self.buffer = lines[-1]

    def _write_to_widgets(self, line):
        try:
            try:
                system_log = self.app.query_one("#system_log", RichLog)
                system_log.write(line)
            except Exception:
                pass
            try:
                screen_log = self.app.query_one(f"#{self.log_widget_id}", RichLog)
                screen_log.write(line)
            except Exception:
                pass
        except Exception:
            pass

    def flush(self):
        self.stdout.flush()


@contextlib.contextmanager
def redirect_stdout_to_tui(app, log_widget_id: str):
    redirector = TUILogRedirector(app, log_widget_id)
    old_stdout = sys.stdout
    sys.stdout = redirector
    try:
        yield
    finally:
        sys.stdout = old_stdout


class NovelTranslatorApp(App[None]):
    ALLOW_SELECT = False
    config: TranslatorConfig
    api_manager: APIManagerV2
    app_state: AppState
    _stop_flag: bool
    _coordinator: Optional[GenerationCoordinator]
    _smart_director: SmartDirector

    CSS = """
    Screen { padding: 1; }
    #title { text-style: bold; text-align: center; margin-bottom: 1; }
    DataTable { height: 12; }
    RichLog { border: solid $primary; height: 20; }
    ProgressBar { margin: 1 0; }
    .role_row { height: 3; align: left middle; }
    .role_label { width: 14; }
    .role_select { width: 30; }
    Button { margin: 1 1; }
    Input { margin: 0 0 1 0; }
    #suggestions_area { height: 10; overflow-y: auto; }
    #style_preview { border: solid $primary; padding: 1; min-height: 3; }
    #gen_style_current { padding: 1; background: $surface; }
    #gen_arc_preview { min-height: 4; }
    TranslateScreen Horizontal, GenerateScreen Horizontal { height: 28; }
    TranslateScreen ScrollableContainer, GenerateScreen ScrollableContainer { width: 50%; height: 100%; border-right: tall $primary; padding-right: 1; }
    TranslateScreen Vertical, GenerateScreen Vertical { width: 50%; height: 100%; }
    #translate_log, #gen_log { height: 100%; }
    """

    BINDINGS = [
        Binding("1", "switch_tab('dashboard')", "Dashboard"),
        Binding("2", "switch_tab('translate')", "Translate"),
        Binding("3", "switch_tab('generate')", "Generate"),
        Binding("4", "switch_tab('style')", "Style"),
        Binding("5", "switch_tab('models')", "Models"),
        Binding("6", "switch_tab('log')", "Log"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self):
        super().__init__()
        self.config = TranslatorConfig()
        self.config.load_api_config()
        self.api_manager = APIManagerV2(self.config)
        self.app_state = AppState()
        model_registry.configure(self.config.api_endpoint, self.config.auth_key)
        self._stop_flag = False
        self._coordinator = None
        self._smart_director = SmartDirector(self.config.api_endpoint, self.config.auth_key)

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent(initial="dashboard"):
            with TabPane(" Dashboard", id="dashboard"):
                yield Dashboard()
            with TabPane(" Translate", id="translate"):
                yield TranslateScreen()
            with TabPane(" Generate", id="generate"):
                yield GenerateScreen()
            with TabPane(" Style", id="style"):
                yield StyleScreen()
            with TabPane(" Models", id="models"):
                yield ModelConfigScreen()
            with TabPane(" Log", id="log"):
                yield LogScreen()
        yield Footer()

    def on_mount(self):
        self.log_msg("Novel Translation System v3.5 started")
        self.log_msg(f"API: {self.config.api_endpoint}")
        self.log_msg(f"Models: {self.config.role_models}")
        self.action_scan_chapters()

    @work(name="scan_raw_chapters", group="scan", exit_on_error=False)
    async def action_scan_chapters(self):
        self.log_msg("Scanning raw chapters to determine range...")
        loop = asyncio.get_running_loop()
        loader = ContentLoader(self.config)
        try:
            all_chapters = await loop.run_in_executor(None, loader.match_chapters)
            if all_chapters:
                max_idx = max(ch.index for ch in all_chapters)
                min_idx = min(ch.index for ch in all_chapters)
                self.log_msg(f"Scan complete: found {len(all_chapters)} chapters (index {min_idx} to {max_idx})")
                self.config.start_chapter = min_idx
                self.config.end_chapter = max_idx
                try:
                    ts = self.query_one(TranslateScreen)
                    in_start = ts.query_one("#in_start", Input)
                    in_end = ts.query_one("#in_end", Input)
                    if in_start.value == "1" or in_start.value == "":
                        in_start.value = str(min_idx)
                    if in_end.value == "9999" or in_end.value == "":
                        in_end.value = str(max_idx)
                except Exception:
                    pass
            else:
                self.log_msg("Scan complete: no chapters found in raw file")
        except Exception as e:
            self.log_msg(f"Error scanning raw chapters: {e}")

    def log_msg(self, msg: str):
        formatted = f"[{time.strftime('%H:%M:%S')}] {msg}"
        LogScreen._log_lines.append(formatted)
        try:
            log_w = self.query_one("#system_log", RichLog)
            log_w.write(formatted)
        except Exception:
            pass

    def app_log(self, msg: str):
        self.log_msg(msg)

    def action_switch_tab(self, tab: str):
        self.query_one(TabbedContent).active = tab

    def run_export_novel_profile(self):
        self.log_msg("Exporting NovelProfile...")
        exporter = NovelProfileExporter(self.config)
        path = exporter.export()
        self.log_msg(f" NovelProfile exported: {path}")

    @work(name="import_novel", group="import", exit_on_error=False)
    async def action_import_novel(self):
        if self.app_state.is_busy:
            self.log_msg(" System is currently busy!")
            return
        
        self.app_state.translate_phase = TranslatePhase.LOADING
        try:
            self.query_one(Dashboard)._refresh()
        except Exception:
            pass

        try:
            self.log_msg(f"🚀 Bắt đầu import truyện: {self.config.raw_content_file}...")
            runner = WorkflowV3Runner(self.config)
            importer = NovelImporter(self.config, runner.translator, self.api_manager)
            importer.log = lambda msg: self.log_msg(f"[Importer] {msg}")
            
            result = await importer.run_async(
                file_path=self.config.raw_content_file,
                sample_every=5,
                max_samples=30,
                qa_review=True
            )
            
            self.log_msg("🎉 Quá trình import hoàn tất thành công!")
            self.log_msg(f"  • Số chương phân tích thực thể: {result.chapters_analyzed}")
            self.log_msg(f"  • Nhân vật tìm thấy: {len(result.characters_found)}")
            self.log_msg(f"  • Địa điểm tìm thấy: {len(result.locations_found)}")
            
            if result.qa_review:
                self.log_msg(f"📋 Điểm đánh giá QA: {result.qa_review.overall_score}/100")
                if result.qa_review.issues:
                    self.log_msg("⚠️ Vấn đề phát hiện:")
                    for issue in result.qa_review.issues:
                        self.log_msg(f"    - {issue}")
            
            self.action_scan_chapters()
            
        except Exception as e:
            self.log_msg(f"❌ Lỗi import truyện: {e}")
        finally:
            self.app_state.translate_phase = TranslatePhase.IDLE
            try:
                self.query_one(Dashboard)._refresh()
            except Exception:
                pass

    @work(name="refresh_models", group="models", exit_on_error=False)
    async def action_refresh_models(self):
        self.log_msg("Fetching model list from API...")
        models = await model_registry.fetch_async(force=True)
        if models:
            self.log_msg(f" Found {len(models)} models")
            for role, mid in self.config.role_models.items():
                self.config.role_max_context[role] = model_registry.get_context_length(mid)
        else:
            self.log_msg(" No models from API, using hardcoded fallback")
        try:
            ms = self.query_one(ModelConfigScreen)
            ms.refresh_ui(models)
        except Exception:
            pass

    def action_save_model_config(self, role_models: Dict[str, str], endpoint: Optional[str] = None, auth_key: Optional[str] = None):
        if endpoint is not None:
            self.config.api_endpoint = endpoint
        if auth_key is not None:
            self.config.auth_key = auth_key
        for role, mid in role_models.items():
            self.config.role_models[role] = mid
            self.config.role_max_context[role] = model_registry.get_context_length(mid)
        self.config.save_api_config(
            endpoint=self.config.api_endpoint,
            key=self.config.auth_key,
            role_models=role_models
        )
        self.log_msg(f" Saved config: API={self.config.api_endpoint}, Roles={role_models}")
        try:
            self.query_one(Dashboard)._refresh()
        except Exception:
            pass

    @work(name="translate", group="translate", exit_on_error=False)
    async def action_start_translate(self):
        if self.app_state.is_busy:
            self.log_msg(" Already busy")
            return
        try:
            ts = self.query_one(TranslateScreen)
            start = int(ts.query_one("#in_start", Input).value)
            end = int(ts.query_one("#in_end", Input).value)
            threads = int(ts.query_one("#in_threads", Input).value)
            lite_critic = ts.query_one("#chk_lite_critic", Checkbox).value
        except (ValueError, Exception):
            self.log_msg(" Invalid input")
            return

        self.config.start_chapter = start
        self.config.end_chapter = end
        self.config.max_threads = threads
        self.config.lite_critic = lite_critic
        self.config.save_api_config()
        self._stop_flag = False

        self.app_state.translate_phase = TranslatePhase.LOADING
        self.log_msg(f" Loading chapters {start}-{end}...")

        try:
            loader = ContentLoader(self.config)
            all_chapters = loader.match_chapters()
            chapters = [ch for ch in all_chapters if start <= ch.index <= end]

            if not chapters:
                self.log_msg(" No chapters in range")
                self.app_state.translate_phase = TranslatePhase.FAILED
                return

            self.app_state.total_chapters = len(chapters)
            self.app_state.translate_phase = TranslatePhase.TRANSLATING
            self.log_msg(f" Translating {len(chapters)} chapters with {threads} thread(s)")

            try:
                pb = ts.query_one("#translate_progress", ProgressBar)
                pb.total = len(chapters)
                pb.update(progress=0)
            except Exception:
                pb = None

            def on_progress(task, res):
                try:
                    pb = ts.query_one("#translate_progress", ProgressBar)
                    pb.advance(1)
                except Exception:
                    pass

            runner = WorkflowV3Runner(self.config)
            with redirect_stdout_to_tui(self, "translate_log"):
                success, total = await runner.run_async(chapters, on_progress=on_progress)

            self.app_state.translated_count = success
            self.app_state.failed_count = total - success
            self.app_state.translate_phase = TranslatePhase.COMPLETE
            self.log_msg(f" Done: {success}/{total} chapters")
            if pb:
                pb.update(progress=total)
        except Exception as e:
            self.app_state.translate_phase = TranslatePhase.FAILED
            self.app_state.error_message = str(e)
            self.log_msg(f" Translation failed: {e}")
        finally:
            try:
                self.query_one(Dashboard)._refresh()
            except Exception:
                pass

    @work(name="generate", group="gen", exit_on_error=False)
    async def action_start_generation(self):
        if self.app_state.is_busy:
            self.log_msg(" Already busy")
            return

        try:
            gs = self.query_one(GenerateScreen)
            radio = gs.query_one("#gen_flow_radio", RadioSet)
            is_spinoff = radio.pressed_index == 1
        except Exception:
            is_spinoff = False
        flow = GenFlow.SPINOFF if is_spinoff else GenFlow.CONTINUE
        char_name = self.query_one("#in_character", Input).value or "Lâm Nhất"
        try:
            num_chapters = int(self.query_one("#in_gen_chapters", Input).value or "5")
        except ValueError:
            num_chapters = 5

        self._stop_flag = False
        self.app_state.gen_flow = flow
        self.app_state.gen_phase = GenPhase.PLANNING
        flow_str = "spin-off" if flow == GenFlow.SPINOFF else "continue"
        self.log_msg(f" Generation: {flow_str} for {char_name}, {num_chapters} chapters")

        try:
            exporter = NovelProfileExporter(self.config)
            profile = exporter.load()
            if profile is None:
                self.log_msg(" No saved NovelProfile — exporting new...")
                path = exporter.export()
                profile = exporter.load()
                self.log_msg(f" NovelProfile exported: {path}")

            translated_dir = os.path.join(self.config.temp_folder, "translated")
            existing = glob.glob(os.path.join(translated_dir, "chap_*.txt"))
            if not existing:
                # Fallback cho các dự án cũ chưa phân tách thư mục
                existing = glob.glob(os.path.join(self.config.temp_folder, "chap_*.txt"))
            start_ch = 1
            if existing:
                nums = []
                for f in existing:
                    bn = os.path.basename(f)
                    m = re.search(r'chap_(\d+)', bn)
                    if m:
                        nums.append(int(m.group(1)))
                if nums:
                    start_ch = max(nums) + 1

            self.log_msg(f" Starting generation from chapter {start_ch}...")

            runner = WorkflowV3Runner(self.config)
            coordinator = GenerationCoordinator(
                self.config, runner.glossary, runner.memory, runner.translator, self.app_state
            )
            coordinator.log_callback = self.log_msg
            coordinator.steer_queue = asyncio.Queue()
            self._coordinator = coordinator

            with redirect_stdout_to_tui(self, "gen_log"):
                success, total = await coordinator.run_async(
                    start_chapter=start_ch,
                    num_chapters=num_chapters,
                    flow=flow_str,
                    spinoff_character=char_name if is_spinoff else "",
                    profile=profile
                )

            if self._stop_flag:
                self.app_state.gen_phase = GenPhase.IDLE
                self.log_msg(f" Stopped: {success}/{total} chapters done")
            else:
                self.app_state.gen_phase = GenPhase.COMPLETE
                self.log_msg(f" Generation complete: {success}/{total} chapters ({flow_str})")
        except Exception as e:
            self.app_state.gen_phase = GenPhase.FAILED
            self.app_state.error_message = str(e)
            self.log_msg(f"❌ Generation failed: {e}")
        finally:
            try:
                self.query_one(Dashboard)._refresh()
            except Exception:
                pass

    @work(name="suggest_chapters", group="gen", exit_on_error=False)
    async def action_suggest_chapters(self):
        self.log_msg(" Phân tích để gợi ý số chương...")
        exporter = NovelProfileExporter(self.config)
        profile = exporter.load()
        if profile is None:
            path = exporter.export()
            profile = exporter.load()
        sd = SmartDirector(self.config.api_endpoint, self.config.auth_key)
        try:
            results = await sd.analyze(profile)
            st = self.query_one("#gen_suggestion", Static)
            lines = ["Gợi ý từ AI:"]
            for s in results:
                d = DIRECTION_LABELS.get(s.get("direction", "?"), "?")
                t = TAG_LABELS.get(s.get("tag", "?"), "?")
                lines.append(f"  {d} ({t}): {s.get('reason', '')}")
            st.update("\n".join(lines))
        except Exception as e:
            self.log_msg(f" Lỗi gợi ý: {e}")


class AppScreen(ScrollableContainer):
    @property
    def app(self) -> NovelTranslatorApp:
        return cast(NovelTranslatorApp, super().app)

class AppModal(ModalScreen):
    @property
    def app(self) -> NovelTranslatorApp:
        return cast(NovelTranslatorApp, super().app)

CHAT_MODAL_HTML = """
<style>
.chat-log { overflow-y: auto; height: 20; border: solid $primary; padding: 1; }
.chat-input { width: 100%; }
.user-msg { color: $text; }
.ai-msg { color: $accent; }
</style>
"""


class ChatModal(AppModal):
    """Modal chat với AI về 1 suggestion"""

    def __init__(self, suggestion: Dict, smart_director: SmartDirector,
                 profile: Optional[NovelProfile]):
        super().__init__()
        self.suggestion = suggestion
        self.smart_director = smart_director
        self.profile = profile
        self.direction = suggestion.get("direction", "free")
        self.tag = suggestion.get("tag", "on")
        self.reason = suggestion.get("reason", "")
        self.detail = suggestion.get("detail", "")

    def compose(self):
        yield ScrollableContainer(
            Static(f"[bold]💬 Chat về: {DIRECTION_LABELS.get(self.direction, self.direction)} ({TAG_LABELS.get(self.tag, self.tag)})[/]"),
            Static(f"Lý do: {self.reason}"),
            Static(f"Phân tích: {self.detail}"),
            RichLog(id="chat_log", highlight=True, max_lines=100, wrap=True),
            Horizontal(
                Input(placeholder="Hỏi AI về đề xuất này...", id="chat_input"),
                Button("Gửi", id="btn_chat_send", variant="primary"),
            ),
            Button("Đóng", id="btn_chat_close", variant="default"),
        )

    def on_mount(self):
        self.query_one("#chat_log", RichLog).write("[System] Hãy hỏi về đề xuất này. Ví dụ: 'tại sao lại là Đề xuất?'")

    async def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn_chat_close":
            self.app.pop_screen()
        elif event.button.id == "btn_chat_send":
            inp = self.query_one("#chat_input", Input)
            question = inp.value.strip()
            if not question:
                return
            inp.value = ""
            log = self.query_one("#chat_log", RichLog)
            log.write(f"[white]Bạn: {question}[/]")
            log.write("[dim]AI đang trả lời...[/]")
            try:
                answer = await self.smart_director.chat(self.suggestion, self.profile)
                log.write(f"[accent]AI: {answer}[/]")
            except Exception as e:
                log.write(f"[red]Lỗi: {e}[/]")

    def on_input_submitted(self, event: Input.Submitted):
        if event.input.id == "chat_input":
            self.query_one("#btn_chat_send", Button).press()


class Dashboard(AppScreen):
    def compose(self):
        yield Static("[bold]Novel Translation System v3.5[/]", id="title")
        yield Static("", id="project_info")
        yield Static("", id="status_info")
        yield Horizontal(
            Button(" Export NovelProfile", id="btn_export", variant="primary"),
            Button(" Import Novel", id="btn_import", variant="success")
        )

    def on_mount(self):
        self._refresh()

    def _refresh(self):
        cfg = self.app.config
        self.query_one("#project_info", Static).update(
            f"Novel: Đừng Chạy, Nơi Này Khắp Nơi Là Quái Vật\n"
            f"API: {cfg.api_endpoint}\n"
            f"Roles: Arch={cfg.role_models.get('architect','?')} | "
            f"Writer={cfg.role_models.get('writer','?')} | "
            f"Critic={cfg.role_models.get('critic','?')}"
        )
        st = self.app.app_state
        self.query_one("#status_info", Static).update(
            f"Status: {st.status_line()}\n"
            f"Phase: Translate={st.translate_phase.value} | Gen={st.gen_phase.value}\n"
            f"Style: {STYLE_LABELS.get(cfg.expansion_style, cfg.expansion_style)} | "
            f"Dir: {DIRECTION_LABELS.get(cfg.hallucination_direction, cfg.hallucination_direction)} | "
            f"Creativity: {cfg.creativity_level}/3"
        )

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn_export":
            self.app.run_export_novel_profile()
        elif event.button.id == "btn_import":
            self.app.action_import_novel()


class TranslateScreen(AppScreen):
    def compose(self):
        yield Static("[bold] Translation Pipeline[/]", id="translate_title")
        yield Horizontal(
            ScrollableContainer(
                Label("Start chapter:"),
                Input(placeholder="1", id="in_start"),
                Label("End chapter:"),
                Input(placeholder="9999", id="in_end"),
                Label("Threads:"),
                Input(placeholder="1", id="in_threads"),
                Checkbox("Lite Critic (1-shot, no rewrites)", id="chk_lite_critic"),
                Button(" Start Translation", id="btn_start_translate", variant="primary"),
                Button(" Stop", id="btn_stop_translate", variant="error"),
            ),
            Vertical(
                ProgressBar(total=100, id="translate_progress", show_eta=True),
                RichLog(id="translate_log", highlight=True, max_lines=100, wrap=True),
            ),
        )

    def on_mount(self):
        cfg = self.app.config
        self.query_one("#in_start", Input).value = str(cfg.start_chapter)
        self.query_one("#in_end", Input).value = str(cfg.end_chapter)
        self.query_one("#in_threads", Input).value = str(cfg.max_threads)
        self.query_one("#chk_lite_critic", Checkbox).value = cfg.lite_critic

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn_start_translate":
            self.app.action_start_translate()
        elif event.button.id == "btn_stop_translate":
            self.app._stop_flag = True
            self.app.log(" Stop requested")


class GenerateScreen(AppScreen):
    def compose(self):
        yield Static("[bold] Generation Mode[/]", id="gen_title")

        yield Static("[bold]Style hiện tại:[/]", id="gen_style_current")
        yield Button(" Đổi trong tab Style (4)", id="btn_goto_style", variant="default")

        yield Static("[bold]CẤU HÌNH MỞ RỘNG:[/]")
        yield Horizontal(
            ScrollableContainer(
                Label("Generation flow:"),
                RadioSet(
                    RadioButton("Continue from last chapter", value=True, id="gen_continue"),
                    RadioButton("Spin-off character", id="gen_spinoff"),
                    id="gen_flow_radio",
                ),
                Label("Character name (for spin-off):"),
                Input(placeholder="Lâm Nhất", id="in_character"),
                Label("Total chapters to generate:"),
                Input(placeholder="5", id="in_gen_chapters"),
                Button(" AI gợi ý số chương", id="btn_suggest_chapters", variant="default"),
                Static("", id="gen_suggestion"),
                RadioSet(
                    RadioButton("AI tự động chia arc", value=True, id="arc_auto"),
                    RadioButton("Fixed chapters/arc:", id="arc_fixed"),
                    id="arc_mode_radio",
                ),
                Input(placeholder="20", id="in_arc_size"),
                Static("", id="gen_arc_preview"),
                Static("[bold]STEER (khi đang gen):[/]", classes="section_label"),
                Horizontal(
                    Input(placeholder="stop | focus: world/character/challenge | slow | fast | note: ...", id="in_steer"),
                    Button("Gửi", id="btn_steer_send", variant="default"),
                ),
                Button(" Start Generation", id="btn_start_gen", variant="primary"),
                Button(" Stop", id="btn_stop_gen", variant="error"),
            ),
            Vertical(
                RichLog(id="gen_log", highlight=True, max_lines=100, wrap=True),
            ),
        )

    def on_mount(self):
        cfg = self.app.config
        self._refresh_style()
        self.query_one("#in_gen_chapters", Input).value = "5"
        self.query_one("#in_arc_size", Input).value = "20"

    def _refresh_style(self):
        cfg = self.app.config
        style_label = STYLE_LABELS.get(cfg.expansion_style, cfg.expansion_style)
        dir_label = DIRECTION_LABELS.get(cfg.hallucination_direction, cfg.hallucination_direction)
        st = self.query_one("#gen_style_current", Static)
        st.update(f"Style: {style_label} | Hướng: {dir_label} | Sáng tạo: {cfg.creativity_level}/3")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn_start_gen":
            self.app.action_start_generation()
        elif event.button.id == "btn_stop_gen":
            self.app._stop_flag = True
            if hasattr(self.app, '_coordinator') and self.app._coordinator:
                self.app._coordinator._stop_flag = True
            self.app.log(" Generation stopped")
        elif event.button.id == "btn_goto_style":
            self.app.action_switch_tab("style")
        elif event.button.id == "btn_suggest_chapters":
            self.app.action_suggest_chapters()
        elif event.button.id == "btn_steer_send":
            self._send_steer()

    def on_input_submitted(self, event: Input.Submitted):
        if event.input.id == "in_steer":
            self._send_steer()

    def _send_steer(self):
        inp = self.query_one("#in_steer", Input)
        cmd = inp.value.strip()
        if not cmd:
            return
        inp.value = ""
        coord = getattr(self.app, '_coordinator', None)
        if coord and hasattr(coord, 'steer_queue') and coord.steer_queue is not None:
            coord.steer_queue.put_nowait(cmd)
            self.app.log(f" Steer sent: {cmd}")
        else:
            self.app.log(" Steer: coordinator not running")


class StyleScreen(AppScreen):
    def compose(self):
        yield Static("[bold] Văn phong & Hướng mở rộng[/]", id="style_title")
        yield Static("Chọn trước khi Gen. Các lựa chọn này được inject vào prompt Architect + Writer.")

        yield Static("[bold]VĂN PHONG (Writing Style):[/]")
        yield RadioSet(
            RadioButton("Cân bằng", id="style_balanced"),
            RadioButton("Hành động", id="style_action"),
            RadioButton("Tâm lý", id="style_psychological"),
            RadioButton("Miêu tả", id="style_descriptive"),
            RadioButton("Văn học", id="style_literary"),
            RadioButton("Giữ nguyên (bám sát style gốc)", id="style_giu_nguyen"),
            id="style_radio",
        )

        yield Static("[bold]HƯỚNG MỞ RỘNG (Smart Analysis):[/]")
        yield Button(" Phân tích thông minh", id="btn_analyze", variant="primary")
        yield Static("", id="analyze_status")
        yield Static("", id="suggestions_area")

        yield Static("[bold]HƯỚNG TẬP TRUNG (Hallucination Focus):[/]")
        yield RadioSet(
            RadioButton("Tự do (Free)", id="dir_free"),
            RadioButton("Thế giới/Bối cảnh (World)", id="dir_world"),
            RadioButton("Nhân vật (Character)", id="dir_character"),
            RadioButton("Thử thách (Challenge)", id="dir_challenge"),
            id="direction_radio",
        )

        yield Static("[bold]MỨC SÁNG TẠO (Creativity Level):[/]")
        yield RadioSet(
            RadioButton("1 - Thấp (bám sát outline)", id="creativity_1"),
            RadioButton("2 - Trung bình (cân bằng)", id="creativity_2"),
            RadioButton("3 - Cao (bay bổng)", id="creativity_3"),
            id="creativity_radio",
        )

        yield Static("[bold]CẤU HÌNH BỔ SUNG:[/]")
        yield Checkbox("Cấm tạo nhân vật mới (Forbidden new characters)", id="chk_forbidden_chars")
        yield Label("Số từ trung bình mỗi chương (Average Words):")
        yield Input(placeholder="auto hoặc số từ cụ thể (ví dụ: 3000)", id="in_avg_words")

        yield Button(" Lưu Style Config", id="btn_save_style", variant="primary")
        yield Static("", id="style_preview")

    def on_mount(self):
        cfg = self.app.config
        self._set_radio("style_radio", f"style_{cfg.expansion_style}")
        self._set_radio("creativity_radio", f"creativity_{cfg.creativity_level}")
        self._set_radio("direction_radio", f"dir_{cfg.hallucination_direction}")
        self.query_one("#chk_forbidden_chars", Checkbox).value = cfg.forbidden_new_characters
        self.query_one("#in_avg_words", Input).value = str(cfg.avg_words_per_chapter)
        self._refresh_preview()

    def _set_radio(self, radio_id: str, value_id: str):
        try:
            rs = self.query_one(f"#{radio_id}", RadioSet)
            for rb in rs.query(RadioButton):
                if rb.id == value_id:
                    rb.value = True
                    break
        except Exception:
            pass

    def _refresh_preview(self):
        style = self._get_selected_style()
        direction = self._get_selected_direction()
        creativity = self._get_selected_creativity()
        section = build_style_section(style, direction, creativity)
        preview = self.query_one("#style_preview", Static)
        if section:
            preview.update(f"[dim]{section[:400]}[/]")
        else:
            preview.update("[dim]Giữ nguyên: không inject style prompt[/]")

    def _get_selected_style(self) -> str:
        rs = self.query_one("#style_radio", RadioSet)
        for rb in rs.query(RadioButton):
            if rb.value and rb.id:
                return rb.id.replace("style_", "")
        return "giu_nguyen"

    def _get_selected_creativity(self) -> int:
        rs = self.query_one("#creativity_radio", RadioSet)
        for rb in rs.query(RadioButton):
            if rb.value and rb.id:
                return int(rb.id.replace("creativity_", ""))
        return 2

    def _get_selected_direction(self) -> str:
        rs = self.query_one("#direction_radio", RadioSet)
        for rb in rs.query(RadioButton):
            if rb.value and rb.id:
                return rb.id.replace("dir_", "")
        return "free"

    def on_radio_set_changed(self, event: RadioSet.Changed):
        if event.radio_set.id in ("style_radio", "creativity_radio", "direction_radio"):
            self._refresh_preview()

    async def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn_save_style":
            self._save_style()
        elif event.button.id == "btn_analyze":
            await self._run_analysis()

    def _save_style(self):
        cfg = self.app.config
        cfg.expansion_style = self._get_selected_style()
        cfg.creativity_level = self._get_selected_creativity()
        cfg.hallucination_direction = self._get_selected_direction()
        cfg.forbidden_new_characters = self.query_one("#chk_forbidden_chars", Checkbox).value
        
        avg_val = self.query_one("#in_avg_words", Input).value.strip()
        if avg_val.lower() == "auto" or not avg_val:
            cfg.avg_words_per_chapter = "auto"
        else:
            try:
                cfg.avg_words_per_chapter = int(avg_val)
            except ValueError:
                cfg.avg_words_per_chapter = "auto"

        cfg.save_api_config()
        self.app.log(f" Style saved: {cfg.expansion_style}, creativity={cfg.creativity_level}, dir={cfg.hallucination_direction}, forbidden_chars={cfg.forbidden_new_characters}, avg_words={cfg.avg_words_per_chapter}")
        try:
            self.app.query_one(GenerateScreen)._refresh_style()
        except Exception:
            pass
        try:
            self.app.query_one(Dashboard)._refresh()
        except Exception:
            pass
        self._refresh_preview()

    async def _run_analysis(self):
        status = self.query_one("#analyze_status", Static)
        suggestions = self.query_one("#suggestions_area", Static)
        status.update("[yellow]Đang phân tích NovelProfile...[/]")
        suggestions.update("")

        exporter = NovelProfileExporter(self.app.config)
        profile = exporter.load()
        if profile is None:
            path = exporter.export()
            profile = exporter.load()

        sd = SmartDirector(self.app.config.api_endpoint, self.app.config.auth_key)
        try:
            results = await sd.analyze(profile)
            self._suggestions_data = results
            self._render_suggestions(results)
            status.update("[green]Phân tích hoàn tất![/]")
        except Exception as e:
            status.update(f"[red]Lỗi: {e}[/]")

    def _render_suggestions(self, results: List[Dict]):
        lines = []
        for i, s in enumerate(results):
            direction = s.get("direction", "free")
            tag = s.get("tag", "on")
            reason = s.get("reason", "")
            label = DIRECTION_LABELS.get(direction, direction)
            tag_label = TAG_LABELS.get(tag, tag)
            lines.append(f"[{i}] {label} ({tag_label})")
            lines.append(f"   {reason}")
            lines.append(f"   [dim]{s.get('detail', '')}[/]")
            lines.append("")
        self.query_one("#suggestions_area", Static).update("\n".join(lines))


class ModelConfigScreen(AppScreen):
    def compose(self):
        yield Static("[bold] Model Configuration[/]", id="model_title")
        yield Label("API Endpoint:")
        yield Input(placeholder="http://127.0.0.1:58100/v1", id="in_api_endpoint")
        yield Label("Auth Key:")
        yield Input(placeholder="sk-...", id="in_auth_key", password=True)
        yield Button(" Refresh models from API", id="btn_refresh_models")
        yield Static("", id="model_status")
        yield DataTable(id="model_table")
        yield Static("")
        yield Static("[bold]Per-Role Assignment:[/]")
        for role in ("architect", "writer", "critic", "coordinator"):
            yield Horizontal(
                Static(f"{role}:", classes="role_label"),
                Select([], id=f"sel_{role}", classes="role_select"),
                classes="role_row",
            )
        yield Button(" Save Config", id="btn_save_config", variant="primary")

    def on_mount(self):
        self.table = self.query_one("#model_table", DataTable)
        self.table.add_columns("Model", "Context Window")
        
        cfg = self.app.config
        self.query_one("#in_api_endpoint", Input).value = cfg.api_endpoint
        self.query_one("#in_auth_key", Input).value = cfg.auth_key
        
        self.loading_lbl = self.query_one("#model_status", Static)
        self.loading_lbl.update("⏳ Fetching models from API...")
        self._load_models()

    @work(name="load_models", group="models", exit_on_error=False)
    async def _load_models(self):
        try:
            endpoint = self.query_one("#in_api_endpoint", Input).value.strip()
            auth_key = self.query_one("#in_auth_key", Input).value.strip()
            model_registry.configure(endpoint, auth_key)
            self.app.api_manager.update_config(endpoint, auth_key)
            
            models = await model_registry.fetch_async(force=True)
        except Exception:
            models = []
        
        self.refresh_ui(models)
        
        if models:
            self.loading_lbl.update(f" {len(models)} models loaded from API")
        else:
            self.loading_lbl.update("⚠ API unavailable — using hardcoded fallback")

    def refresh_ui(self, models: List[Dict]):
        if not models:
            models = [{"id": k, "context_length": v} for k, v in HARDCODED_CONTEXT.items()]
        
        self.table.clear()
        for m in models:
            ctx = m.get("context_length", 220000)
            self.table.add_row(m["id"], f"{ctx:,}")
        
        # Ensure options are unique and contain currently configured values
        options_map = {m["id"]: m["id"] for m in models}
        for role in ("architect", "writer", "critic", "coordinator"):
            current = self.app.config.role_models.get(role, "")
            if current and current not in options_map:
                options_map[current] = current
                
        options = list(options_map.items())
        
        for role in ("architect", "writer", "critic", "coordinator"):
            sel = self.query_one(f"#sel_{role}", Select)
            current = self.app.config.role_models.get(role, "")
            sel.set_options(options)
            if current and current in options_map:
                try:
                    sel.value = current
                except Exception:
                    pass

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn_refresh_models":
            self._load_models()
        elif event.button.id == "btn_save_config":
            endpoint = self.query_one("#in_api_endpoint", Input).value.strip()
            auth_key = self.query_one("#in_auth_key", Input).value.strip()
            roles: Dict[str, str] = {}
            for role in ("architect", "writer", "critic", "coordinator"):
                val = self.query_one(f"#sel_{role}", Select).value
                if isinstance(val, str):
                    roles[role] = val
            self.app.action_save_model_config(roles, endpoint=endpoint, auth_key=auth_key)


class LogScreen(AppScreen):
    _log_lines: list = []

    def compose(self):
        yield Static("[bold] System Log[/]", id="log_title")
        yield RichLog(id="system_log", highlight=True, max_lines=500, wrap=True)
        yield Horizontal(
            Button(" Clear Log", id="btn_clear_log"),
            Button(" Copy Log", id="btn_copy_log", variant="default"),
            Button(" Save Log to File", id="btn_save_log", variant="default"),
        )

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn_clear_log":
            self.query_one("#system_log", RichLog).clear()
            LogScreen._log_lines.clear()
            self.app.log_msg("[Log cleared]")
        elif event.button.id == "btn_copy_log":
            try:
                import pyperclip
                pyperclip.copy("\n".join(LogScreen._log_lines))
                self.app.log_msg(" Log copied to clipboard!")
            except Exception as e:
                self.app.log_msg(f"❌ Copy failed: {e}")
        elif event.button.id == "btn_save_log":
            self._save_log_to_file()

    def _save_log_to_file(self):
        import time as _time
        import os
        try:
            log_dir = self.app.config.output_dir
            os.makedirs(log_dir, exist_ok=True)
            ts = _time.strftime("%Y%m%d_%H%M%S")
            log_path = os.path.join(log_dir, f"session_log_{ts}.txt")
            lines = LogScreen._log_lines if LogScreen._log_lines else ["(No log content captured)"]
            with open(log_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            self.app.log_msg(f" Log saved → {log_path}")
        except Exception as e:
            self.app.log_msg(f"❌ Save log failed: {e}")


if __name__ == "__main__":
    app = NovelTranslatorApp()
    app.run()
