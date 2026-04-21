import unittest

from src.classifier import SYSTEM_PROMPT, build_user_prompt, parse_suggestion
from src.config import CATEGORY_MAP


class ClassifierTests(unittest.TestCase):
    def test_system_prompt_mentions_current_category_folders(self) -> None:
        for folder in CATEGORY_MAP.values():
            self.assertIn(folder, SYSTEM_PROMPT)

    def test_system_prompt_expands_reference_category_for_lookup_material(self) -> None:
        self.assertIn("科普", SYSTEM_PROMPT)
        self.assertIn("百科", SYSTEM_PROMPT)
        self.assertIn("知识点罗列", SYSTEM_PROMPT)
        self.assertIn("查阅", SYSTEM_PROMPT)

    def test_build_user_prompt_truncates_content(self) -> None:
        prompt = build_user_prompt("标题", "abcdef", limit=4)
        self.assertIn("abcd", prompt)
        self.assertNotIn("abcdef", prompt)

    def test_parse_suggestion_accepts_valid_payload(self) -> None:
        payload = (
            '{"category_key":"2","folder":"02_safety","confidence":0.75,"reason":"偏向工作与收入"}'
        )
        suggestion = parse_suggestion(payload)

        self.assertEqual(suggestion.category_key, "2")
        self.assertEqual(suggestion.folder, "02_safety")
        self.assertAlmostEqual(suggestion.confidence, 0.75)

    def test_parse_suggestion_rejects_invalid_folder(self) -> None:
        payload = '{"category_key":"2","folder":"06_journal","confidence":0.75,"reason":"错误"}'

        with self.assertRaises(ValueError):
            parse_suggestion(payload)

    def test_parse_suggestion_rejects_missing_fields(self) -> None:
        with self.assertRaises(ValueError):
            parse_suggestion("{}")


if __name__ == "__main__":
    unittest.main()
