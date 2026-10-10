package edu.strathmore.pricing.data.repository

import edu.strathmore.pricing.data.network.dto.PeerMatchDTO
import edu.strathmore.pricing.data.network.dto.PricingQueryDTO
import edu.strathmore.pricing.data.network.dto.PredictionResultDTO
import edu.strathmore.pricing.domain.IPricingRepository
import edu.strathmore.pricing.domain.PricingFailure
import edu.strathmore.pricing.domain.PricingOutcome
import kotlinx.coroutines.delay

/**
 * Deterministic, network-free [IPricingRepository] used for debug-build offline UI review (see
 * di/AppContainer.kt), Compose previews, and ViewModel unit tests. Never used in release builds.
 */
class FakePricingRepository(
    private val simulatedLatencyMs: Long = 600L,
    private val resultProvider: (PricingQueryDTO) -> PricingOutcome<PredictionResultDTO> = ::defaultSuccess,
) : IPricingRepository {

    override suspend fun calculateOptimalRate(query: PricingQueryDTO): PricingOutcome<PredictionResultDTO> {
        delay(simulatedLatencyMs)
        return resultProvider(query)
    }

    companion object {
        fun defaultSuccess(query: PricingQueryDTO): PricingOutcome<PredictionResultDTO> {
            val base = 2500f
            val surcharge = if (query.mentorCountry.equals("KE", ignoreCase = true)) 57f else 0f
            return PricingOutcome.Success(
                PredictionResultDTO(
                    basePredictedRate = base,
                    mpesaTariffSurcharge = surcharge,
                    finalQuotedRate = base + surcharge,
                    minQuotedRate = base * 0.85f,
                    maxQuotedRate = base * 1.35f,
                    kNeighborsUsed = 5,
                    bilateralArbitrageFactor = if (query.mentorCountry == query.clientCountry) 1.0f else 0.51f,
                    confidenceScore = 0.0f,
                    comparables = listOf(
                        PeerMatchDTO("list_001", "Senior Android Architect", 2600f, 0.92f, 0.41f),
                        PeerMatchDTO("list_045", "Kotlin Mentor", 2400f, 0.88f, 0.55f),
                    ),
                    reason = "Weighted from 5 indexed peers in KES/hour; corridor excludes the M-Pesa surcharge.",
                    timestamp = "2026-10-10T00:00:00Z",
                ),
            )
        }

        fun failure(failure: PricingFailure): (PricingQueryDTO) -> PricingOutcome<PredictionResultDTO> =
            { PricingOutcome.Failure(failure) }
    }
}

