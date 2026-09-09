import tempfile
import time
import unittest

import numpy as np

from src.nlp_pipeline import TextFeatureReducer


class NlpVectorizerSvdTests(unittest.TestCase):
    def setUp(self) -> None:
        # Build an alphabetic corpus so sanitization keeps token diversity for 50-D SVD.
        alphabet = "abcdefghijklmnopqrstuvwxyz"
        def alpha_token(index: int) -> str:
            base = len(alphabet)
            chars = []
            value = index
            while True:
                chars.append(alphabet[value % base])
                value //= base
                if value == 0:
                    break
            return "tok" + "".join(chars)

        self.training_texts = [
            " ".join(
                [
                    "data",
                    "science",
                    "machine",
                    "learning",
                    "python",
                    "analytics",
                    alpha_token(i),
                    alpha_token(i + 200),
                    alpha_token(i + 400),
                ]
            )
            for i in range(180)
        ]
        self.query_text = "Experienced python machine learning engineer building analytics API"

    def test_fit_transform_returns_requested_dimension(self) -> None:
        reducer = TextFeatureReducer(n_components=50, max_features=8000)
        vectors = reducer.fit_transform(self.training_texts)

        self.assertEqual(vectors.shape[0], len(self.training_texts))
        self.assertEqual(vectors.shape[1], 50)

    def test_transform_is_stable_after_fit(self) -> None:
        reducer = TextFeatureReducer(n_components=50, max_features=8000)
        reducer.fit_transform(self.training_texts)

        first = reducer.transform([self.query_text])
        second = reducer.transform([self.query_text])
        np.testing.assert_allclose(first, second, atol=1e-9)

    def test_save_and_load_artifacts_preserve_output_shape(self) -> None:
        reducer = TextFeatureReducer(n_components=50, max_features=8000)
        reducer.fit_transform(self.training_texts)

        with tempfile.TemporaryDirectory() as tmp_dir:
            reducer.save_artifacts(tmp_dir)
            restored = TextFeatureReducer.load_artifacts(tmp_dir)

            original_vec = reducer.transform([self.query_text])
            restored_vec = restored.transform([self.query_text])
            self.assertEqual(original_vec.shape, restored_vec.shape)
            np.testing.assert_allclose(original_vec, restored_vec, atol=1e-9)

    def test_explained_variance_sum_is_bounded(self) -> None:
        reducer = TextFeatureReducer(n_components=50, max_features=8000)
        reducer.fit_transform(self.training_texts)

        variance_sum = reducer.explained_variance_sum()
        self.assertGreater(variance_sum, 0.0)
        self.assertLessEqual(variance_sum, 1.0)

    def test_transform_latency_reasonable_for_single_document(self) -> None:
        reducer = TextFeatureReducer(n_components=50, max_features=8000)
        reducer.fit_transform(self.training_texts)

        loops = 60
        start = time.perf_counter()
        for _ in range(loops):
            reducer.transform([self.query_text])
        avg_ms = ((time.perf_counter() - start) / loops) * 1000.0

        # Wide threshold to avoid flaky CI while still guarding obvious regressions.
        self.assertLess(avg_ms, 200.0)


if __name__ == "__main__":
    unittest.main()

