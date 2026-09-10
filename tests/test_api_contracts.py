import unittest

from pydantic import ValidationError

from src.api_contracts import HealthResponseDTO, PeerMatchDTO, PredictionResultDTO, PricingQueryDTO


class ApiContractsTests(unittest.TestCase):
    def test_pricing_query_accepts_documented_request_and_normalizes_country_codes(self) -> None:
        payload = PricingQueryDTO(
            raw_description="Senior Android engineer specializing in Kotlin and Jetpack Compose UI architecture.",
            selected_industry="SOFTWARE_ENG",
            mentor_country="ke",
            client_country="us",
            competitiveness_score=0.65,
            market_saturation_score=0.45,
        )

        self.assertEqual(payload.mentor_country, "KE")
        self.assertEqual(payload.client_country, "US")
        self.assertEqual(payload.competitiveness_score, 0.65)

    def test_pricing_query_rejects_bad_bounds_and_unknown_fields(self) -> None:
        base_payload = {
            "raw_description": "A sufficiently long consulting profile description for validation.",
            "selected_industry": "SOFTWARE_ENG",
            "mentor_country": "KE",
            "client_country": "US",
            "competitiveness_score": 1.5,
            "market_saturation_score": 0.45,
        }
        with self.assertRaises(ValidationError):
            PricingQueryDTO(**base_payload)

        valid_payload = {**base_payload, "competitiveness_score": 0.5, "unexpected": True}
        with self.assertRaises(ValidationError):
            PricingQueryDTO(**valid_payload)

    def test_prediction_response_matches_documented_schema(self) -> None:
        response = PredictionResultDTO(
            base_predicted_rate=4700.0,
            mpesa_tariff_surcharge=55.0,
            final_quoted_rate=4755.0,
            currency="KES",
            bilateral_arbitrage_factor=0.51,
            nearest_neighbors=[
                PeerMatchDTO(
                    peer_index=1402,
                    distance=0.214,
                    verified_rate=4900.0,
                    similarity_score=0.823,
                    idw_weight=0.6,
                )
            ],
        )

        dumped = response.model_dump()
        self.assertEqual(dumped["final_quoted_rate"], 4755.0)
        self.assertEqual(dumped["nearest_neighbors"][0]["peer_index"], 1402)

    def test_prediction_response_rejects_invalid_similarity_and_inconsistent_final_rate(self) -> None:
        with self.assertRaises(ValidationError):
            PeerMatchDTO(peer_index=1, distance=0.2, verified_rate=1000.0, similarity_score=0.0)

        with self.assertRaises(ValidationError):
            PredictionResultDTO(
                base_predicted_rate=4700.0,
                mpesa_tariff_surcharge=55.0,
                final_quoted_rate=4700.0,
                currency="KES",
                bilateral_arbitrage_factor=0.51,
                nearest_neighbors=[
                    PeerMatchDTO(peer_index=1, distance=0.2, verified_rate=1000.0, similarity_score=0.8)
                ],
            )

    def test_health_response_is_explicit_about_firestore_state(self) -> None:
        response = HealthResponseDTO(status="HEALTHY", models_loaded=True, database="firestore")

        self.assertEqual(response.model_dump(), {"status": "HEALTHY", "models_loaded": True, "database": "firestore"})


if __name__ == "__main__":
    unittest.main()

