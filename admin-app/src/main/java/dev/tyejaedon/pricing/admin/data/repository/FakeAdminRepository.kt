package dev.tyejaedon.pricing.admin.data.repository

import dev.tyejaedon.pricing.admin.data.network.dto.AdminProfileDTO
import dev.tyejaedon.pricing.admin.data.network.dto.ArtifactStatusDTO
import dev.tyejaedon.pricing.admin.data.network.dto.DriftSummaryDTO
import dev.tyejaedon.pricing.admin.data.network.dto.GridSearchConfigDTO
import dev.tyejaedon.pricing.admin.data.network.dto.HealthStatusDTO
import dev.tyejaedon.pricing.admin.data.network.dto.MetricsResponseDTO
import dev.tyejaedon.pricing.admin.data.network.dto.QuoteFeedbackRecordDTO
import dev.tyejaedon.pricing.admin.data.network.dto.RetrainResponseDTO
import dev.tyejaedon.pricing.admin.data.network.dto.TransactionAuditDTO
import dev.tyejaedon.pricing.admin.domain.AdminOutcome
import dev.tyejaedon.pricing.admin.domain.IAdminRepository
import kotlinx.coroutines.delay

class FakeAdminRepository(
    private val simulatedLatencyMs: Long = 100L,
) : IAdminRepository {
    private var currentTuning = GridSearchConfigDTO()
    private val profiles =
        mutableListOf(
            AdminProfileDTO("mentor-001", "Alice Mentor", "alice@example.test", "KE", "active"),
            AdminProfileDTO("mentor-002", "Bob Mentor", "bob@example.test", "UG", "active"),
        )

    override fun setAdminToken(token: String) = Unit

    override fun clearAdminToken() = Unit

    override suspend fun fetchHealth(): AdminOutcome<HealthStatusDTO> {
        delay(simulatedLatencyMs)
        return AdminOutcome.Success(
            HealthStatusDTO(
                status = "HEALTHY",
                service = "pricing-engine",
                unit = "KES/hour",
                modelsLoaded = true,
                version = "1.0.0",
            ),
        )
    }

    override suspend fun fetchMetrics(): AdminOutcome<MetricsResponseDTO> {
        delay(simulatedLatencyMs)
        return AdminOutcome.Success(
            MetricsResponseDTO(
                generatedAt = "2026-11-16T10:00:00Z",
                metrics = mapOf("inference.optimize_price.count" to 42),
                tuning = currentTuning,
            ),
        )
    }

    override suspend fun fetchArtifacts(): AdminOutcome<ArtifactStatusDTO> {
        delay(simulatedLatencyMs)
        return AdminOutcome.Success(
            ArtifactStatusDTO(
                modelsLoaded = true,
                artifactVersion = "v1:ab12cd34ef56",
                datasetVersion = "platform-v2",
                sourceType = "platform",
                validationStatus = "passed",
            ),
        )
    }

    override suspend fun fetchDrift(): AdminOutcome<DriftSummaryDTO> {
        delay(simulatedLatencyMs)
        return AdminOutcome.Success(
            DriftSummaryDTO(
                totalTransactions = 42,
                byIndustry = mapOf("mobile" to 18, "web_backend" to 14, "data_ai" to 10),
                byCorridor = mapOf("KE->US" to 24, "KE->KE" to 18),
                averageFinalRate = 2640.5f,
            ),
        )
    }

    override suspend fun updateGridSearch(config: GridSearchConfigDTO): AdminOutcome<GridSearchConfigDTO> {
        delay(simulatedLatencyMs)
        currentTuning = config
        return AdminOutcome.Success(config)
    }

    override suspend fun triggerRetrain(): AdminOutcome<RetrainResponseDTO> {
        delay(simulatedLatencyMs)
        return AdminOutcome.Success(
            RetrainResponseDTO(jobId = "retrain-demo-01", status = "accepted"),
        )
    }

    override suspend fun fetchRetrainStatus(jobId: String): AdminOutcome<RetrainResponseDTO> {
        delay(simulatedLatencyMs)
        return AdminOutcome.Success(
            RetrainResponseDTO(jobId = jobId, status = "succeeded", artifactVersion = "v1:demo999"),
        )
    }

    override suspend fun listProfiles(): AdminOutcome<List<AdminProfileDTO>> {
        delay(simulatedLatencyMs)
        return AdminOutcome.Success(profiles.toList())
    }

    override suspend fun deleteProfile(profileId: String): AdminOutcome<Boolean> {
        delay(simulatedLatencyMs)
        return AdminOutcome.Success(profiles.removeAll { it.profileId == profileId })
    }

    override suspend fun seedPlatformMentors(): AdminOutcome<Map<String, Any>> {
        delay(simulatedLatencyMs)
        return AdminOutcome.Success(mapOf("seeded" to 12))
    }

    override suspend fun listHistory(): AdminOutcome<List<TransactionAuditDTO>> {
        delay(simulatedLatencyMs)
        return AdminOutcome.Success(
            listOf(
                TransactionAuditDTO(
                    transactionId = "api-demo-1",
                    mentorId = "mentor-001",
                    selectedIndustry = "mobile",
                    mentorCountryCode = "KE",
                    clientCountryCode = "US",
                    finalQuotedRate = 2557f,
                    executedAt = "2026-11-16T09:30:00Z",
                ),
            ),
        )
    }

    override suspend fun listFeedback(): AdminOutcome<List<QuoteFeedbackRecordDTO>> {
        delay(simulatedLatencyMs)
        return AdminOutcome.Success(
            listOf(
                QuoteFeedbackRecordDTO(
                    feedbackId = "fb-demo-1",
                    transactionId = "api-demo-1",
                    mentorId = "mentor-001",
                    outcome = "booked",
                    actualRate = 2600f,
                    notes = "Client accepted quoted corridor",
                    submittedAt = "2026-11-16T09:45:00Z",
                ),
            ),
        )
    }
}
