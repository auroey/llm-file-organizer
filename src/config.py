from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - fallback for minimal test environments
    def load_dotenv() -> bool:
        return False

CATEGORY_MAP = {
    "1": "01_physiological",
    "2": "02_safety",
    "3": "03_leisure",
    "4": "04_belonging",
    "5": "05_esteem",
    "6": "06_journal",
    "7": "07_reference",
}

CATEGORY_LABELS = {
    "1": "01 生活必须",
    "2": "02 未来保障",
    "3": "03 娱乐享受",
    "4": "04 社交人情",
    "5": "05 自我实现",
    "6": "06 心情随笔",
    "7": "07 参考资料",
}


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        return int(raw)
    except ValueError:
        return default


def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class AppConfig:
    source_dir: Path
    siliconflow_api_key: str | None
    siliconflow_base_url: str
    llm_model: str
    llm_timeout_sec: int
    llm_max_retry: int
    llm_content_limit: int
    prefetch_enabled: bool
    prefetch_concurrency: int

    @property
    def llm_enabled(self) -> bool:
        return bool(self.siliconflow_api_key)


def load_config() -> AppConfig:
    load_dotenv()
    llm_model = os.getenv("LLM_MODEL", "deepseek-ai/DeepSeek-V3").strip()
    if llm_model.startswith("Pro/"):
        raise ValueError("Refusing to use Pro model. Please configure a non-Pro DeepSeek model.")

    default_source_dir = Path.home() / "Notes"
    source_dir = Path(os.getenv("SOURCE_DIR", str(default_source_dir))).expanduser()
    base_url = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1").rstrip("/")
    if not base_url.startswith("https://"):
        raise ValueError("SILICONFLOW_BASE_URL must use HTTPS.")

    return AppConfig(
        source_dir=source_dir,
        siliconflow_api_key=os.getenv("SILICONFLOW_API_KEY"),
        siliconflow_base_url=base_url,
        llm_model=llm_model,
        llm_timeout_sec=_get_int("LLM_TIMEOUT_SEC", 10),
        llm_max_retry=_get_int("LLM_MAX_RETRY", 1),
        llm_content_limit=_get_int("LLM_CONTENT_LIMIT", 4000),
        prefetch_enabled=_get_bool("PREFETCH_ENABLED", True),
        prefetch_concurrency=max(1, _get_int("PREFETCH_CONCURRENCY", 4)),
    )
