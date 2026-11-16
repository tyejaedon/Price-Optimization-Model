package dev.tyejaedon.pricing.admin.data.repository

import android.util.Log
import com.google.gson.JsonParser
import dev.tyejaedon.pricing.admin.data.network.AdminApiService
import dev.tyejaedon.pricing.admin.data.network.dto.AdminProfileDTO
import dev.tyejaedon.pricing.admin.data.network.dto.ArtifactStatusDTO
import dev.tyejaedon.pricing.admin.data.network.dto.DriftSummaryDTO
import dev.tyejaedon.pricing.admin.data.network.dto.GridSearchConfigDTO
import dev.tyejaedon.pricing.admin.data.network.dto.HealthStatusDTO
import dev.tyejaedon.pricing.admin.data.network.dto.MetricsResponseDTO
import dev.tyejaedon.pricing.admin.data.network.dto.QuoteFeedbackRecordDTO
import dev.tyejaedon.pricing.admin.data.network.dto.RetrainResponseDTO
import dev.tyejaedon.pricing.admin.data.network.dto.TransactionAuditDTO
import dev.tyejaedon.pricing.admin.domain.AdminFailure
import dev.tyejaedon.pricing.admin.domain.AdminOutcome
import dev.tyejaedon.pricing.admin.domain.IAdminRepository
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import retrofit2.HttpException
import java.io.IOException

class AdminRepositoryImpl(
    private val apiService: AdminApiService,
    private val ioDispatcher: CoroutineDispatcher = Dispatchers.IO,
) : IAdminRepository {
    @Volatile
    private var adminToken: String = ""

    override fun setAdminToken(token: String) {
        adminToken = token.trim()
    }

    override fun clearAdminToken() {
        adminToken = ""
    }

    override suspend fun fetchHealth(): AdminOutcome<HealthStatusDTO> = safeCall { apiService.fetchHealth() }

    override suspend fun fetchMetrics(): AdminOutcome<MetricsResponseDTO> = safeAdminCall { token -> apiService.fetchMetrics(token) }

    override suspend fun fetchArtifacts(): AdminOutcome<ArtifactStatusDTO> = safeAdminCall { token -> apiService.fetchArtifacts(token) }

    override suspend fun fetchDrift(): AdminOutcome<DriftSummaryDTO> = safeAdminCall { token -> apiService.fetchDrift(token) }

    override suspend fun updateGridSearch(config: GridSearchConfigDTO): AdminOutcome<GridSearchConfigDTO> =
        safeAdminCall { token -> apiService.updateGridSearch(token, config) }

    override suspend fun triggerRetrain(): AdminOutcome<RetrainResponseDTO> = safeAdminCall { token -> apiService.triggerRetrain(token) }

    override suspend fun fetchRetrainStatus(jobId: String): AdminOutcome<RetrainResponseDTO> =
        safeAdminCall { token ->
            val raw = apiService.fetchRetrainStatus(token, jobId)
            RetrainResponseDTO(
                jobId = raw["job_id"]?.toString() ?: jobId,
                status = raw["status"]?.toString() ?: "unknown",
                artifactVersion = raw["artifact_version"]?.toString(),
                error = raw["error"]?.toString(),
            )
        }

    override suspend fun listProfiles(): AdminOutcome<List<AdminProfileDTO>> = safeAdminCall { token -> apiService.listProfiles(token) }

    override suspend fun deleteProfile(profileId: String): AdminOutcome<Boolean> =
        safeAdminCall { token -> apiService.deleteProfile(token, profileId)["deleted"] == true }

    override suspend fun seedPlatformMentors(): AdminOutcome<Map<String, Any>> =
        safeAdminCall { token -> apiService.seedPlatformMentors(token) }

    override suspend fun listHistory(): AdminOutcome<List<TransactionAuditDTO>> = safeAdminCall { token -> apiService.listHistory(token) }

    override suspend fun listFeedback(): AdminOutcome<List<QuoteFeedbackRecordDTO>> =
        safeAdminCall { token -> apiService.listFeedback(token) }

    private suspend fun <T> safeAdminCall(block: suspend (String) -> T): AdminOutcome<T> {
        val token = adminToken
        if (token.isBlank()) return AdminOutcome.Failure(AdminFailure.Forbidden)
        return safeCall { block(token) }
    }

    private suspend fun <T> safeCall(block: suspend () -> T): AdminOutcome<T> =
        withContext(ioDispatcher) {
            try {
                AdminOutcome.Success(block())
            } catch (error: HttpException) {
                AdminOutcome.Failure(handleApiError(error))
            } catch (_: IOException) {
                AdminOutcome.Failure(AdminFailure.Network)
            }
        }

    private fun handleApiError(error: HttpException): AdminFailure {
        Log.w(TAG, "Admin request failed with HTTP ${error.code()}")
        val detail = extractErrorDetail(error)
        return when (error.code()) {
            401, 403 -> AdminFailure.Forbidden
            422 -> AdminFailure.Validation(detail ?: "Validation failed.")
            503 -> AdminFailure.ServiceUnavailable
            else -> AdminFailure.Unknown(detail ?: "Unexpected server error (${error.code()}).")
        }
    }

    private fun extractErrorDetail(error: HttpException): String? {
        val rawBody =
            try {
                error.response()?.errorBody()?.string()
            } catch (_: IOException) {
                null
            } ?: return null
        if (rawBody.isBlank()) return null
        return try {
            val root = JsonParser.parseString(rawBody)
            if (!root.isJsonObject) return null
            val detail = root.asJsonObject.get("detail") ?: return null
            if (detail.isJsonPrimitive && detail.asJsonPrimitive.isString) {
                detail.asString.takeIf { it.isNotBlank() }
            } else {
                null
            }
        } catch (_: Exception) {
            null
        }
    }

    private companion object {
        const val TAG = "AdminRepositoryImpl"
    }
}
