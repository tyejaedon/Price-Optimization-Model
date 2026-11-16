package dev.tyejaedon.pricing.admin.data.network.dto

import com.google.gson.annotations.SerializedName

data class HealthStatusDTO(
    @SerializedName("status") val status: String,
    @SerializedName("service") val service: String,
    @SerializedName("unit") val unit: String,
    @SerializedName("modelsLoaded") val modelsLoaded: Boolean,
    @SerializedName("version") val version: String,
)

data class GridSearchConfigDTO(
    @SerializedName("k_neighbors") val kNeighbors: List<Int> = listOf(1, 3, 5, 7, 10),
    @SerializedName("text_weight") val textWeight: Float = 1.0f,
    @SerializedName("metadata_weight") val metadataWeight: Float = 1.0f,
    @SerializedName("idw_epsilon") val idwEpsilon: Float = 1e-9f,
    @SerializedName("minimum_partition_size") val minimumPartitionSize: Int = 1,
    @SerializedName("allow_fallback") val allowFallback: Boolean = true,
)

data class MetricsResponseDTO(
    @SerializedName("generated_at") val generatedAt: String,
    @SerializedName("metrics") val metrics: Map<String, Any>,
    @SerializedName("tuning") val tuning: GridSearchConfigDTO,
)

data class RetrainResponseDTO(
    @SerializedName("job_id") val jobId: String,
    @SerializedName("status") val status: String,
    @SerializedName("artifact_version") val artifactVersion: String? = null,
    @SerializedName("error") val error: String? = null,
)

data class DriftSummaryDTO(
    @SerializedName("totalTransactions") val totalTransactions: Int,
    @SerializedName("byIndustry") val byIndustry: Map<String, Int>,
    @SerializedName("byCorridor") val byCorridor: Map<String, Int>,
    @SerializedName("averageFinalRate") val averageFinalRate: Float? = null,
)

data class ArtifactStatusDTO(
    @SerializedName("modelsLoaded") val modelsLoaded: Boolean,
    @SerializedName("artifactVersion") val artifactVersion: String? = null,
    @SerializedName("datasetVersion") val datasetVersion: String? = null,
    @SerializedName("sourceType") val sourceType: String? = null,
    @SerializedName("validationStatus") val validationStatus: String? = null,
    @SerializedName("loadError") val loadError: String? = null,
)

data class AdminProfileDTO(
    @SerializedName("profile_id") val profileId: String,
    @SerializedName("full_name") val fullName: String,
    @SerializedName("email") val email: String,
    @SerializedName("country_code") val countryCode: String,
    @SerializedName("account_status") val accountStatus: String = "active",
)

data class QuoteFeedbackRecordDTO(
    @SerializedName("feedback_id") val feedbackId: String,
    @SerializedName("transaction_id") val transactionId: String,
    @SerializedName("mentor_id") val mentorId: String? = null,
    @SerializedName("outcome") val outcome: String,
    @SerializedName("actual_rate") val actualRate: Float? = null,
    @SerializedName("notes") val notes: String? = null,
    @SerializedName("submitted_at") val submittedAt: String? = null,
)

data class TransactionAuditDTO(
    @SerializedName("transaction_id") val transactionId: String,
    @SerializedName("mentor_id") val mentorId: String? = null,
    @SerializedName("selected_industry") val selectedIndustry: String? = null,
    @SerializedName("mentor_country_code") val mentorCountryCode: String? = null,
    @SerializedName("client_country_code") val clientCountryCode: String? = null,
    @SerializedName("final_quoted_rate") val finalQuotedRate: Float? = null,
    @SerializedName("executed_at") val executedAt: String? = null,
)
