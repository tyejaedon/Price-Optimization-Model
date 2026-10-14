import subprocess
import sys
import unittest
from unittest.mock import patch

from src.nlp.nlp_pipeline import _lemmatizer, sanitize_many, sanitize_text


class NlpPipelineSanitizationTests(unittest.TestCase):
    def test_sanitize_text_removes_urls_digits_and_punctuation(self) -> None:
        raw = "Senior dev!!! Visit https://example.com now. Built 3 APIs in 2026."
        cleaned = sanitize_text(raw)

        self.assertNotIn("http", cleaned)
        self.assertNotIn("2026", cleaned)
        self.assertNotIn("!", cleaned)
        self.assertTrue(cleaned)

    def test_sanitize_text_filters_short_tokens_and_stopwords(self) -> None:
        raw = "I am a data engineer and I do AI in ML for US clients"
        cleaned = sanitize_text(raw)

        tokens = cleaned.split()
        self.assertTrue(all(len(tok) > 2 for tok in tokens))
        self.assertNotIn("and", tokens)
        self.assertIn("data", tokens)

    def test_sanitize_text_is_deterministic(self) -> None:
        raw = "Building analytics dashboards with Python and SQL"
        first = sanitize_text(raw)
        second = sanitize_text(raw)
        self.assertEqual(first, second)

    def test_sanitize_text_handles_empty_input(self) -> None:
        self.assertEqual(sanitize_text(""), "")
        self.assertEqual(sanitize_text("  ...  12!!"), "")

    def test_sanitize_many_preserves_order(self) -> None:
        inputs = ["Data Science with Python", "React app and API", ""]
        outputs = sanitize_many(inputs)

        self.assertEqual(len(outputs), len(inputs))
        self.assertEqual(outputs[2], "")

    def test_unavailable_wordnet_uses_original_token_without_repeated_lookup(self) -> None:
        _lemmatizer.cache_clear()
        try:
            with patch("src.nlp.nlp_pipeline.nltk.data.find", side_effect=LookupError), \
                 patch("src.nlp.nlp_pipeline.nltk.download", return_value=False) as download:
                self.assertIn("software", sanitize_text("Software engineering software"))
                self.assertIn("software", sanitize_text("Software analytics"))
                download.assert_called_once_with("wordnet", quiet=True)
        finally:
            _lemmatizer.cache_clear()

    def test_zipped_wordnet_does_not_attempt_download(self) -> None:
        _lemmatizer.cache_clear()
        try:
            with patch("src.nlp.nlp_pipeline.nltk.data.find", side_effect=[LookupError, object()]) as find, \
                 patch("src.nlp.nlp_pipeline.nltk.download") as download, \
                 patch("src.nlp.nlp_pipeline.WordNetLemmatizer") as lemmatizer:
                lemmatizer.return_value.lemmatize.return_value = "dog"
                self.assertIsNotNone(_lemmatizer())
                self.assertEqual(find.call_count, 2)
                download.assert_not_called()
        finally:
            _lemmatizer.cache_clear()

    def test_cli_runner_emits_sanitized_text(self) -> None:
        cmd = [
            sys.executable,
            "-m",
            "src.nlp.nlp_pipeline",
            "--text",
            "NLP + AI for 2026! Visit www.example.org",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertNotIn("www", result.stdout.lower())
        self.assertNotIn("2026", result.stdout)


if __name__ == "__main__":
    unittest.main()
