"""Synthetic FR-06 math tests; proxy peers are not verified mentor prices."""

import math
import unittest

import numpy as np

from src.interval_synthesizer import FloorExceedsCeilingError, synthesize_corridor, weighted_peer_stddev
from src.spatial_engine import DomainPartitionedKDTreeIndexer


class IntervalSynthesizerTests(unittest.TestCase):
    def test_indexed_peers_use_full_precision_idw_weights(self) -> None:
        vectors = np.zeros((5, 53))
        vectors[:, 0] = [0.0, 0.00000051, 1.0, 2.0, 3.0]
        rates = [100.0, 200.0, 300.0, 400.0, 500.0]
        indexer = DomainPartitionedKDTreeIndexer()
        indexer.fit(vectors, ["mobile"] * 5, verified_rates=rates)

        result = indexer.predict_base_rate(np.zeros(53), "mobile", k=5, epsilon=1e-6)
        peer_rates = [rates[index] for index in result["neighbor_indices"]]
        weights = [1 / (distance**2 + 1e-6) for distance in result["distances"]]
        mean = sum(rate * weight for rate, weight in zip(peer_rates, weights)) / sum(weights)
        expected_sigma = math.sqrt(
            sum(weight * (rate - mean)**2 for rate, weight in zip(peer_rates, weights)) / sum(weights)
        )

        self.assertEqual(result["k_neighbors_used"], 5)
        self.assertAlmostEqual(result["base_predicted_rate"], mean, places=2)
        self.assertAlmostEqual(result["peer_stddev"], expected_sigma, places=9)
        self.assertEqual(result["nearest_neighbors"][0]["distance"], 0.0)

    def test_identical_peers_and_single_peer_have_zero_dispersion(self) -> None:
        self.assertEqual(weighted_peer_stddev([800.0] * 5, [1, 2, 3, 4, 5]), 0.0)
        self.assertEqual(weighted_peer_stddev([800.0], [10.0]), 0.0)
        self.assertEqual(synthesize_corridor(800.0, 0.0, 1.0), {
            "min_quoted_rate": 800.0, "max_quoted_rate": 800.0,
        })

    def test_high_dispersion_domestic_and_export_formulas(self) -> None:
        sigma = weighted_peer_stddev([100.0, 1000.0], [1.0, 1.0])
        self.assertEqual(sigma, 450.0)
        domestic = synthesize_corridor(550.0, sigma, 1.0)
        export = synthesize_corridor(550.0, sigma, 0.51)
        self.assertEqual(domestic["min_quoted_rate"], 275.0)  # default floor is half the base
        self.assertEqual(domestic["max_quoted_rate"], 1112.5)
        self.assertEqual(export["min_quoted_rate"], domestic["min_quoted_rate"])
        self.assertAlmostEqual(export["max_quoted_rate"], 1112.5 * (2 - 0.51))
        self.assertLessEqual(export["min_quoted_rate"], export["max_quoted_rate"])

    def test_explicit_floor_zero_is_not_treated_as_missing(self) -> None:
        self.assertEqual(synthesize_corridor(100.0, 100.0, 1.0)["min_quoted_rate"], 50.0)
        self.assertEqual(synthesize_corridor(100.0, 100.0, 1.0, base_rate_floor=0)["min_quoted_rate"], 25.0)
        self.assertEqual(synthesize_corridor(100.0, 20.0, 1.0, base_rate_floor=105), {
            "min_quoted_rate": 105.0, "max_quoted_rate": 125.0,
        })
        with self.assertRaisesRegex(FloorExceedsCeilingError, "exceeds"):
            synthesize_corridor(100.0, 20.0, 1.0, base_rate_floor=126)

    def test_empty_misaligned_and_invalid_evidence_fails_closed(self) -> None:
        for rates, weights in [([], []), ([100.0], []), ([100.0], [0.0]),
                               ([100.0], [math.nan]), ([-100.0], [1.0]),
                               ([math.inf], [1.0]), ([100.0], [-1.0])]:
            with self.subTest(rates=rates, weights=weights), self.assertRaises(ValueError):
                weighted_peer_stddev(rates, weights)

        for kwargs in [{"base_rate": math.nan}, {"peer_stddev": -1.0},
                       {"bilateral_factor": 0.0}, {"bilateral_factor": math.inf},
                       {"base_rate_floor": -1.0}, {"base_rate_floor": math.inf}]:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                synthesize_corridor(**{"base_rate": 100, "peer_stddev": 10, "bilateral_factor": 1, **kwargs})


if __name__ == "__main__":
    unittest.main()
