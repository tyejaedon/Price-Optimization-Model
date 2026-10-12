package edu.strathmore.pricing.data.repository

import android.util.Log
import edu.strathmore.pricing.data.auth.AuthSessionException
import edu.strathmore.pricing.data.auth.IAuthTokenProvider
import edu.strathmore.pricing.data.network.PricingApiService
import edu.strathmore.pricing.data.network.dto.PredictionResultDTO
import edu.strathmore.pricing.data.network.dto.PricingQueryDTO
import edu.strathmore.pricing.domain.IPricingRepository
import edu.strathmore.pricing.domain.PricingFailure
import edu.strathmore.pricing.domain.PricingOutcome
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import retrofit2.HttpException
import java.io.IOException

/**
 * Uses the canonical protected API without leaking ID tokens or request/response content into logs.
 * All Retrofit calls run on [ioDispatcher] and cancellations are allowed to propagate.
 */
class PricingRepositoryImpl(
    private val apiService: PricingApiService,
    private val authManager: IAuthTokenProvider,
    private val ioDispatcher: CoroutineDispatcher = Dispatchers.IO,
) : IPricingRepository {
    override suspend fun calculateOptimalRate(query: PricingQueryDTO): PricingOutcome<PredictionResultDTO> =
        withContext(ioDispatcher) {
            try {
                val token = authManager.getActiveBearerToken()
                val result = apiService.requestPriceOptimization("Bearer $token", query)
                PricingOutcome.Success(result)
            } catch (error: HttpException) {
                PricingOutcome.Failure(handleApiError(error))
            } catch (error: IOException) {
                PricingOutcome.Failure(PricingFailure.Network)
            } catch (error: AuthSessionException) {
                PricingOutcome.Failure(PricingFailure.Unauthorized)
            }
        }

    private fun handleApiError(error: HttpException): PricingFailure {
        Log.w(TAG, "Pricing request failed with HTTP ${error.code()}")
        return when (error.code()) {
            401 -> PricingFailure.Unauthorized
            403 -> PricingFailure.Forbidden
            422 -> PricingFailure.Validation(field = "request", detail = "Check your inputs and try again.")
            503 -> PricingFailure.ServiceUnavailable
            else -> PricingFailure.Unknown("Unexpected server error (${error.code()}).")
        }
    }

    private companion object {
        const val TAG = "PricingRepositoryImpl"
    }
}
