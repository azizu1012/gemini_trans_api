"""
ModelRegistry — singleton quản lý danh sách model + context_window
"""

import os, json, time
from typing import Dict, List, Optional, Any
import httpx

HARDCODED_CONTEXT: Dict[str, int] = {
    "gemini-flash-35": 200_000,
    "gemini-flash-30": 200_000,
    "gemini-flash": 200_000,
    "gemini-flash-25": 200_000,
    "gemini-flash-lite": 200_000,
    "gemini-flash-25-lite": 200_000,
}


class ModelRegistry:
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if ModelRegistry._initialized:
            return
        ModelRegistry._initialized = True
        self._models: List[Dict[str, Any]] = []
        self._context_map: Dict[str, int] = {}
        self._last_fetch: float = 0.0
        self._cache_ttl: float = 300.0  # 5 phút
        self._endpoint: str = "http://127.0.0.1:58100/v1"
        self._auth_key: str = ""

    def configure(self, endpoint: str, auth_key: str = ""):
        self._endpoint = endpoint
        self._auth_key = auth_key

    async def fetch_async(self, force: bool = False) -> List[Dict[str, Any]]:
        now = time.time()
        if not force and self._models and (now - self._last_fetch) < self._cache_ttl:
            return self._models

        models: List[Dict[str, Any]] = []
        url = self._endpoint.rstrip("/")
        if "openrouter.ai" in url:
            if not url.endswith("/api/v1"):
                url = f"{url}/api/v1"
            url = f"{url}/models"
        elif "googleapis.com" in url:
            if not url.endswith("/v1beta") and not url.endswith("/v1"):
                url = f"{url}/v1beta"
            url = f"{url}/models"
        else:
            if url.endswith("/v1"):
                url = f"{url[:-3]}/v1beta/models"
            elif url.endswith("/v1beta") or url.endswith("/v1alpha"):
                url = f"{url}/models"
            elif not url.endswith("/models"):
                url = f"{url}/v1beta/models"

        headers = {}
        if self._auth_key:
            headers["Authorization"] = f"Bearer {self._auth_key}"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    raw = []
                    if isinstance(data, dict):
                        if "data" in data:
                            raw = data["data"]
                        elif "models" in data:
                            raw = data["models"]
                    elif isinstance(data, list):
                        raw = data
                    
                    for m in raw:
                        if not isinstance(m, dict):
                            continue
                        mid = m.get("id") or m.get("name") or ""
                        if not mid:
                            continue
                        if mid.startswith("models/"):
                            mid = mid[len("models/"):]
                        ctx = (m.get("context_length") 
                               or m.get("inputTokenLimit")
                               or m.get("context_window")
                               or m.get("max_context_length") 
                               or m.get("limits", {}).get("max_context_length")
                               or HARDCODED_CONTEXT.get(mid, 220000))
                        models.append({
                            "id": mid,
                            "display": m.get("display") or m.get("displayName") or mid,
                            "root": m.get("root") or mid,
                            "context_length": int(ctx),
                        })
        except Exception:
            pass

        if not models:
            # Fallback to hardcoded map
            for mid, ctx in HARDCODED_CONTEXT.items():
                models.append({
                    "id": mid,
                    "display": mid,
                    "root": mid,
                    "context_length": ctx,
                })

        self._models = models
        self._context_map = {m["id"]: m["context_length"] for m in models}
        self._last_fetch = now
        return models

    def fetch(self, force: bool = False) -> List[Dict[str, Any]]:
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                import threading
                result: List[Dict[str, Any]] = []
                exception: List[Exception] = []
                def _run():
                    try:
                        r = asyncio.run(self.fetch_async(force))
                        result.extend(r)
                    except Exception as e:
                        exception.append(e)
                t = threading.Thread(target=_run, daemon=True)
                t.start()
                t.join(timeout=15)
                if exception:
                    pass
                return result if result else (self._models or [])
        except RuntimeError:
            return asyncio.run(self.fetch_async(force))
        return self._models or []

    def get_context_length(self, model_id: str) -> int:
        if model_id in self._context_map:
            return self._context_map[model_id]
        mid_lower = model_id.lower()
        if "gemini" in mid_lower:
            for k, v in self._context_map.items():
                k_lower = k.lower()
                if "gemini" in k_lower:
                    if "flash" in mid_lower and "flash" in k_lower:
                        return v
                    if "pro" in mid_lower and "pro" in k_lower:
                        return v
        return HARDCODED_CONTEXT.get(model_id, 220000)

    def get_model_list(self) -> List[Dict[str, Any]]:
        return self._models or self.fetch()

    def get_model_ids(self) -> List[str]:
        return [m["id"] for m in self.get_model_list()]

    def get_display_name(self, model_id: str) -> str:
        for m in self._models:
            if m["id"] == model_id:
                return m.get("display", model_id)
        return model_id


