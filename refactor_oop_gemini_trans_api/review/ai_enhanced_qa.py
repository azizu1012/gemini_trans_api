"""
AI-Enhanced Quality Assurance
=============================
QA thông minh sử dụng API để:
1. Phân tích sâu với sampling ngẫu nhiên
2. Đánh giá pacing qua nhiều chương
3. Phát hiện plot holes và inconsistencies
4. Đưa feedback có thể action được cho Director

Khác với QA cũ (regex-based), module này:
- Gọi API để phân tích phức tạp
- Sử dụng ít request (sampling thay vì mọi chương)
- Output feedback dạng actionable cho production team
"""

import os
import re
import json
import random
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# Try relative import first, fallback to direct
try:
    from .quality_assurance import QualityAssurance, QualityScore, QualityLevel
except ImportError:
    try:
        from directors.quality_assurance import QualityAssurance, QualityScore, QualityLevel
    except ImportError:
        # Standalone mode
        QualityAssurance = None
        
try:
    from world.ai_analysis_pipeline import SummaryExtractor, SmartQA, RAGFeeder
except ImportError:
    try:
        from ..world.ai_analysis_pipeline import SummaryExtractor, SmartQA, RAGFeeder
    except ImportError:
        # Components not available - QA will work without them
        SummaryExtractor = None
        SmartQA = None
        RAGFeeder = None


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class AIQAFeedback:
    """Feedback từ AI analysis - actionable cho Director"""
    timestamp: str
    analysis_type: str  # 'sampling', 'targeted', 'full'
    chapters_analyzed: List[int]
    
    # Scores
    overall_score: float  # 0-100
    pacing_score: float
    consistency_score: float
    character_score: float
    plot_score: float
    
    # Assessments
    pacing_assessment: str  # 'too_slow', 'good', 'too_fast', 'inconsistent'
    arc_health: str  # 'developing', 'climax', 'resolution', 'problematic'
    character_development: str  # 'strong', 'adequate', 'weak', 'missing'
    
    # Actionable Feedback
    critical_issues: List[str]  # Cần fix ngay
    warnings: List[str]  # Nên xem xét
    suggestions: List[str]  # Có thể cải thiện
    
    # For Director
    director_instructions: str  # Hướng dẫn cụ thể cho Director
    
    # Meta
    confidence: float  # 0-1, độ tin cậy của analysis
    requires_rewrite: List[int]  # Chapters cần viết lại


@dataclass
class PlotThread:
    """Một tuyến truyện đang theo dõi"""
    name: str
    start_chapter: int
    status: str  # 'active', 'dormant', 'resolved', 'abandoned'
    last_mentioned: int
    key_events: List[Dict]
    characters_involved: List[str]


# ============================================================================
# AI-ENHANCED QA CLASS
# ============================================================================

