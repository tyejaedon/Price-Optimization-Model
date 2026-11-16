package dev.tyejaedon.pricing.admin.data.repository

import com.google.common.truth.Truth.assertThat
import dev.tyejaedon.pricing.admin.data.network.AdminApiService
import dev.tyejaedon.pricing.admin.data.network.dto.GridSearchConfigDTO
import dev.tyejaedon.pricing.admin.domain.AdminFailure
import dev.tyejaedon.pricing.admin.domain.AdminOutcome
import kotlinx.coroutines.Dispatchers
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

class AdminRepositoryImplTest {
    private val server = MockWebServer()
    private lateinit var repository: AdminRepositoryImpl

    @Before
    fun setUp() {
        server.start()
        val client =
            OkHttpClient
                .Builder()
                .connectTimeout(1, TimeUnit.SECONDS)
                .readTimeout(1, TimeUnit.SECONDS)
                .build()
        val api =
            Retrofit
                .Builder()
                .baseUrl(server.url("/"))
                .client(client)
                .addConverterFactory(GsonConverterFactory.create())
                .build()
                .create(AdminApiService::class.java)
        repository = AdminRepositoryImpl(api, Dispatchers.IO)
    }

    @After
    fun tearDown() {
        server.shutdown()
    }

    @Test
    fun `admin calls without token fail with forbidden without network call`() =
        runTest {
            val outcome = repository.fetchMetrics()
            assertThat(outcome).isInstanceOf(AdminOutcome.Failure::class.java)
            assertThat((outcome as AdminOutcome.Failure).error).isEqualTo(AdminFailure.Forbidden)
            assertThat(server.requestCount).isEqualTo(0)
        }

    @Test
    fun `fetchDrift sends X-Admin-Token and parses distribution summary`() =
        runTest {
            repository.setAdminToken("ops-secret")
            server.enqueue(
                MockResponse().setBody(
                    """{"totalTransactions":5,"byIndustry":{"mobile":3,"data_ai":2},"byCorridor":{"KE->US":5},"averageFinalRate":2500.0}""",
                ),
            )

            val outcome = repository.fetchDrift()

            assertThat(outcome).isInstanceOf(AdminOutcome.Success::class.java)
            val drift = (outcome as AdminOutcome.Success).value
            assertThat(drift.totalTransactions).isEqualTo(5)
            assertThat(drift.byIndustry["mobile"]).isEqualTo(3)
            val req = server.takeRequest()
            assertThat(req.path).isEqualTo("/api/v1/admin/drift?limit=500")
            assertThat(req.getHeader("X-Admin-Token")).isEqualTo("ops-secret")
        }

    @Test
    fun `updateGridSearch sends PUT payload and returns updated config`() =
        runTest {
            repository.setAdminToken("ops-secret")
            server.enqueue(
                MockResponse().setBody(
                    """{"k_neighbors":[1,3,5],"text_weight":2.0,"metadata_weight":0.5,"idw_epsilon":0.001,"minimum_partition_size":2,"allow_fallback":false}""",
                ),
            )

            val outcome =
                repository.updateGridSearch(
                    GridSearchConfigDTO(kNeighbors = listOf(1, 3, 5), textWeight = 2.0f, allowFallback = false),
                )

            assertThat(outcome).isInstanceOf(AdminOutcome.Success::class.java)
            assertThat((outcome as AdminOutcome.Success).value.textWeight).isEqualTo(2.0f)
            val req = server.takeRequest()
            assertThat(req.method).isEqualTo("PUT")
            assertThat(req.path).isEqualTo("/api/v1/admin/grid-search")
        }

    @Test
    fun `403 maps to AdminFailure Forbidden`() =
        runTest {
            repository.setAdminToken("bad-token")
            server.enqueue(MockResponse().setResponseCode(403))

            val outcome = repository.fetchArtifacts()

            assertThat((outcome as AdminOutcome.Failure).error).isEqualTo(AdminFailure.Forbidden)
        }
}
