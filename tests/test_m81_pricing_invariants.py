import os
import tempfile
import unittest
from pathlib import Path

import numpy as np

from src.ingest_multisource import (
    build_macro_lookup,
    compute_bilateral_arbitrage_factor,
    load_macro_lookup_table,
)
from src.macro_arbitrage import HYBRID_VECTOR_DIMENSIONS, fuse_coordinates
from src.spatial_engine import DomainPartitionedKDTreeIndexer
from src.tariff_evaluator import MpesaTariffEvaluator


class M81PricingInvariantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        repo_root = Path(__file__).resolve().parent.parent
        raw_fixture_dir = str(repo_root / "tests" / "fixtures" / "raw")
        with tempfile.TemporaryDirectory() as tmp_dir:
            lookup_path = os.path.join(tmp_dir, "macro_lookup_table.json")
            build_macro_lookup(raw_fixture_dir, lookup_path)
            cls.macro_records = load_macro_lookup_table(lookup_path)

        cls.tariff_evaluator = MpesaTariffEvaluator.from_csv(
            str(repo_root / "tests" / "fixtures" / "raw" / "Mpesa_Tarrifs" / "tarrifs_full_schedule.csv")
        )

    def test_domestic_parity_is_one(self) -> None:
        parity = compute_bilateral_arbitrage_factor("KE", "KE", self.macro_records)

        self.assertAlmostEqual(parity, 1.0, places=9)

    def test_export_corridor_parity_exceeds_domestic(self) -> None:
        domestic = compute_bilateral_arbitrage_factor("KE", "KE", self.macro_records)
        export = compute_bilateral_arbitrage_factor("KE", "US", self.macro_records)

        self.assertEqual(domestic, 1.0)
        self.assertGreater(export, domestic)
        self.assertTrue(np.isfinite(export))

    def test_fusion_is_53d_immutable_and_deterministic(self) -> None:
        text = np.linspace(0.0, 1.0, 50)
        metadata = np.asarray([0.2, 0.4, 0.6], dtype=float)

        first = fuse_coordinates(text, metadata)
        second = fuse_coordinates(text, metadata)

        self.assertEqual(first.shape, (HYBRID_VECTOR_DIMENSIONS,))
        self.assertFalse(first.flags.writeable)
        np.testing.assert_allclose(first, second, atol=1e-12)
        np.testing.assert_allclose(first[:50], text)
        np.testing.assert_allclose(first[50:], metadata)

    def test_fusion_rejects_malformed_and_nonfinite_inputs(self) -> None:
        with self.assertRaisesRegex(ValueError, "dense_text_vector"):
            fuse_coordinates(np.ones(49), np.ones(3))
        with self.assertRaisesRegex(ValueError, "normalized_metadata"):
            fuse_coordinates(np.ones(50), np.ones(2))
        with self.assertRaisesRegex(ValueError, "non-finite"):
            fuse_coordinates(np.ones(50), np.asarray([0.2, np.nan, 0.4]))

    def test_domestic_tariff_and_international_bypass(self) -> None:
        domestic = self.tariff_evaluator.evaluate_quote(4500.0, "KE")
        international = self.tariff_evaluator.evaluate_quote(4500.0, "US")

        self.assertEqual(domestic["mpesa_tariff_surcharge"], 55.0)
        self.assertEqual(domestic["final_quoted_rate"], 4555.0)
        self.assertEqual(international["mpesa_tariff_surcharge"], 0.0)
        self.assertEqual(international["final_quoted_rate"], 4500.0)

    def test_tariff_edges_are_deterministic(self) -> None:
        expected_edges = {
            2500.0: 33.0,
            2501.0: 55.0,
            5000.0: 55.0,
            5001.0: 78.0,
            15001.0: 105.0,
        }
        for amount, expected_fee in expected_edges.items():
            with self.subTest(amount=amount):
                self.assertEqual(self.tariff_evaluator.compute_surcharge(amount, "KE"), expected_fee)

    def test_exact_match_idw_prediction_is_finite_and_explainable(self) -> None:
        vectors = np.zeros((3, HYBRID_VECTOR_DIMENSIONS), dtype=float)
        vectors[:, 0] = np.asarray([0.0, 0.1, 0.2])
        rates = [2000.0, 2500.0, 3000.0]
        indexer = DomainPartitionedKDTreeIndexer(minimum_partition_size=1)
        indexer.fit(vectors, ["data_ai"] * 3, verified_rates=rates)

        result = indexer.predict_base_rate(vectors[1], "data_ai", k=3)

        self.assertEqual(result["base_predicted_rate"], 2500.0)
        self.assertEqual(result["nearest_neighbors"][0]["distance"], 0.0)
        self.assertEqual(result["nearest_neighbors"][0]["similarity_score"], 1.0)
        self.assertTrue(all(np.isfinite(peer["distance"]) for peer in result["nearest_neighbors"]))


if __name__ == "__main__":
    unittest.main()

