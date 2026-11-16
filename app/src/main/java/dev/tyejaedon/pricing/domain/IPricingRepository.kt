package dev.tyejaedon.pricing.domain

import dev.tyejaedon.pricing.data.network.dto.MetadataResponseDTO
import dev.tyejaedon.pricing.data.network.dto.PredictionResultDTO
import dev.tyejaedon.pricing.data.network.dto.PricingQueryDTO
import dev.tyejaedon.pricing.data.network.dto.QuoteFeedbackDTO
import dev.tyejaedon.pricing.data.network.dto.QuoteFeedbackRequestDTO
import dev.tyejaedon.pricing.data.network.dto.QuoteHistoryItemDTO
import dev.tyejaedon.pricing.data.network.dto.SelfListingDTO
import dev.tyejaedon.pricing.data.network.dto.SelfListingUpsertDTO
import dev.tyejaedon.pricing.data.network.dto.SelfProfileDTO
import dev.tyejaedon.pricing.data.network.dto.SelfProfileUpsertDTO

/**
 * Mirrors the class diagram's `IPricingRepository` boundary. The ViewModel depends only on this
 * interface, never on Retrofit/Firebase types directly, so it is testable with a fake (see
 * data/repository/FakePricingRepository.kt and the PricingViewModel unit tests).
 */
interface IPricingRepository {
    suspend fun calculateOptimalRate(query: PricingQueryDTO): PricingOutcome<PredictionResultDTO>

    suspend fun fetchMyProfile(): PricingOutcome<SelfProfileDTO?> = PricingOutcome.Success(null)

    suspend fun upsertMyProfile(payload: SelfProfileUpsertDTO): PricingOutcome<SelfProfileDTO> =
        PricingOutcome.Failure(PricingFailure.Unknown("Profile updates are not supported."))

    suspend fun fetchMetadata(): PricingOutcome<MetadataResponseDTO> =
        PricingOutcome.Failure(PricingFailure.Unknown("Metadata lookup is not supported."))

    suspend fun fetchMyHistory(): PricingOutcome<List<QuoteHistoryItemDTO>> = PricingOutcome.Success(emptyList())

    suspend fun fetchMyListings(): PricingOutcome<List<SelfListingDTO>> = PricingOutcome.Success(emptyList())

    suspend fun upsertMyListing(
        listingId: String,
        payload: SelfListingUpsertDTO,
    ): PricingOutcome<SelfListingDTO> = PricingOutcome.Failure(PricingFailure.Unknown("Listing updates are not supported."))

    suspend fun submitQuoteFeedback(
        transactionId: String,
        payload: QuoteFeedbackRequestDTO,
    ): PricingOutcome<QuoteFeedbackDTO> = PricingOutcome.Failure(PricingFailure.Unknown("Feedback submission is not supported."))
}
