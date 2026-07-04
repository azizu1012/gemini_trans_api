"""
API Manager Module - Tối giản hóa cho Router API v2
Không còn duy trì key pools, rotation counters hay daily quotas cục bộ.
"""
import os
import json
import httpx
from typing import Optional, List, Dict, Any
from .config import TranslatorConfig


class APIManagerV2:
    """
    APIManagerV2 tối giản:
    - Quản lý api_endpoint và auth_key.
    - Cung cấp phương thức fetch_available_models() động từ Router API v2.
    """

    def __init__(self, config: TranslatorConfig):
        self.config = config
        self.api_endpoint = config.api_endpoint
        self.auth_key = config.auth_key

    def update_config(self, endpoint: str, auth_key: str):
        """Cập nhật endpoint và key mới"""
        self.api_endpoint = endpoint
        self.auth_key = auth_key
        self.config.api_endpoint = endpoint
        self.config.auth_key = auth_key

    async def fetch_available_models_async(self) -> List[str]:
        """Lấy danh sách các model khả dụng từ endpoint (bất đồng bộ)"""
        if not self.api_endpoint:
            return []

        url = self.api_endpoint.rstrip("/")
        if not url.endswith("/models"):
            url = f"{url}/models"

        headers = {}
        if self.auth_key:
            headers["Authorization"] = f"Bearer {self.auth_key}"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    models = []
                    # Chuẩn OpenAI trả về danh sách dạng {"data": [{"id": "model-id", ...}]}
                    if isinstance(data, dict) and "data" in data:
                        for m in data["data"]:
                            if isinstance(m, dict) and "id" in m:
                                models.append(m["id"])
                    elif isinstance(data, list):
                        # Đề phòng endpoint trả về list thuần
                        models = data
                    return sorted(models)
                else:
                    print(f"⚠️ Lỗi quét model từ endpoint: HTTP {response.status_code}")
        except Exception as e:
            print(f"⚠️ Lỗi kết nối endpoint khi quét model: {e}")
        return []

    def fetch_available_models(self) -> List[str]:
        """Lấy danh sách các model khả dụng từ endpoint (đồng bộ)"""
        if not self.api_endpoint:
            return []

        url = self.api_endpoint.rstrip("/")
        if not url.endswith("/models"):
            url = f"{url}/models"

        headers = {}
        if self.auth_key:
            headers["Authorization"] = f"Bearer {self.auth_key}"

        try:
            response = httpx.get(url, headers=headers, timeout=10.0)
            if response.status_code == 200:
                data = response.json()
                models = []
                if isinstance(data, dict) and "data" in data:
                    for m in data["data"]:
                        if isinstance(m, dict) and "id" in m:
                            models.append(m["id"])
                elif isinstance(data, list):
                    models = data
                return sorted(models)
            else:
                print(f"⚠️ Lỗi quét model từ endpoint: HTTP {response.status_code}")
        except Exception as e:
            print(f"⚠️ Lỗi kết nối endpoint khi quét model: {e}")
        return []

    def call_api_sync(
        self,
        model: str,
        system_prompt: str,
        user_content: str,
        temperature: float = 0.2
    ) -> str:
        """Thực hiện gọi API đồng bộ sử dụng google-genai client với retry"""
        from google import genai
        from google.genai import types
        import time
        import random
        
        base_url = self.api_endpoint.rstrip("/")
        if base_url.endswith("/v1"):
            base_url = base_url[:-3]
            
        client = genai.Client(
            api_key=self.auth_key or "sk-no-key-required",
            http_options={"base_url": base_url}
        )
        
        retries = 0
        delay = getattr(self.config, 'retry_initial_delay', 6.0)
        limit = getattr(self.config, 'retry_limit', 6)
        
        while True:
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=user_content,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        temperature=temperature,
                        tools=[]
                    )
                )
                return (response.text or "").strip()
            except Exception as e:
                retries += 1
                if retries > limit:
                    raise RuntimeError(f"Lỗi gọi API đồng bộ ({model}) sau {limit} lần thử: {e}")
                
                err_str = str(e).lower()
                is_rate_limit = "429" in err_str or "rate_limit" in err_str or "quota" in err_str or "exhausted" in err_str
                
                sleep_time = delay * (1.5 ** (retries - 1)) + random.uniform(0, 2)
                sleep_time = min(sleep_time, getattr(self.config, 'retry_max_delay', 30.0))
                
                level = "RATE_LIMIT" if is_rate_limit else "ERROR"
                print(f"⚠️ [{level}] Lỗi gọi API đồng bộ ({model}): {e}. Đang thử lại lần {retries}/{limit} sau {sleep_time:.1f}s...")
                time.sleep(sleep_time)