class AIEnhancedQA:
    """
    QA thông minh với AI analysis
    
    Features:
    1. Random Sampling - Không cần check mọi chương
    2. API-Powered Deep Analysis - Cho các issues phức tạp
    3. Actionable Feedback - Output cho Director có thể action ngay
    4. Historical Tracking - Theo dõi quality trends
    """
    
    def __init__(
        self,
        base_dir: str,
        api_caller = None,  # Optional: API caller để deep analysis
        sample_ratio: float = 0.1,  # Sample 10% chapters
        min_samples: int = 5,
        max_samples: int = 20
    ):
        self.base_dir = base_dir
        self.api_caller = api_caller
        self.sample_ratio = sample_ratio
        self.min_samples = min_samples
        self.max_samples = max_samples
        
        # Paths
        self.memory_dir = os.path.join(base_dir, 'memory_store')
        self.map_config = os.path.join(base_dir, 'output', 'world_config.json')
        self.qa_history_file = os.path.join(base_dir, 'output', 'qa_history.json')
        
        # State
        self.summaries: Dict[int, str] = {}
        self.plot_threads: List[PlotThread] = []
        self.qa_history: List[AIQAFeedback] = []
        
        # Load existing data
        self._load_data()
    
    def _load_data(self):
        """Load summaries và history"""
        # Load summaries từ memory_store
        if os.path.exists(self.memory_dir):
            for file in os.listdir(self.memory_dir):
                if file.startswith('cumulative_') or file.startswith('memory_block_'):
                    self._parse_memory_file(os.path.join(self.memory_dir, file))
        
        # Load QA history
        if os.path.exists(self.qa_history_file):
            try:
                with open(self.qa_history_file, 'r', encoding='utf-8') as f:
                    history_data = json.load(f)
                    # Convert to dataclass (simplified)
            except:
                pass
    
    def _parse_memory_file(self, path: str):
        """Parse memory file để lấy summaries"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Pattern cho cumulative files
            pattern = r'Chương\s+(\d+)[:\s]+(.+?)(?=Chương\s+\d+|$)'
            for ch_str, summary in re.findall(pattern, content, re.DOTALL):
                try:
                    self.summaries[int(ch_str)] = summary.strip()[:500]
                except:
                    pass
        except:
            pass
    
    # ========================================================================
    # SAMPLING STRATEGY
    # ========================================================================
    
    def select_samples(self, total_chapters: int, strategy: str = 'distributed') -> List[int]:
        """
        Chọn chapters để sample
        
        Strategies:
        - 'distributed': Phân bố đều qua toàn bộ
        - 'weighted': Ưu tiên cao trào và chuyển arc
        - 'random': Hoàn toàn ngẫu nhiên
        - 'recent': Ưu tiên chapters gần đây
        """
        num_samples = int(total_chapters * self.sample_ratio)
        num_samples = max(self.min_samples, min(self.max_samples, num_samples))
        
        available = sorted(self.summaries.keys())
        if not available:
            return list(range(1, min(num_samples + 1, total_chapters + 1)))
        
        if strategy == 'distributed':
            # Chia đều
            step = len(available) // num_samples
            samples = [available[i * step] for i in range(num_samples)]
        
        elif strategy == 'weighted':
            # Ưu tiên: chapter 1, mỗi 50 chapter, last 10
            priority = [1]
            priority.extend([ch for ch in available if ch % 50 == 0])
            priority.extend(available[-10:])
            
            # Fill còn lại random
            remaining = num_samples - len(priority)
            if remaining > 0:
                others = [ch for ch in available if ch not in priority]
                priority.extend(random.sample(others, min(remaining, len(others))))
            
            samples = sorted(set(priority))[:num_samples]
        
        elif strategy == 'recent':
            # 70% từ 20% cuối, 30% từ phần còn lại
            recent_count = int(num_samples * 0.7)
            early_count = num_samples - recent_count
            
            cutoff = int(len(available) * 0.8)
            recent = available[cutoff:]
            early = available[:cutoff]
            
            samples = random.sample(recent, min(recent_count, len(recent)))
            samples.extend(random.sample(early, min(early_count, len(early))))
            samples = sorted(set(samples))
        
        else:  # random
            samples = sorted(random.sample(available, min(num_samples, len(available))))
        
        return samples
    
    # ========================================================================
    # LOCAL ANALYSIS (không cần API)
    # ========================================================================
    
    def analyze_pacing_local(self, chapters: List[int]) -> Dict:
        """
        Phân tích pacing từ summaries (local, không API)
        """
        if not chapters:
            return {'error': 'No chapters to analyze'}
        
        results = {
            'chapters': chapters,
            'pacing_scores': {},
            'overall_pacing': 'unknown',
            'issues': []
        }
        
        # Event keywords
        action_words = ['đánh', 'chém', 'giết', 'chiến đấu', 'tấn công', 'chạy', 'trốn']
        slow_words = ['nói', 'nghĩ', 'nhớ', 'kể', 'giải thích', 'hồi tưởng']
        climax_words = ['quyết định', 'cuối cùng', 'kết thúc', 'chiến thắng', 'thất bại']
        
        action_count = 0
        slow_count = 0
        climax_count = 0
        
        for ch in chapters:
            if ch not in self.summaries:
                continue
            
            summary = self.summaries[ch].lower()
            
            ch_action = sum(1 for w in action_words if w in summary)
            ch_slow = sum(1 for w in slow_words if w in summary)
            ch_climax = sum(1 for w in climax_words if w in summary)
            
            action_count += ch_action
            slow_count += ch_slow
            climax_count += ch_climax
            
            # Per-chapter pacing
            if ch_action > ch_slow + 2:
                results['pacing_scores'][ch] = 'fast'
            elif ch_slow > ch_action + 2:
                results['pacing_scores'][ch] = 'slow'
            elif ch_climax > 0:
                results['pacing_scores'][ch] = 'climax'
            else:
                results['pacing_scores'][ch] = 'normal'
        
        # Overall assessment
        total = action_count + slow_count
        if total == 0:
            results['overall_pacing'] = 'unknown'
        elif action_count > slow_count * 2:
            results['overall_pacing'] = 'too_fast'
            results['issues'].append('Quá nhiều action liên tục, cần breathing room')
        elif slow_count > action_count * 2:
            results['overall_pacing'] = 'too_slow'
            results['issues'].append('Quá nhiều exposition, cần thêm conflict')
        else:
            results['overall_pacing'] = 'balanced'
        
        # Check for inconsistent pacing
        pacing_values = list(results['pacing_scores'].values())
        if pacing_values:
            fast_ratio = pacing_values.count('fast') / len(pacing_values)
            slow_ratio = pacing_values.count('slow') / len(pacing_values)
            
            if fast_ratio > 0.3 and slow_ratio > 0.3:
                results['overall_pacing'] = 'inconsistent'
                results['issues'].append('Nhịp độ dao động nhiều - "lên voi xuống chó"')
        
        return results
    
    def analyze_consistency_local(self, chapters: List[int]) -> Dict:
        """
        Check consistency giữa các chapters (local)
        """
        results = {
            'chapters': chapters,
            'issues': [],
            'score': 100
        }
        
        # Track entities mentioned
        entities_per_chapter: Dict[int, set] = {}
        
        for ch in chapters:
            if ch not in self.summaries:
                continue
            
            summary = self.summaries[ch]
            
            # Extract names (capitalized words)
            names = set(re.findall(r'\b[A-ZĐ][a-zàáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵ]+(?:\s+[A-ZĐ][a-zàáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵ]+)?\b', summary))
            entities_per_chapter[ch] = names
        
        # Check for sudden disappearances
        sorted_chapters = sorted(entities_per_chapter.keys())
        for i, ch in enumerate(sorted_chapters[:-1]):
            current = entities_per_chapter[ch]
            next_ch = sorted_chapters[i + 1]
            next_entities = entities_per_chapter.get(next_ch, set())
            
            # Characters that were prominent but disappeared
            if len(current) > 3:
                lost = current - next_entities
                if len(lost) > len(current) * 0.5:
                    results['issues'].append(
                        f"Ch.{ch}→{next_ch}: Nhiều nhân vật biến mất đột ngột"
                    )
                    results['score'] -= 10
        
        return results
    
    def detect_plot_threads(self, chapters: List[int]) -> List[PlotThread]:
        """
        Phát hiện các tuyến truyện từ summaries
        """
        threads = []
        
        # Keywords indicating plot threads
        thread_indicators = {
            'mystery': ['bí mật', 'bí ẩn', 'ai là', 'tại sao', 'ẩn giấu'],
            'conflict': ['xung đột', 'đối đầu', 'thù', 'chiến tranh'],
            'romance': ['yêu', 'tình', 'thương', 'nhớ'],
            'power': ['mạnh', 'sức mạnh', 'tiến hóa', 'thức tỉnh'],
            'survival': ['sống', 'chết', 'thoát', 'nguy hiểm'],
        }
        
        thread_mentions: Dict[str, List[int]] = {k: [] for k in thread_indicators}
        
        for ch in sorted(self.summaries.keys()):
            if ch not in chapters:
                continue
            
            summary = self.summaries[ch].lower()
            
            for thread_type, keywords in thread_indicators.items():
                if any(kw in summary for kw in keywords):
                    thread_mentions[thread_type].append(ch)
        
        # Create PlotThread objects
        for thread_type, mentions in thread_mentions.items():
            if len(mentions) >= 2:
                threads.append(PlotThread(
                    name=thread_type,
                    start_chapter=min(mentions),
                    status='active' if max(mentions) >= max(chapters) - 10 else 'dormant',
                    last_mentioned=max(mentions),
                    key_events=[{'chapter': ch} for ch in mentions[:5]],
                    characters_involved=[]
                ))
        
        return threads
    
    # ========================================================================
    # API-POWERED ANALYSIS (optional)
    # ========================================================================
    
    def analyze_with_api(self, chapters: List[int], focus: str = 'general') -> Optional[Dict]:
        """
        Deep analysis sử dụng API
        
        Focus options:
        - 'general': Phân tích tổng quát
        - 'pacing': Focus vào nhịp độ
        - 'plot_holes': Tìm lỗ hổng plot
        - 'character': Phân tích character development
        """
        if not self.api_caller:
            return None
        
        # Gather context
        context_summaries = []
        for ch in chapters:
            if ch in self.summaries:
                context_summaries.append(f"Ch.{ch}: {self.summaries[ch][:200]}")
        
        if not context_summaries:
            return None
        
        # Build prompt based on focus
        prompts = {
            'general': f"""
