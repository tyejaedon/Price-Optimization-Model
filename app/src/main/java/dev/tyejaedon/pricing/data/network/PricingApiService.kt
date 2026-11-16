package dev.tyejaedon.pricing.data.network

import dev.tyejaedon.pricing.data.network.dto.HealthStatusDTO
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
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Path
import retrofit2.http.Query

/**
 * Retrofit boundary matching the class diagram's `PricingApiService` and the canonical protected
 * pricing/health/profile routes.
 */
interface PricingApiService {
    @POST("api/v1/optimize-price")
    suspend fun requestPriceOptimization(
        @Header("Authorization") bearerToken: String,
        @Body payload: PricingQueryDTO,
    ): PredictionResultDTO

    @GET("api/v1/me")
    suspend fun fetchMyProfile(
        @Header("Authorization") bearerToken: String,
    ): SelfProfileDTO

    @PUT("api/v1/me")
    suspend fun upsertMyProfile(
        @Header("Authorization") bearerToken: String,
        @Body payload: SelfProfileUpsertDTO,
    ): SelfProfileDTO

    @GET("api/v1/me/history")
    suspend fun fetchMyHistory(
        @Header("Authorization") bearerToken: String,
        @Query("limit") limit: Int = 50,
    ): List<QuoteHistoryItemDTO>

    @GET("api/v1/me/listings")
    suspend fun fetchMyListings(
        @Header("Authorization") bearerToken: String,
    ): List<SelfListingDTO>

    @PUT("api/v1/me/listings/{listing_id}")
    suspend fun upsertMyListing(
        @Header("Authorization") bearerToken: String,
        @Path("listing_id") listingId: String,
        @Body payload: SelfListingUpsertDTO,
    ): SelfListingDTO

    @POST("api/v1/quotes/{transaction_id}/feedback")
    suspend fun submitQuoteFeedback(
        @Header("Authorization") bearerToken: String,
        @Path("transaction_id") transactionId: String,
        @Body payload: QuoteFeedbackRequestDTO,
    ): QuoteFeedbackDTO

    @GET("api/v1/metadata")
    suspend fun fetchMetadata(): MetadataResponseDTO

    @GET("health")
    suspend fun fetchHealth(): HealthStatusDTO
}
