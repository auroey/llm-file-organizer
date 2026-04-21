import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.cache import CACHE_SCHEMA_VERSION, SuggestionCache
from src.classifier import ClassificationSuggestion


def _sample_suggestion() -> ClassificationSuggestion:
    return ClassificationSuggestion(
        category_key="2",
        folder="02_safety",
        confidence=0.83,
        reason="工作理财相关",
    )


class SuggestionCacheTests(unittest.TestCase):
    def test_set_writes_to_disk_and_reloads(self) -> None:
        with TemporaryDirectory() as directory:
            cache_path = Path(directory) / ".llm_cache.json"
            cache = SuggestionCache(cache_path)
            cache.set("hash-a", _sample_suggestion())

            self.assertTrue(cache_path.exists())
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], CACHE_SCHEMA_VERSION)
            self.assertEqual(payload["entries"]["hash-a"]["folder"], "02_safety")

            reloaded = SuggestionCache(cache_path)
            suggestion = reloaded.get("hash-a")
            self.assertIsNotNone(suggestion)
            self.assertEqual(suggestion.category_key, "2")

    def test_pop_removes_entry(self) -> None:
        with TemporaryDirectory() as directory:
            cache = SuggestionCache(Path(directory) / ".llm_cache.json")
            cache.set("hash-a", _sample_suggestion())
            cache.pop("hash-a")
            self.assertFalse(cache.has("hash-a"))

    def test_ignores_invalid_payload(self) -> None:
        with TemporaryDirectory() as directory:
            cache_path = Path(directory) / ".llm_cache.json"
            cache_path.write_text(
                json.dumps(
                    {
                        "schema_version": CACHE_SCHEMA_VERSION,
                        "entries": {
                            "bad": {
                                "category_key": "9",
                                "folder": "nonexistent",
                                "confidence": 0.5,
                                "reason": "x",
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            cache = SuggestionCache(cache_path)
            self.assertIsNone(cache.get("bad"))

    def test_prune_drops_unknown_hashes(self) -> None:
        with TemporaryDirectory() as directory:
            cache = SuggestionCache(Path(directory) / ".llm_cache.json")
            cache.set("keep", _sample_suggestion())
            cache.set("drop", _sample_suggestion())
            removed = cache.prune(["keep"])
            self.assertEqual(removed, 1)
            self.assertTrue(cache.has("keep"))
            self.assertFalse(cache.has("drop"))


if __name__ == "__main__":
    unittest.main()
