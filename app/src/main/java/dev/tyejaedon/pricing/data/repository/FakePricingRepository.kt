package dev.tyejaedon.pricing.data.repository

import dev.tyejaedon.pricing.data.network.dto.MetadataResponseDTO
import dev.tyejaedon.pricing.data.network.dto.PeerMatchDTO
import dev.tyejaedon.pricing.data.network.dto.PredictionResultDTO
import dev.tyejaedon.pricing.data.network.dto.PricingQueryDTO
import dev.tyejaedon.pricing.data.network.dto.QuoteFeedbackDTO
import dev.tyejaedon.pricing.data.network.dto.QuoteFeedbackRequestDTO
import dev.tyejaedon.pricing.data.network.dto.QuoteHistoryItemDTO
import dev.tyejaedon.pricing.data.network.dto.SelfListingDTO
import dev.tyejaedon.pricing.data.network.dto.SelfListingUpsertDTO
import dev.tyejaedon.pricing.data.network.dto.SelfProfileDTO
import dev.tyejaedon.pricing.data.network.dto.SelfProfileUpsertDTO
import dev.tyejaedon.pricing.domain.IPricingRepository
import dev.tyejaedon.pricing.domain.PricingFailure
import dev.tyejaedon.pricing.domain.PricingOutcome
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

    override suspend fun fetchMyProfile(): PricingOutcome<SelfProfileDTO?> =
        PricingOutcome.Success(
            SelfProfileDTO(
                profileId = "demo-mentor",
                fullName = "Demo Mentor",
                email = "demo@example.test",
                countryCode = "KE",
            ),
        )

    private val demoListings =
        mutableListOf(
            SelfListingDTO(
                listingId = "demo-listing-1",
                mentorId = "demo-mentor",
                industryId = "mobile",
                title = "Android & Kotlin Architecture Mentoring",
                rawText = "Senior Android engineer mentoring Kotlin and Jetpack Compose teams.",
                verifiedRate = 2500f,
                isActive = true,
                marketCompetitiveness = 0.5f,
            ),
        )

    private val demoHistory =
        mutableListOf(
            QuoteHistoryItemDTO(
                transactionId = "demo-tx-1",
                selectedIndustry = "mobile",
                mentorCountryCode = "KE",
                clientCountryCode = "US",
                basePredictedRate = 2500f,
                mpesaTariffSurcharge = 57f,
                finalQuotedRate = 2557f,
                executedAt = "2026-11-16T09:00:00Z",
                listingId = "demo-listing-1",
            ),
        )

    override suspend fun upsertMyProfile(payload: SelfProfileUpsertDTO): PricingOutcome<SelfProfileDTO> =
        PricingOutcome.Success(
            SelfProfileDTO(
                profileId = "demo-mentor",
                fullName = payload.fullName,
                email = payload.email,
                countryCode = payload.countryCode,
                rawText = payload.rawText,
            ),
        )

    override suspend fun fetchMetadata(): PricingOutcome<MetadataResponseDTO> =
        PricingOutcome.Success(
            MetadataResponseDTO(
                industries =
                    listOf(
                        "data_ai",
                        "web_backend",
                        "mobile",
                        "devops_cloud",
                        "design_creative",
                        "product_management",
                        "digital_marketing",
                        "general_tech",
                    ),
                modelsLoaded = true,
            ),
        )

    override suspend fun fetchMyHistory(): PricingOutcome<List<QuoteHistoryItemDTO>> = PricingOutcome.Success(demoHistory.toList())

    override suspend fun fetchMyListings(): PricingOutcome<List<SelfListingDTO>> = PricingOutcome.Success(demoListings.toList())

    override suspend fun upsertMyListing(
        listingId: String,
        payload: SelfListingUpsertDTO,
    ): PricingOutcome<SelfListingDTO> {
        val item =
            SelfListingDTO(
                listingId = listingId,
                mentorId = "demo-mentor",
                industryId = payload.industryId,
                title = payload.title,
                rawText = payload.rawText,
                verifiedRate = payload.verifiedRate,
                isActive = payload.isActive,
                marketCompetitiveness = payload.marketCompetitiveness,
                baseRateFloor = payload.baseRateFloor,
            )
        demoListings.removeAll { it.listingId == listingId }
        demoListings.add(item)
        return PricingOutcome.Success(item)
    }

    override suspend fun submitQuoteFeedback(
        transactionId: String,
        payload: QuoteFeedbackRequestDTO,
    ): PricingOutcome<QuoteFeedbackDTO> =
        PricingOutcome.Success(
            QuoteFeedbackDTO(
                feedbackId = "fb-demo-1",
                transactionId = transactionId,
                mentorId = "demo-mentor",
                outcome = payload.outcome,
                actualRate = payload.actualRate,
                notes = payload.notes,
                submittedAt = "2026-11-16T10:00:00Z",
            ),
        )

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
                    comparables =
                        listOf(
                            PeerMatchDTO("list_001", "Senior Android Architect", 2600f, 0.92f, 0.41f),
                            PeerMatchDTO("list_045", "Kotlin Mentor", 2400f, 0.88f, 0.55f),
                        ),
                    reason = "Weighted from 5 indexed peers in KES/hour; corridor excludes the M-Pesa surcharge.",
                    timestamp = "2026-10-10T00:00:00Z",
                ),
            )
        }

        fun failure(failure: PricingFailure): (PricingQueryDTO) -> PricingOutcome<PredictionResultDTO> = { PricingOutcome.Failure(failure) }
    }
}
