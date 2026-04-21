from __future__ import annotations

import json
import time
from dataclasses import dataclass
from hashlib import sha256
from typing import TYPE_CHECKING

from .config import CATEGORY_MAP, AppConfig
from .scanner import NoteFile

if TYPE_CHECKING:
    from .cache import SuggestionCache

SYSTEM_PROMPT = (
    "你是一个个人笔记分类助手。给定一段 Markdown 笔记（标题 + 正文），"
    "从以下 7 个类别里选唯一一个最合适的：\n\n"
    "1 -> 01_physiological：为了活着必须做的基本事情（饮食、身体、起居、生活琐事）\n"
    "2 -> 02_safety：为了挣钱、理财、工作、保障未来的事情\n"
    "3 -> 03_leisure：好玩的、放松心情的事情（游戏、影视、旅行、娱乐）\n"
    "4 -> 04_belonging：社交、人际关系、亲友往来、送礼人情\n"
    "5 -> 05_esteem：热爱、兴趣、学习、项目、成就感相关\n"
    "6 -> 06_journal：心情记录、日记类随笔\n"
    "7 -> 07_reference：平常用不到、仅供日后翻查参考的资料；"
    "包括杂乱信息、科普、百科、知识点罗列、说明性整理、速查型内容。"
    "即使是用户自己写的，只要更像查阅型资料而不是持续投入的项目/学习过程，"
    "也优先归到这个分类\n\n"
    "只返回 JSON（不要任何其它文本）：\n"
    '{"category_key":"<1-7>","folder":"<对应英文目录名>",'
    '"confidence":<0~1 的小数>,"reason":"<15 字内简短理由>"}'
)


@dataclass(frozen=True)
class ClassificationSuggestion:
    category_key: str
    folder: str
    confidence: float
    reason: str


def build_user_prompt(title: str, content: str, limit: int) -> str:
    trimmed = content[:limit].strip()
    return f"标题：{title}\n正文（可能已截断）：\n{trimmed}"


def build_note_hash(note: NoteFile, limit: int) -> str:
    payload = f"{note.title}\n{note.content[:limit]}"
    return sha256(payload.encode("utf-8", errors="ignore")).hexdigest()


def parse_suggestion(raw_content: str) -> ClassificationSuggestion:
    try:
        payload = json.loads(raw_content)
        category_key = str(payload["category_key"])
        folder = str(payload["folder"])
        confidence = float(payload["confidence"])
        reason = str(payload["reason"]).strip()
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise ValueError("LLM returned an invalid suggestion payload.") from exc

    if category_key not in CATEGORY_MAP:
        raise ValueError(f"Invalid category key: {category_key}")
    if folder != CATEGORY_MAP[category_key]:
        raise ValueError("Folder does not match category key.")
    if not 0.0 <= confidence <= 1.0:
        raise ValueError("Confidence must be between 0 and 1.")

    return ClassificationSuggestion(
        category_key=category_key,
        folder=folder,
        confidence=confidence,
        reason=reason[:15],
    )


class SiliconFlowClassifier:
    def __init__(
        self,
        config: AppConfig,
        persistent_cache: SuggestionCache | None = None,
    ) -> None:
        self._config = config
        self._memory_cache: dict[str, ClassificationSuggestion] = {}
        self._persistent_cache = persistent_cache
        self._client = None
        if config.llm_enabled:
            try:
                from openai import OpenAI
            except ImportError as exc:  # pragma: no cover - depends on local environment
                raise RuntimeError("openai package is required when LLM is enabled.") from exc
            self._client = OpenAI(
                api_key=config.siliconflow_api_key,
                base_url=config.siliconflow_base_url,
            )

    @property
    def enabled(self) -> bool:
        return self._client is not None

    def cache_key_for(self, note: NoteFile) -> str:
        return build_note_hash(note, self._config.llm_content_limit)

    def peek_cached(self, note: NoteFile) -> ClassificationSuggestion | None:
        cache_key = self.cache_key_for(note)
        cached = self._memory_cache.get(cache_key)
        if cached is not None:
            return cached
        if self._persistent_cache is not None:
            persistent = self._persistent_cache.get(cache_key)
            if persistent is not None:
                self._memory_cache[cache_key] = persistent
                return persistent
        return None

    def clear_cache_for(self, note: NoteFile) -> None:
        cache_key = self.cache_key_for(note)
        self._memory_cache.pop(cache_key, None)
        if self._persistent_cache is not None:
            self._persistent_cache.pop(cache_key)

    def suggest(self, note: NoteFile, *, bypass_cache: bool = False) -> ClassificationSuggestion:
        if not self._client:
            raise RuntimeError("LLM is disabled because SILICONFLOW_API_KEY is missing.")

        cache_key = self.cache_key_for(note)
        if not bypass_cache:
            cached = self.peek_cached(note)
            if cached is not None:
                return cached

        user_prompt = build_user_prompt(note.title, note.content, self._config.llm_content_limit)
        attempts = self._config.llm_max_retry + 1

        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                response = self._client.chat.completions.create(
                    model=self._config.llm_model,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.2,
                    timeout=self._config.llm_timeout_sec,
                )
                suggestion = parse_suggestion(response.choices[0].message.content or "{}")
                self._memory_cache[cache_key] = suggestion
                if self._persistent_cache is not None:
                    self._persistent_cache.set(cache_key, suggestion)
                return suggestion
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt >= attempts - 1:
                    break
                time.sleep(1)

        detail = str(last_error).strip() if last_error is not None else "unknown error"
        raise RuntimeError(
            f"Failed to fetch LLM suggestion after retries. Last error: {detail}"
        ) from last_error
