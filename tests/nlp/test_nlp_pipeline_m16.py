"""Unit tests for Milestone 16 NLP pipeline enhancements.

Validates:
- BaseTextEmbedder protocol conformance for TextFeatureReducer
- SentenceTransformerEmbedder functionality and dimension properties
- Pluggable embedding interfaces for benchmarking
"""

import unittest
import numpy as np

from src.nlp.nlp_pipeline import (
    BaseTextEmbedder,
    SentenceTransformerEmbedder,
    TextFeatureReducer,
    ensure_text_dimensions,
)


class NLPMilestone16Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.sample_texts = [
            "Senior machine learning engineer building recommendation pipelines with Python and PyTorch.",
            "Full stack software developer building React web interfaces and FastAPI microservices.",
            "Cloud architect designing Kubernetes clusters and automated CI/CD pipelines.",
        ]

    def test_text_feature_reducer_conforms_to_base_text_embedder(self) -> None:
        reducer = TextFeatureReducer(n_components=50)
        self.assertIsInstance(reducer, BaseTextEmbedder)
        self.assertEqual(reducer.dimension, 50)

    def test_sentence_transformer_embedder_conforms_to_base_text_embedder(self) -> None:
        embedder = SentenceTransformerEmbedder(dimension=384, mock_mode=True)
        self.assertIsInstance(embedder, BaseTextEmbedder)
        self.assertEqual(embedder.dimension, 384)

    def test_sentence_transformer_embedder_encodes_texts(self) -> None:
        embedder = SentenceTransformerEmbedder(dimension=384, mock_mode=True, normalize_embeddings=True)
        vectors = embedder.transform(self.sample_texts)

        self.assertEqual(vectors.shape, (3, 384))
        # Norm of each normalized embedding should be close to 1.0
        for vec in vectors:
            self.assertAlmostEqual(float(np.linalg.norm(vec)), 1.0, places=4)

    def test_sentence_transformer_fit_transform_parity(self) -> None:
        embedder = SentenceTransformerEmbedder(dimension=128, mock_mode=True)
        ft_vectors = embedder.fit_transform(self.sample_texts)
        t_vectors = embedder.transform(self.sample_texts)

        np.testing.assert_allclose(ft_vectors, t_vectors)

    def test_ensure_text_dimensions_supports_custom_dimensions(self) -> None:
        matrix = np.ones((4, 25))
        # Expand from 25 to 75
        expanded = ensure_text_dimensions(matrix, expected_dimensions=75)
        self.assertEqual(expanded.shape, (4, 75))
        np.testing.assert_allclose(expanded[:, :25], 1.0)
        np.testing.assert_allclose(expanded[:, 25:], 0.0)

        # Truncate from 75 to 50
        truncated = ensure_text_dimensions(expanded, expected_dimensions=50)
        self.assertEqual(truncated.shape, (4, 50))


if __name__ == "__main__":
    unittest.main()
