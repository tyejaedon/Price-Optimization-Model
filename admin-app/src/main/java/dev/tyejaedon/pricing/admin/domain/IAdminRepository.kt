package dev.tyejaedon.pricing.admin.domain

import dev.tyejaedon.pricing.admin.data.network.dto.AdminProfileDTO
import dev.tyejaedon.pricing.admin.data.network.dto.ArtifactStatusDTO
import dev.tyejaedon.pricing.admin.data.network.dto.DriftSummaryDTO
import dev.tyejaedon.pricing.admin.data.network.dto.GridSearchConfigDTO
import dev.tyejaedon.pricing.admin.data.network.dto.HealthStatusDTO
import dev.tyejaedon.pricing.admin.data.network.dto.MetricsResponseDTO
import dev.tyejaedon.pricing.admin.data.network.dto.QuoteFeedbackRecordDTO
import dev.tyejaedon.pricing.admin.data.network.dto.RetrainResponseDTO
import dev.tyejaedon.pricing.admin.data.network.dto.TransactionAuditDTO

interface IAdminRepository {
    fun setAdminToken(token: String)

    fun clearAdminToken()

    suspend fun fetchHealth(): AdminOutcome<HealthStatusDTO>

    suspend fun fetchMetrics(): AdminOutcome<MetricsResponseDTO>

    suspend fun fetchArtifacts(): AdminOutcome<ArtifactStatusDTO>

    suspend fun fetchDrift(): AdminOutcome<DriftSummaryDTO>

    suspend fun updateGridSearch(config: GridSearchConfigDTO): AdminOutcome<GridSearchConfigDTO>

    suspend fun triggerRetrain(): AdminOutcome<RetrainResponseDTO>

    suspend fun fetchRetrainStatus(jobId: String): AdminOutcome<RetrainResponseDTO>

    suspend fun listProfiles(): AdminOutcome<List<AdminProfileDTO>>

    suspend fun deleteProfile(profileId: String): AdminOutcome<Boolean>

    suspend fun seedPlatformMentors(): AdminOutcome<Map<String, Any>>

    suspend fun listHistory(): AdminOutcome<List<TransactionAuditDTO>>

    suspend fun listFeedback(): AdminOutcome<List<QuoteFeedbackRecordDTO>>
}
