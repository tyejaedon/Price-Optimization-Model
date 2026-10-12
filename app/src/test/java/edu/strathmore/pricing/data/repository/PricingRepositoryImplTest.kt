package edu.strathmore.pricing.data.repository

import com.google.common.truth.Truth.assertThat
import edu.strathmore.pricing.data.auth.AuthSessionException
import edu.strathmore.pricing.data.auth.IAuthTokenProvider
import edu.strathmore.pricing.data.network.PricingApiService
import edu.strathmore.pricing.data.network.dto.PricingQueryDTO
import edu.strathmore.pricing.domain.PricingFailure
import edu.strathmore.pricing.domain.PricingOutcome
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.test.runTest
import okhttp3.OkHttpClient
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Before
import org.junit.Test
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

class PricingRepositoryImplTest {
    private val server = MockWebServer()
    private val tokenProvider = FakeTokenProvider()
    private lateinit var repository: PricingRepositoryImpl

    @Before
    fun setUp() {
        server.start()
        repository = createRepository()
    }

    @After
    fun tearDown() {
        server.shutdown()
    }

    @Test
    fun `success sends canonical payload and refreshed bearer token`() =
        runTest {
            server.enqueue(MockResponse().setBody(SUCCESS_RESPONSE))

            val outcome = repository.calculateOptimalRate(query)

            assertThat(outcome).isInstanceOf(PricingOutcome.Success::class.java)
            assertThat((outcome as PricingOutcome.Success).value.finalQuotedRate).isEqualTo(4757f)
            val request = server.takeRequest()
            assertThat(request.path).isEqualTo("/api/v1/optimize-price")
            assertThat(request.getHeader("Authorization")).isEqualTo("Bearer refreshed-token-1")
            val requestBody = request.body.readUtf8()
            assertThat(requestBody).contains("\"mentorId\":\"mentor-profile-123\"")
            assertThat(requestBody).contains("\"baseRateFloor\":4000.0")
            assertThat(tokenProvider.refreshCount).isEqualTo(1)
        }

    @Test
    fun `each quote obtains a newly refreshed token`() =
        runTest {
            server.enqueue(MockResponse().setBody(SUCCESS_RESPONSE))
            server.enqueue(MockResponse().setBody(SUCCESS_RESPONSE))

            repository.calculateOptimalRate(query)
            repository.calculateOptimalRate(query)

            assertThat(server.takeRequest().getHeader("Authorization")).isEqualTo("Bearer refreshed-token-1")
            assertThat(server.takeRequest().getHeader("Authorization")).isEqualTo("Bearer refreshed-token-2")
            assertThat(tokenProvider.refreshCount).isEqualTo(2)
        }

    @Test
    fun `401 requires sign in and 403 reports mentor ownership mismatch`() =
        runTest {
            server.enqueue(MockResponse().setResponseCode(401))
            assertFailure(repository.calculateOptimalRate(query), PricingFailure.Unauthorized)

            server.enqueue(MockResponse().setResponseCode(403))
            assertFailure(repository.calculateOptimalRate(query), PricingFailure.Forbidden)
        }

    @Test
    fun `422 returns actionable request validation failure`() =
        runTest {
            server.enqueue(MockResponse().setResponseCode(422))

            val outcome = repository.calculateOptimalRate(query)

            assertThat((outcome as PricingOutcome.Failure).error)
                .isInstanceOf(PricingFailure.Validation::class.java)
        }

    @Test
    fun `503 returns service unavailable failure`() =
        runTest {
            server.enqueue(MockResponse().setResponseCode(503))

            val outcome = repository.calculateOptimalRate(query)

            assertFailure(outcome, PricingFailure.ServiceUnavailable)
        }

    @Test
    fun `unexpected server response is not reported as success`() =
        runTest {
            server.enqueue(MockResponse().setResponseCode(500))

            val outcome = repository.calculateOptimalRate(query)

            assertThat((outcome as PricingOutcome.Failure).error)
                .isInstanceOf(PricingFailure.Unknown::class.java)
        }

    @Test
    fun `timeout maps to a network failure`() =
        runTest {
            repository = createRepository(readTimeoutMs = 100)
            server.enqueue(
                MockResponse()
                    .setBodyDelay(500, TimeUnit.MILLISECONDS)
                    .setBody(SUCCESS_RESPONSE),
            )

            val outcome = repository.calculateOptimalRate(query)

            assertFailure(outcome, PricingFailure.Network)
        }

    @Test
    fun `cancelling an in-flight request propagates cancellation`() =
        runTest {
            server.enqueue(
                MockResponse()
                    .setBodyDelay(2, TimeUnit.SECONDS)
                    .setBody(SUCCESS_RESPONSE),
            )
            val request = async(Dispatchers.IO) { repository.calculateOptimalRate(query) }
            assertThat(server.takeRequest(1, TimeUnit.SECONDS)).isNotNull()

            request.cancelAndJoin()

            assertThat(request.isCancelled).isTrue()
        }

    @Test
    fun `token refresh failure is unauthorized and sends no request`() =
        runTest {
            tokenProvider.failure = AuthSessionException("Sign in again.")

            val outcome = repository.calculateOptimalRate(query)

            assertFailure(outcome, PricingFailure.Unauthorized)
            assertThat(server.requestCount).isEqualTo(0)
        }

    private fun createRepository(readTimeoutMs: Long = 1000): PricingRepositoryImpl {
        val client =
            OkHttpClient
                .Builder()
                .connectTimeout(1, TimeUnit.SECONDS)
                .readTimeout(readTimeoutMs, TimeUnit.MILLISECONDS)
                .build()
        val api =
            Retrofit
                .Builder()
                .baseUrl(server.url("/"))
                .client(client)
                .addConverterFactory(GsonConverterFactory.create())
                .build()
                .create(PricingApiService::class.java)
        return PricingRepositoryImpl(api, tokenProvider, Dispatchers.IO)
    }

    private fun assertFailure(
        outcome: PricingOutcome<*>,
        expected: PricingFailure,
    ) {
        assertThat(outcome).isInstanceOf(PricingOutcome.Failure::class.java)
        assertThat((outcome as PricingOutcome.Failure).error).isEqualTo(expected)
    }

    private class FakeTokenProvider : IAuthTokenProvider {
        var refreshCount = 0
        var failure: AuthSessionException? = null

        override suspend fun signIn(
            email: String,
            password: String,
        ): String = "firebase-uid"

        override suspend fun getActiveBearerToken(): String {
            failure?.let { throw it }
            refreshCount += 1
            return "refreshed-token-$refreshCount"
        }

        override suspend fun signOut() = Unit

        override fun currentUserId(): String? = "firebase-uid"
    }

    private companion object {
        val query =
            PricingQueryDTO(
                mentorId = "mentor-profile-123",
                rawText = "Senior Android engineer mentoring Kotlin and Compose teams.",
                industry = "mobile",
                mentorCountry = "KE",
                clientCountry = "US",
                baseRateFloor = 4000f,
            )
        const val SUCCESS_RESPONSE =
            """{"basePredictedRate":4700.0,"mpesaTariffSurcharge":57.0,"finalQuotedRate":4757.0,"minQuotedRate":4460.0,"maxQuotedRate":7599.0,"kNeighborsUsed":5,"bilateralArbitrageFactor":0.51,"confidenceScore":0.0,"comparables":[],"reason":"Weighted from 5 indexed peers.","timestamp":"2026-10-06T12:00:00Z"}"""
    }
}
