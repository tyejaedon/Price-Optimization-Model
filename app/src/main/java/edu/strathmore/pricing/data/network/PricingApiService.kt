package edu.strathmore.pricing.data.network

import edu.strathmore.pricing.data.network.dto.HealthStatusDTO
import edu.strathmore.pricing.data.network.dto.PredictionResultDTO
import edu.strathmore.pricing.data.network.dto.PricingQueryDTO
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.POST

/**
 * Retrofit boundary matching the class diagram's `PricingApiService` and the canonical protected
 * pricing/health routes.
 */
interface PricingApiService {
    @POST("api/v1/optimize-price")
    suspend fun requestPriceOptimization(
        @Header("Authorization") bearerToken: String,
        @Body payload: PricingQueryDTO,
    ): PredictionResultDTO

    @GET("health")
    suspend fun fetchHealth(): HealthStatusDTO
}
