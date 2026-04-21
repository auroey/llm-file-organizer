import unittest
from pathlib import Path
from unittest.mock import patch

from src.config import load_config


class ConfigTests(unittest.TestCase):
    def test_load_config_uses_generic_default_source_dir(self) -> None:
        fake_home = Path("/tmp/test-home")
        with patch("src.config.Path.home", return_value=fake_home):
            with patch.dict("os.environ", {}, clear=True):
                config = load_config()

        self.assertEqual(config.source_dir, fake_home / "Notes")

    def test_load_config_rejects_pro_models(self) -> None:
        with patch.dict("os.environ", {"LLM_MODEL": "Pro/bad-model"}, clear=False):
            with self.assertRaises(ValueError):
                load_config()

    def test_load_config_requires_https_base_url(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "LLM_MODEL": "deepseek-ai/DeepSeek-V3",
                "SILICONFLOW_BASE_URL": "http://example.com/v1",
            },
            clear=False,
        ):
            with self.assertRaises(ValueError):
                load_config()


if __name__ == "__main__":
    unittest.main()
