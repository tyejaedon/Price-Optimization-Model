package dev.tyejaedon.pricing.admin.data.network

import dev.tyejaedon.pricing.admin.data.network.dto.AdminProfileDTO
import dev.tyejaedon.pricing.admin.data.network.dto.ArtifactStatusDTO
import dev.tyejaedon.pricing.admin.data.network.dto.DriftSummaryDTO
import dev.tyejaedon.pricing.admin.data.network.dto.GridSearchConfigDTO
import dev.tyejaedon.pricing.admin.data.network.dto.HealthStatusDTO
import dev.tyejaedon.pricing.admin.data.network.dto.MetricsResponseDTO
import dev.tyejaedon.pricing.admin.data.network.dto.QuoteFeedbackRecordDTO
import dev.tyejaedon.pricing.admin.data.network.dto.RetrainResponseDTO
import dev.tyejaedon.pricing.admin.data.network.dto.TransactionAuditDTO
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Path
import retrofit2.http.Query

interface AdminApiService {
    @GET("health")
    suspend fun fetchHealth(): HealthStatusDTO

    @GET("api/v1/admin/metrics")
    suspend fun fetchMetrics(
        @Header("X-Admin-Token") adminToken: String,
    ): MetricsResponseDTO

    @GET("api/v1/admin/artifacts")
    suspend fun fetchArtifacts(
        @Header("X-Admin-Token") adminToken: String,
    ): ArtifactStatusDTO

    @GET("api/v1/admin/drift")
    suspend fun fetchDrift(
        @Header("X-Admin-Token") adminToken: String,
        @Query("limit") limit: Int = 500,
    ): DriftSummaryDTO

    @GET("api/v1/admin/grid-search")
    suspend fun fetchGridSearch(
        @Header("X-Admin-Token") adminToken: String,
    ): GridSearchConfigDTO

    @PUT("api/v1/admin/grid-search")
    suspend fun updateGridSearch(
        @Header("X-Admin-Token") adminToken: String,
        @Body config: GridSearchConfigDTO,
    ): GridSearchConfigDTO

    @POST("api/v1/admin/retrain")
    suspend fun triggerRetrain(
        @Header("X-Admin-Token") adminToken: String,
    ): RetrainResponseDTO

    @GET("api/v1/admin/retrain/{job_id}")
    suspend fun fetchRetrainStatus(
        @Header("X-Admin-Token") adminToken: String,
        @Path("job_id") jobId: String,
    ): Map<String, Any>

    @GET("api/v1/admin/profiles")
    suspend fun listProfiles(
        @Header("X-Admin-Token") adminToken: String,
    ): List<AdminProfileDTO>

    @DELETE("api/v1/admin/profiles/{profile_id}")
    suspend fun deleteProfile(
        @Header("X-Admin-Token") adminToken: String,
        @Path("profile_id") profileId: String,
    ): Map<String, Any>

    @POST("api/v1/admin/seed-platform-mentors")
    suspend fun seedPlatformMentors(
        @Header("X-Admin-Token") adminToken: String,
    ): Map<String, Any>

    @GET("api/v1/admin/history")
    suspend fun listHistory(
        @Header("X-Admin-Token") adminToken: String,
        @Query("limit") limit: Int = 100,
    ): List<TransactionAuditDTO>

    @GET("api/v1/admin/feedback")
    suspend fun listFeedback(
        @Header("X-Admin-Token") adminToken: String,
        @Query("limit") limit: Int = 100,
    ): List<QuoteFeedbackRecordDTO>
}
