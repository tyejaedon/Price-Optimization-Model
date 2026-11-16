package dev.tyejaedon.pricing.data.repository

import android.util.Log
import com.google.gson.JsonParser
import dev.tyejaedon.pricing.data.auth.AuthSessionException
import dev.tyejaedon.pricing.data.auth.IAuthTokenProvider
import dev.tyejaedon.pricing.data.network.PricingApiService
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
import dev.tyejaedon.pricing.domain.IPricingRepository
import dev.tyejaedon.pricing.domain.PricingFailure
import dev.tyejaedon.pricing.domain.PricingOutcome
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

    override suspend fun fetchMyProfile(): PricingOutcome<SelfProfileDTO?> =
        withContext(ioDispatcher) {
            try {
                val token = authManager.getActiveBearerToken()
                PricingOutcome.Success(apiService.fetchMyProfile("Bearer $token"))
            } catch (error: HttpException) {
                if (error.code() == 404) {
                    PricingOutcome.Success(null)
                } else {
                    PricingOutcome.Failure(handleApiError(error))
                }
            } catch (_: IOException) {
                PricingOutcome.Failure(PricingFailure.Network)
            } catch (_: AuthSessionException) {
                PricingOutcome.Failure(PricingFailure.Unauthorized)
            }
        }

    override suspend fun upsertMyProfile(payload: SelfProfileUpsertDTO): PricingOutcome<SelfProfileDTO> =
        safeAuthCall { token -> apiService.upsertMyProfile("Bearer $token", payload) }

    override suspend fun fetchMetadata(): PricingOutcome<MetadataResponseDTO> =
        withContext(ioDispatcher) {
            try {
                PricingOutcome.Success(apiService.fetchMetadata())
            } catch (error: HttpException) {
                PricingOutcome.Failure(handleApiError(error))
            } catch (_: IOException) {
                PricingOutcome.Failure(PricingFailure.Network)
            }
        }

    override suspend fun fetchMyHistory(): PricingOutcome<List<QuoteHistoryItemDTO>> =
        safeAuthCall { token -> apiService.fetchMyHistory("Bearer $token") }

    override suspend fun fetchMyListings(): PricingOutcome<List<SelfListingDTO>> =
        safeAuthCall { token -> apiService.fetchMyListings("Bearer $token") }

    override suspend fun upsertMyListing(
        listingId: String,
        payload: SelfListingUpsertDTO,
    ): PricingOutcome<SelfListingDTO> = safeAuthCall { token -> apiService.upsertMyListing("Bearer $token", listingId, payload) }

    override suspend fun submitQuoteFeedback(
        transactionId: String,
        payload: QuoteFeedbackRequestDTO,
    ): PricingOutcome<QuoteFeedbackDTO> = safeAuthCall { token -> apiService.submitQuoteFeedback("Bearer $token", transactionId, payload) }

    private suspend fun <T> safeAuthCall(block: suspend (String) -> T): PricingOutcome<T> =
        withContext(ioDispatcher) {
            try {
                val token = authManager.getActiveBearerToken()
                PricingOutcome.Success(block(token))
            } catch (error: HttpException) {
                PricingOutcome.Failure(handleApiError(error))
            } catch (_: IOException) {
                PricingOutcome.Failure(PricingFailure.Network)
            } catch (_: AuthSessionException) {
                PricingOutcome.Failure(PricingFailure.Unauthorized)
            }
        }

    private fun handleApiError(error: HttpException): PricingFailure {
        Log.w(TAG, "Pricing request failed with HTTP ${error.code()}")
        val serverDetail = extractErrorDetail(error)
        return when (error.code()) {
            401 -> PricingFailure.Unauthorized
            403 -> PricingFailure.Forbidden
            422 ->
                PricingFailure.Validation(
                    field = "request",
                    detail = serverDetail ?: "Check your inputs and try again.",
                )
            503 -> PricingFailure.ServiceUnavailable
            else -> PricingFailure.Unknown("Unexpected server error (${error.code()}).")
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
            when {
                detail.isJsonPrimitive && detail.asJsonPrimitive.isString ->
                    detail.asString.takeIf { it.isNotBlank() }
                detail.isJsonArray && detail.asJsonArray.size() > 0 -> {
                    val first = detail.asJsonArray[0]
                    if (first.isJsonObject) {
                        first.asJsonObject
                            .get("msg")
                            ?.takeIf { it.isJsonPrimitive }
                            ?.asString
                            ?.takeIf { it.isNotBlank() }
                    } else {
                        null
                    }
                }
                else -> null
            }
        } catch (_: Exception) {
            null
        }
    }

    private companion object {
        const val TAG = "PricingRepositoryImpl"
    }
}