Phân tích các chương sau và đánh giá chất lượng:

{chr(10).join(context_summaries)}

Đánh giá:
1. Nhịp độ (1-10): 
2. Tính nhất quán (1-10):
3. Phát triển nhân vật (1-10):
4. Logic plot (1-10):
5. Các vấn đề cần fix:
6. Gợi ý cải thiện:
""",
            'pacing': f"""
Phân tích nhịp độ của các chương:

{chr(10).join(context_summaries)}

Trả lời:
1. Nhịp độ hiện tại: (quá chậm/cân bằng/quá nhanh/không đều)
2. Các chương có vấn đề về nhịp:
3. Cách khắc phục:
""",
            'plot_holes': f"""
Tìm các lỗ hổng cốt truyện trong:

{chr(10).join(context_summaries)}

Liệt kê:
1. Mâu thuẫn logic:
2. Nhân vật/chi tiết bị bỏ quên:
3. Các loose ends chưa giải quyết:
""",
            'character': f"""
Phân tích phát triển nhân vật:

{chr(10).join(context_summaries)}

Đánh giá:
1. Nhân vật có character arc rõ ràng:
2. Nhân vật cần development thêm:
3. Giọng văn nhân vật có nhất quán:
"""
        }
        
        prompt = prompts.get(focus, prompts['general'])
        
        # Call API
        try:
            response = self.api_caller(prompt, model='summary')  # Use summary pool
            return {
                'focus': focus,
                'chapters': chapters,
                'analysis': response,
                'api_used': True
            }
        except Exception as e:
            return {
                'error': str(e),
                'api_used': False
            }
    
    # ========================================================================
    # GENERATE FEEDBACK FOR DIRECTOR
    # ========================================================================
    
    def generate_director_feedback(
        self,
        total_chapters: int,
        current_chapter: int,
        strategy: str = 'distributed',
        use_api: bool = False
    ) -> AIQAFeedback:
        """
        Generate comprehensive feedback cho Director
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Select samples
        samples = self.select_samples(total_chapters, strategy)
        
        # Local analysis
        pacing_result = self.analyze_pacing_local(samples)
        consistency_result = self.analyze_consistency_local(samples)
        plot_threads = self.detect_plot_threads(samples)
        
        # API analysis (optional)
        api_result = None
        if use_api and self.api_caller:
            api_result = self.analyze_with_api(samples[-10:], 'general')  # Recent chapters
        
        # Calculate scores
        pacing_score = 70  # Base
        if pacing_result['overall_pacing'] == 'balanced':
            pacing_score = 85
        elif pacing_result['overall_pacing'] in ['too_fast', 'too_slow']:
            pacing_score = 55
        elif pacing_result['overall_pacing'] == 'inconsistent':
            pacing_score = 40
        
        consistency_score = consistency_result['score']
        
        character_score = 70  # Default, can be enhanced with API
        plot_score = 70
        
        if len(plot_threads) >= 3:
            plot_score = 80  # Good variety
        
        active_threads = [t for t in plot_threads if t.status == 'active']
        if len(active_threads) == 0:
            plot_score -= 20  # No active plot threads is bad
        
        overall_score = (pacing_score + consistency_score + character_score + plot_score) / 4
        
        # Gather issues
        critical_issues = []
        warnings = []
        suggestions = []
        requires_rewrite = []
        
        # Pacing issues
        if pacing_result['overall_pacing'] == 'inconsistent':
            critical_issues.append("⚠️ Nhịp độ không đều - cần review và balance lại")
        for issue in pacing_result.get('issues', []):
            warnings.append(f"📊 Pacing: {issue}")
        
        # Consistency issues
        for issue in consistency_result.get('issues', []):
            warnings.append(f"🔗 Consistency: {issue}")
        
        # Plot issues
        dormant = [t for t in plot_threads if t.status == 'dormant']
        for thread in dormant:
            if current_chapter - thread.last_mentioned > 30:
                warnings.append(f"📖 Tuyến '{thread.name}' bị bỏ rơi từ ch.{thread.last_mentioned}")
        
        # Suggestions
        if pacing_score < 70:
            suggestions.append("Xem xét thêm chapter transition/breathing room")
        
        if len(active_threads) >= 4:
            suggestions.append("Có nhiều tuyến truyện đang mở - cần resolve một số")
        
        if consistency_score < 80:
            suggestions.append("Review lại references đến nhân vật phụ")
        
        # Director instructions
        director_instructions = self._build_director_instructions(
            pacing_result, consistency_result, plot_threads, current_chapter
        )
        
        # Determine chapters that need rewrite
        if pacing_score < 50:
            # Find problematic chapters
            for ch, pacing in pacing_result.get('pacing_scores', {}).items():
                if pacing == 'too_slow' or pacing == 'too_fast':
                    requires_rewrite.append(ch)
        
        # Build feedback
        feedback = AIQAFeedback(
            timestamp=timestamp,
            analysis_type='sampling',
            chapters_analyzed=samples,
            overall_score=overall_score,
            pacing_score=pacing_score,
            consistency_score=consistency_score,
            character_score=character_score,
            plot_score=plot_score,
            pacing_assessment=pacing_result['overall_pacing'],
            arc_health='developing' if active_threads else 'problematic',
            character_development='adequate',
            critical_issues=critical_issues,
            warnings=warnings,
            suggestions=suggestions,
            director_instructions=director_instructions,
            confidence=0.7 if not api_result else 0.85,
            requires_rewrite=requires_rewrite[:5]  # Max 5
        )
        
        # Save to history
        self.qa_history.append(feedback)
        self._save_history()
        
        return feedback
    
    def _build_director_instructions(
        self,
        pacing: Dict,
        consistency: Dict,
        threads: List[PlotThread],
        current_chapter: int
    ) -> str:
        """Build actionable instructions cho Director"""
        lines = []
        lines.append("=" * 40)
        lines.append("📋 HƯỚNG DẪN CHO DIRECTOR")
        lines.append("=" * 40)
        
        # Pacing guidance
        if pacing['overall_pacing'] == 'too_fast':
            lines.append("\n🎯 NHỊP ĐỘ: Cần chậm lại")
            lines.append("   - Thêm chapter development/dialogue")
            lines.append("   - Cho nhân vật thời gian phản ứng")
            lines.append("   - Thêm worldbuilding hoặc backstory")
        elif pacing['overall_pacing'] == 'too_slow':
            lines.append("\n🎯 NHỊP ĐỘ: Cần tăng tốc")
            lines.append("   - Thêm conflict/action")
            lines.append("   - Cắt bớt exposition dài")
            lines.append("   - Tạo urgency/deadline cho nhân vật")
        elif pacing['overall_pacing'] == 'inconsistent':
            lines.append("\n🎯 NHỊP ĐỘ: Cần cân bằng")
            lines.append("   - Tránh chuyển đột ngột slow↔fast")
            lines.append("   - Dùng transition chapters")
            lines.append("   - Plan arc structure rõ hơn")
        else:
            lines.append("\n✅ NHỊP ĐỘ: Đang tốt, duy trì")
        
        # Plot threads
        active = [t for t in threads if t.status == 'active']
        dormant = [t for t in threads if t.status == 'dormant']
        
        if active:
            lines.append(f"\n📖 TUYẾN ĐANG ACTIVE ({len(active)}):")
            for t in active[:3]:
                lines.append(f"   • {t.name} (từ ch.{t.start_chapter})")
        
        if dormant:
            lines.append(f"\n⏸️ TUYẾN CẦN NHẮC LẠI:")
            for t in dormant[:2]:
                lines.append(f"   • {t.name} (last: ch.{t.last_mentioned})")
        
        # Next steps
        lines.append(f"\n📍 NEXT STEPS (từ ch.{current_chapter}):")
        if len(active) >= 4:
            lines.append("   1. Resolve 1-2 tuyến phụ trước khi mở mới")
        if dormant:
            lines.append(f"   2. Nhắc lại '{dormant[0].name}' trong 5 chương tới")
        lines.append("   3. Maintain current quality level")
        
        lines.append("\n" + "=" * 40)
        return '\n'.join(lines)
    
    def _save_history(self):
        """Save QA history"""
        try:
            os.makedirs(os.path.dirname(self.qa_history_file), exist_ok=True)
            
            # Convert to dict for JSON
            history_data = []
            for fb in self.qa_history[-20:]:  # Keep last 20
                history_data.append({
                    'timestamp': fb.timestamp,
                    'overall_score': fb.overall_score,
                    'pacing': fb.pacing_assessment,
                    'issues_count': len(fb.critical_issues) + len(fb.warnings)
                })
            
            with open(self.qa_history_file, 'w', encoding='utf-8') as f:
                json.dump(history_data, f, ensure_ascii=False, indent=2)
        except:
            pass
    
    # ========================================================================
    # PUBLIC METHODS
    # ========================================================================
    
    def quick_check(self, chapter_range: Tuple[int, int]) -> Dict:
        """Quick local check cho một range nhỏ"""
        chapters = list(range(chapter_range[0], chapter_range[1] + 1))
        chapters = [ch for ch in chapters if ch in self.summaries]
        
        pacing = self.analyze_pacing_local(chapters)
        consistency = self.analyze_consistency_local(chapters)
        
        return {
            'range': chapter_range,
            'chapters_found': len(chapters),
            'pacing': pacing['overall_pacing'],
            'consistency_score': consistency['score'],
            'issues': pacing.get('issues', []) + consistency.get('issues', [])
        }
    
    def get_quality_trend(self) -> Dict:
        """Xem trend chất lượng qua các lần check"""
        if len(self.qa_history) < 2:
            return {'trend': 'insufficient_data'}
        
        scores = [fb.overall_score for fb in self.qa_history]
        recent = scores[-5:] if len(scores) >= 5 else scores
        older = scores[-10:-5] if len(scores) >= 10 else scores[:len(scores)//2]
        
        avg_recent = sum(recent) / len(recent)
        avg_older = sum(older) / len(older) if older else avg_recent
        
        if avg_recent > avg_older + 5:
            trend = 'improving'
        elif avg_recent < avg_older - 5:
            trend = 'declining'
        else:
            trend = 'stable'
        
        return {
            'trend': trend,
            'recent_avg': avg_recent,
            'older_avg': avg_older,
            'data_points': len(self.qa_history)
        }
    
    def format_feedback_for_display(self, feedback: AIQAFeedback) -> str:
        """Format feedback để hiển thị"""
        lines = []
        lines.append("╔" + "═" * 50 + "╗")
        lines.append("║" + "  🔍 AI-ENHANCED QA REPORT  ".center(50) + "║")
        lines.append("╠" + "═" * 50 + "╣")
        
        lines.append(f"║ 📅 {feedback.timestamp}".ljust(51) + "║")
        lines.append(f"║ 📊 Score: {feedback.overall_score:.1f}/100".ljust(51) + "║")
        lines.append("╠" + "─" * 50 + "╣")
        
        lines.append(f"║ Pacing: {feedback.pacing_score:.0f}/100 ({feedback.pacing_assessment})".ljust(51) + "║")
        lines.append(f"║ Consistency: {feedback.consistency_score:.0f}/100".ljust(51) + "║")
        lines.append(f"║ Character: {feedback.character_score:.0f}/100".ljust(51) + "║")
        lines.append(f"║ Plot: {feedback.plot_score:.0f}/100".ljust(51) + "║")
        
        if feedback.critical_issues:
            lines.append("╠" + "─" * 50 + "╣")
            lines.append("║ 🚨 CRITICAL ISSUES:".ljust(51) + "║")
            for issue in feedback.critical_issues:
                lines.append(f"║   {issue[:45]}".ljust(51) + "║")
        
        if feedback.warnings:
            lines.append("╠" + "─" * 50 + "╣")
            lines.append("║ ⚠️ WARNINGS:".ljust(51) + "║")
            for warn in feedback.warnings[:3]:
                lines.append(f"║   {warn[:45]}".ljust(51) + "║")
        
        if feedback.suggestions:
            lines.append("╠" + "─" * 50 + "╣")
            lines.append("║ 💡 SUGGESTIONS:".ljust(51) + "║")
            for sug in feedback.suggestions[:3]:
                lines.append(f"║   {sug[:45]}".ljust(51) + "║")
        
        lines.append("╚" + "═" * 50 + "╝")
        
        if feedback.director_instructions:
            lines.append("\n" + feedback.director_instructions)
        
        return '\n'.join(lines)
