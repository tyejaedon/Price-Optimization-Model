package dev.tyejaedon.pricing.data.network.dto

import com.google.gson.annotations.SerializedName

/**
 * Wire DTOs mirroring `src/api_contracts.py`'s canonical camelCase models (`CanonicalPricingQueryDTO`,
 * `CanonicalPeerMatchDTO`, `CanonicalPredictionResultDTO`, `HealthStatusDTO`). Field names and
 * constraints MUST stay in lockstep with the Python source of truth; update both in the same PR.
 * KES/hour is the only supported currency/unit for all rate fields (docs/architecture_blueprint (1).md).
 */
data class PricingQueryDTO(
    @SerializedName("mentorId") val mentorId: String,
    @SerializedName("listingId") val listingId: String? = null,
    @SerializedName("rawText") val rawText: String,
    @SerializedName("industry") val industry: String,
    @SerializedName("mentorCountry") val mentorCountry: String,
    @SerializedName("clientCountry") val clientCountry: String,
    @SerializedName("competitivenessScore") val competitivenessScore: Float = 0.5f,
    @SerializedName("costOfLivingIndex") val costOfLivingIndex: Float? = null,
    @SerializedName("baseRateFloor") val baseRateFloor: Float? = null,
)

data class PeerMatchDTO(
    @SerializedName("listingId") val listingId: String,
    @SerializedName("jobTitle") val jobTitle: String?,
    @SerializedName("verifiedRate") val verifiedRate: Float,
    @SerializedName("similarityScore") val similarityScore: Float,
    @SerializedName("euclideanDistance") val euclideanDistance: Float,
    @SerializedName("idwWeight") val idwWeight: Float? = null,
    @SerializedName("publishedDate") val publishedDate: String? = null,
    @SerializedName("experienceLevel") val experienceLevel: String? = null,
    @SerializedName("countryCode") val countryCode: String? = null,
    @SerializedName("industryLabel") val industryLabel: String? = null,
)

data class QuoteExplanationDTO(
    @SerializedName("requestedPartition") val requestedPartition: String? = null,
    @SerializedName("routedPartition") val routedPartition: String? = null,
    @SerializedName("usedFallbackPartition") val usedFallbackPartition: Boolean = false,
    @SerializedName("peerRateStddev") val peerRateStddev: Float? = null,
    @SerializedName("baseRateFloorRequested") val baseRateFloorRequested: Float? = null,
    @SerializedName("floorBoundActive") val floorBoundActive: Boolean = false,
    @SerializedName("floorExceedsBase") val floorExceedsBase: Boolean = false,
    @SerializedName("feePushesAboveCeiling") val feePushesAboveCeiling: Boolean = false,
    @SerializedName("corridorUpliftMultiplier") val corridorUpliftMultiplier: Float = 1f,
    @SerializedName("topMatchedTerms") val topMatchedTerms: List<String> = emptyList(),
)

data class PredictionResultDTO(
    @SerializedName("basePredictedRate") val basePredictedRate: Float,
    @SerializedName("mpesaTariffSurcharge") val mpesaTariffSurcharge: Float,
    @SerializedName("finalQuotedRate") val finalQuotedRate: Float,
    @SerializedName("minQuotedRate") val minQuotedRate: Float,
    @SerializedName("maxQuotedRate") val maxQuotedRate: Float,
    @SerializedName("kNeighborsUsed") val kNeighborsUsed: Int,
    @SerializedName("bilateralArbitrageFactor") val bilateralArbitrageFactor: Float,
    // Explicitly uncalibrated per the backend contract; render as a disclosed caveat, not an
    // accuracy probability (see issue #142).
    @SerializedName("confidenceScore") val confidenceScore: Float,
    @SerializedName("comparables") val comparables: List<PeerMatchDTO>,
    @SerializedName("reason") val reason: String,
    @SerializedName("explanation") val explanation: QuoteExplanationDTO? = null,
    @SerializedName("timestamp") val timestamp: String,
)

data class HealthStatusDTO(
    @SerializedName("status") val status: String,
    @SerializedName("service") val service: String,
    @SerializedName("unit") val unit: String,
    @SerializedName("modelsLoaded") val modelsLoaded: Boolean,
    @SerializedName("version") val version: String,
)

data class SelfProfileDTO(
    @SerializedName("profileId") val profileId: String,
    @SerializedName("fullName") val fullName: String,
    @SerializedName("email") val email: String,
    @SerializedName("countryCode") val countryCode: String,
    @SerializedName("accountStatus") val accountStatus: String = "active",
    @SerializedName("rawText") val rawText: String? = null,
)

data class SelfProfileUpsertDTO(
    @SerializedName("fullName") val fullName: String,
    @SerializedName("email") val email: String,
    @SerializedName("countryCode") val countryCode: String,
    @SerializedName("rawText") val rawText: String? = null,
)

data class MetadataResponseDTO(
    @SerializedName("industries") val industries: List<String>,
    @SerializedName("unit") val unit: String = "KES/hour",
    @SerializedName("version") val version: String = "1.0.0",
    @SerializedName("modelsLoaded") val modelsLoaded: Boolean = true,
)

data class SelfListingUpsertDTO(
    @SerializedName("title") val title: String,
    @SerializedName("industryId") val industryId: String,
    @SerializedName("rawText") val rawText: String,
    @SerializedName("verifiedRate") val verifiedRate: Float = 1.0f,
    @SerializedName("isActive") val isActive: Boolean = true,
    @SerializedName("marketCompetitiveness") val marketCompetitiveness: Float? = null,
    @SerializedName("baseRateFloor") val baseRateFloor: Float? = null,
)

data class SelfListingDTO(
    @SerializedName("listingId") val listingId: String,
    @SerializedName("mentorId") val mentorId: String,
    @SerializedName("industryId") val industryId: String,
    @SerializedName("title") val title: String,
    @SerializedName("rawText") val rawText: String,
    @SerializedName("verifiedRate") val verifiedRate: Float,
    @SerializedName("isActive") val isActive: Boolean = true,
    @SerializedName("marketCompetitiveness") val marketCompetitiveness: Float? = null,
    @SerializedName("baseRateFloor") val baseRateFloor: Float? = null,
)

data class QuoteHistoryItemDTO(
    @SerializedName("transaction_id") val transactionId: String,
    @SerializedName("selected_industry") val selectedIndustry: String? = null,
    @SerializedName("mentor_country_code") val mentorCountryCode: String? = null,
    @SerializedName("client_country_code") val clientCountryCode: String? = null,
    @SerializedName("base_predicted_rate") val basePredictedRate: Float? = null,
    @SerializedName("mpesa_tariff_surcharge") val mpesaTariffSurcharge: Float? = null,
    @SerializedName("final_quoted_rate") val finalQuotedRate: Float? = null,
    @SerializedName("executed_at") val executedAt: String? = null,
    @SerializedName("listing_id") val listingId: String? = null,
)

data class QuoteFeedbackRequestDTO(
    @SerializedName("outcome") val outcome: String,
    @SerializedName("actualRate") val actualRate: Float? = null,
    @SerializedName("notes") val notes: String? = null,
)

data class QuoteFeedbackDTO(
    @SerializedName("feedbackId") val feedbackId: String,
    @SerializedName("transactionId") val transactionId: String,
    @SerializedName("mentorId") val mentorId: String? = null,
    @SerializedName("outcome") val outcome: String,
    @SerializedName("actualRate") val actualRate: Float? = null,
    @SerializedName("notes") val notes: String? = null,
    @SerializedName("submittedAt") val submittedAt: String,
)
