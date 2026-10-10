package edu.strathmore.pricing.data.network

import edu.strathmore.pricing.data.network.dto.HealthStatusDTO
import edu.strathmore.pricing.data.network.dto.PricingQueryDTO
import edu.strathmore.pricing.data.network.dto.PredictionResultDTO
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.POST

/**
 * Retrofit boundary matching the class diagram's `PricingApiService` (`docs/Architecture/Class/
 * mobile class diagram.svg`). Full OkHttp client construction, timeout tuning and error
 * classification belong to issue #76 (M13.1); this interface defines the stable request shape so
 * [edu.strathmore.pricing.data.repository.PricingRepositoryImpl] has a concrete contract to depend on.
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
