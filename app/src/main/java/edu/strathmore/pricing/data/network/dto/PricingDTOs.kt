package edu.strathmore.pricing.data.network.dto

import com.google.gson.annotations.SerializedName

/**
 * Wire DTOs mirroring `src/api_contracts.py`'s canonical camelCase models (`CanonicalPricingQueryDTO`,
 * `CanonicalPeerMatchDTO`, `CanonicalPredictionResultDTO`, `HealthStatusDTO`). Field names and
 * constraints MUST stay in lockstep with the Python source of truth; update both in the same PR.
 * KES/hour is the only supported currency/unit for all rate fields (docs/architecture_blueprint (1).md).
 */
data class PricingQueryDTO(
    @SerializedName("mentorId") val mentorId: String,
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
    @SerializedName("timestamp") val timestamp: String,
)

data class HealthStatusDTO(
    @SerializedName("status") val status: String,
    @SerializedName("service") val service: String,
    @SerializedName("unit") val unit: String,
    @SerializedName("modelsLoaded") val modelsLoaded: Boolean,
    @SerializedName("version") val version: String,
)