model_registry = ModelRegistry()


async def get_optimal_import_concurrency(
    config,  # TranslatorConfig
    model_alias: str = "gemini-flash-lite",
    writer_qa_reserved: int = 2,
    safety_factor: float = 0.4,
    min_concurrent: int = 5,
    max_concurrent: int = 30,
) -> int:
    """Tính số luồng concurrent tối ưu cho import dựa trên RPM thực từ router.

    Logic:
        1. Nếu config.import_max_concurrent > 0 → dùng override thủ công
        2. Ngược lại: query router /v1beta/models để lấy RPM của model_alias
        3. Tính: concurrent = floor(RPM_total / 60 * safety_factor)
        4. Trừ đi writer_qa_reserved để luôn còn slot cho writer + QA
        5. Clamp vào [min_concurrent, max_concurrent]

    Args:
        config: TranslatorConfig với api_endpoint và auth_key
        model_alias: Model đang dùng cho import ("gemini-flash-lite")
        writer_qa_reserved: Số slot dành riêng cho writer + QA (mặc định 2)
        safety_factor: Hệ số an toàn (0.4 = dùng 40% RPM capacity)
        min_concurrent: Tối thiểu
        max_concurrent: Tối đa tuyệt đối

    Returns:
        Số concurrent hợp lý
    """
    # Override thủ công từ config
    if config.import_max_concurrent > 0:
        return config.import_max_concurrent

    # Thử query router để lấy RPM thực
    rpm_total: int = 0
    try:
        base = config.api_endpoint.rstrip("/")
        # Strip /v1 suffix để build đúng path
        if base.endswith("/v1"):
            base = base[:-3]
        # Query /v1beta/models để lấy metadata (router có context_length)
        url = f"{base}/v1beta/models"
        headers = {}
        if config.auth_key:
            headers["Authorization"] = f"Bearer {config.auth_key}"
            headers["x-api-key"] = config.auth_key

        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                raw = data.get("models", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
                for m in raw:
                    mid = m.get("id") or m.get("name", "")
                    if mid.startswith("models/"):
                        mid = mid[len("models/"):]
                    if mid == model_alias:
                        # Router v2 có thể expose rpm trong metadata
                        limits = m.get("limits") or m.get("rateLimit") or {}
                        if isinstance(limits, dict):
                            rpm_total = int(limits.get("requestsPerMinute", 0) or limits.get("rpm", 0))
                        break
    except Exception:
        pass

    # Fallback: dùng /v1/models (openai-compat) để estimate
    if rpm_total == 0:
        try:
            base = config.api_endpoint.rstrip("/")
            url = f"{base}/models"
            headers = {}
            if config.auth_key:
                headers["Authorization"] = f"Bearer {config.auth_key}"
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    raw = data.get("data", []) if isinstance(data, dict) else []
                    for m in raw:
                        mid = m.get("id", "")
                        if mid == model_alias:
                            limits = m.get("limits") or m.get("rateLimit") or {}
                            if isinstance(limits, dict):
                                rpm_total = int(limits.get("requestsPerMinute", 0) or limits.get("rpm", 0))
                            break
        except Exception:
            pass

    # Nếu không lấy được từ router → dùng fallback heuristic dựa trên endpoint
    if rpm_total == 0:
        # Local router thường có nhiều key → ước tính 600+ RPM an toàn
        # External API → ước tính 15 RPM
        endpoint = config.api_endpoint.lower()
        if "127.0.0.1" in endpoint or "localhost" in endpoint:
            # Hạ RPM toàn cục ước tính từ 600 xuống 90 để phù hợp hạn ngạch vùng thực tế của tài khoản free
            rpm_total = 90  # conservative estimate cho local router dưới hạn ngạch vùng
        else:
            rpm_total = 15   # free tier external

    # Tính concurrent: RPM → req/s → concurrent an toàn
    # Giả sử mỗi request mất ~4-8s (avg 6s) → concurrent = RPM/60 * avg_latency * safety
    # Đơn giản hơn: concurrent = floor(RPM * safety_factor / 60 * avg_latency)
    # avg_latency = 6s → concurrent = RPM * 0.4 * 6 / 60 = RPM * 0.04
    # Với safety_factor=0.4: concurrent = rpm_total * safety_factor / 60 * 6
    avg_latency_sec = 6.0
    computed = int(rpm_total * safety_factor / 60 * avg_latency_sec)

    # Trừ reserved slots cho writer + QA
    computed = max(min_concurrent, computed - writer_qa_reserved)
    result = min(computed, max_concurrent)

    return result
