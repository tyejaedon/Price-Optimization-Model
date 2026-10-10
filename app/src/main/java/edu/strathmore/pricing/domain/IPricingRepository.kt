package edu.strathmore.pricing.domain

import edu.strathmore.pricing.data.network.dto.PricingQueryDTO
import edu.strathmore.pricing.data.network.dto.PredictionResultDTO

/**
 * Mirrors the class diagram's `IPricingRepository` boundary. The ViewModel depends only on this
 * interface, never on Retrofit/Firebase types directly, so it is testable with a fake (see
 * data/repository/FakePricingRepository.kt and the PricingViewModel unit tests).
 */
interface IPricingRepository {
    suspend fun calculateOptimalRate(query: PricingQueryDTO): PricingOutcome<PredictionResultDTO>
}

