package edu.strathmore.pricing.data.repository

import android.util.Log
import edu.strathmore.pricing.data.auth.IAuthTokenProvider
import edu.strathmore.pricing.data.network.PricingApiService
import edu.strathmore.pricing.data.network.dto.PricingQueryDTO
import edu.strathmore.pricing.data.network.dto.PredictionResultDTO
import edu.strathmore.pricing.domain.IPricingRepository
import edu.strathmore.pricing.domain.PricingFailure
import edu.strathmore.pricing.domain.PricingOutcome
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import retrofit2.HttpException
import java.io.IOException

/**
 * Matches the class diagram's `PricingRepositoryImpl`. Networking is dispatched on [ioDispatcher]
 * (never the main thread), per docs/architecture_blueprint (1).md section 7's coroutines rule.
 *
 * Full timeout tuning, request/response interceptor logging redaction and the broader HTTP error
 * taxonomy are owned by issue #76 (M13.1); this class defines the stable success/failure mapping
 * other layers (ViewModel, UI) are already built against.
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
            } catch (error: IllegalStateException) {
                // Thrown by IAuthTokenProvider when there is no signed-in user / refresh fails.
                PricingOutcome.Failure(PricingFailure.Unauthorized)
            }
        }

    private fun handleApiError(error: HttpException): PricingFailure {
        // Never log the raw request/response body: it may contain mentor description text.
        Log.w(TAG, "Pricing request failed with HTTP ${error.code()}")
        return when (error.code()) {
            401, 403 -> PricingFailure.Unauthorized
            422 -> PricingFailure.Validation(field = "request", detail = "Check your inputs and try again.")
            503 -> PricingFailure.ServiceUnavailable
            else -> PricingFailure.Unknown("Unexpected server error (${error.code()}).")
        }
    }

    private companion object {
        const val TAG = "PricingRepositoryImpl"
    }
}
