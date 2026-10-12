package edu.strathmore.pricing

import android.os.Build
import android.os.SystemClock
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.google.android.gms.tasks.Tasks
import com.google.firebase.auth.FirebaseAuth
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith
import java.net.URI
import java.util.concurrent.TimeUnit
import kotlin.math.ceil

@RunWith(AndroidJUnit4::class)
class AuthenticatedPricingRttTest {
    @Test
    fun authenticatedPricingRoundTripsUnderUmtsProfileWhenOptedIn() {
        val args = InstrumentationRegistry.getArguments()
        assumeTrue("Live RTT measurement is opt-in.", args.getString("rttMeasurementEnabled") == "true")

        val apiBaseUrl = URI(BuildConfig.PRICING_API_BASE_URL)
        require(apiBaseUrl.scheme == "https") { "Live RTT tests require an HTTPS staging API." }
        require(apiBaseUrl.rawUserInfo == null && apiBaseUrl.rawQuery == null && apiBaseUrl.rawFragment == null)
        require(apiBaseUrl.path.isEmpty() || apiBaseUrl.path == "/") { "Provide an API origin without a path." }
        val mentorId = requireNotNull(args.getString("mentorId")) { "Provide the test mentor profile ID." }
        val apiRegion = requireNotNull(args.getString("apiRegion")) { "Record the staging API region." }
        val sampleCount = args.getString("sampleCount")?.toIntOrNull() ?: DEFAULT_SAMPLE_COUNT
        val warmupCount = args.getString("warmupCount")?.toIntOrNull() ?: DEFAULT_WARMUP_COUNT
        require(sampleCount in 1..MAX_SAMPLE_COUNT) { "sampleCount must be between 1 and $MAX_SAMPLE_COUNT." }
        require(warmupCount in 0..MAX_WARMUP_COUNT) { "warmupCount must be between 0 and $MAX_WARMUP_COUNT." }

        val user =
            requireNotNull(FirebaseAuth.getInstance().currentUser) {
                "Sign in with the dedicated staging Firebase test account before running this measurement."
            }
        val apiOrigin = URI("${apiBaseUrl.scheme}://${apiBaseUrl.rawAuthority}/")
        val client =
            OkHttpClient
                .Builder()
                .callTimeout(REQUEST_TIMEOUT_SECONDS, TimeUnit.SECONDS)
                .build()

        val healthRequest =
            Request
                .Builder()
                .url(apiOrigin.resolve("/health").toString())
                .get()
                .build()
        client.newCall(healthRequest).execute().use { response ->
            assertEquals("Staging health check failed.", 200, response.code)
            val health = JSONObject(requireNotNull(response.body).string())
            assertEquals("HEALTHY", health.optString("status"))
            assertEquals("firestore", health.optString("database"))
            assertTrue("Staging models must be loaded.", health.optBoolean("modelsLoaded"))
        }

        val requestBody =
            JSONObject()
                .put("mentorId", mentorId)
                .put("rawText", TEST_DESCRIPTION)
                .put("industry", args.getString("industry") ?: "mobile")
                .put("mentorCountry", args.getString("mentorCountry") ?: "KE")
                .put("clientCountry", args.getString("clientCountry") ?: "US")
                .put("competitivenessScore", 0.5)
                .toString()
                .toRequestBody(JSON_MEDIA_TYPE)
        val quoteRequest =
            Request
                .Builder()
                .url(apiOrigin.resolve("/api/v1/optimize-price").toString())
                .post(requestBody)

        repeat(warmupCount) {
            val warmup = executeSample(client, user, quoteRequest)
            assertTrue("Warm-up failed (${warmup.failureType ?: warmup.statusCode}).", warmup.successful)
        }

        val samples = List(sampleCount) { executeSample(client, user, quoteRequest) }
        val successful = samples.filter(Sample::successful)
        val rtts = successful.map(Sample::fullRttMs)
        val inference = successful.mapNotNull(Sample::inferenceMs)
        val apiDurations = successful.mapNotNull(Sample::apiMs)
        val tokenRefresh = successful.mapNotNull(Sample::tokenRefreshMs)
        val rttP95 = percentileOrNull(rtts, 0.95)
        val failureTypes = samples.mapNotNull(Sample::failureType).groupingBy { it }.eachCount()
        val statusCodes = samples.mapNotNull(Sample::statusCode).groupingBy { it }.eachCount()
        val report =
            JSONObject()
                .put("profile", "Android Emulator UMTS: 384 kbit/s up/down, 35-70 ms one-way delay, 0% packet loss")
                .put("device", Build.MODEL)
                .put("androidVersion", Build.VERSION.RELEASE)
                .put("apiRegion", apiRegion)
                .put("warmups", warmupCount)
                .put("sampleCount", sampleCount)
                .put("successfulRequests", successful.size)
                .put("failureRate", (sampleCount - successful.size).toDouble() / sampleCount)
                .put("failureTypes", JSONObject(failureTypes))
                .put("statusCodes", JSONObject(statusCodes))
                .put("fullRttP50Ms", percentileOrNull(rtts, 0.50))
                .put("fullRttP95Ms", rttP95)
                .put("tokenRefreshP50Ms", percentileOrNull(tokenRefresh, 0.50))
                .put("backendApiP50Ms", percentileOrNull(apiDurations, 0.50))
                .put("backendApiP95Ms", percentileOrNull(apiDurations, 0.95))
                .put("backendInferenceP50Ms", percentileOrNull(inference, 0.50))
                .put("backendInferenceP95Ms", percentileOrNull(inference, 0.95))
        println("PRICING_RTT_REPORT=$report")

        assertEquals("Every authenticated sample must succeed; see PRICING_RTT_REPORT.", sampleCount, successful.size)
        assertNotNull("The backend must expose inference timing.", percentileOrNull(inference, 0.95))
        assertTrue("The p95 full authenticated RTT must be below 3000 ms.", requireNotNull(rttP95) < RTT_LIMIT_MS)
    }

    private fun executeSample(
        client: OkHttpClient,
        user: com.google.firebase.auth.FirebaseUser,
        request: Request.Builder,
    ): Sample {
        val started = SystemClock.elapsedRealtimeNanos()
        var tokenRefreshMs: Double? = null
        var statusCode: Int? = null
        var inferenceMs: Double? = null
        var apiMs: Double? = null
        return try {
            val tokenStarted = SystemClock.elapsedRealtimeNanos()
            val token = Tasks.await(user.getIdToken(true), TOKEN_TIMEOUT_SECONDS, TimeUnit.SECONDS).token
            tokenRefreshMs = (SystemClock.elapsedRealtimeNanos() - tokenStarted) / NANOS_PER_MILLI
            require(!token.isNullOrBlank()) { "Firebase returned no ID token." }

            client.newCall(request.header("Authorization", "Bearer $token").build()).execute().use { response ->
                statusCode = response.code
                inferenceMs = serverTimingDuration(response.header("Server-Timing"), "inference")
                apiMs = serverTimingDuration(response.header("Server-Timing"), "api")
                val body = JSONObject(requireNotNull(response.body).string())
                val successful = response.isSuccessful && body.has("finalQuotedRate")
                Sample(
                    fullRttMs = (SystemClock.elapsedRealtimeNanos() - started) / NANOS_PER_MILLI,
                    tokenRefreshMs = tokenRefreshMs,
                    inferenceMs = inferenceMs,
                    apiMs = apiMs,
                    statusCode = statusCode,
                    successful = successful,
                    failureType =
                        when {
                            successful -> null
                            !response.isSuccessful -> "http_${response.code}"
                            else -> "invalid_response"
                        },
                )
            }
        } catch (failure: Exception) {
            Sample(
                fullRttMs = (SystemClock.elapsedRealtimeNanos() - started) / NANOS_PER_MILLI,
                tokenRefreshMs = tokenRefreshMs,
                inferenceMs = inferenceMs,
                apiMs = apiMs,
                statusCode = statusCode,
                successful = false,
                failureType = failure.javaClass.simpleName,
            )
        }
    }

    private fun serverTimingDuration(
        header: String?,
        metricName: String,
    ): Double? =
        header
            ?.split(',')
            ?.asSequence()
            ?.map { it.trim().split(';') }
            ?.firstOrNull { it.firstOrNull() == metricName }
            ?.firstNotNullOfOrNull { component ->
                component
                    .trim()
                    .takeIf { it.startsWith("dur=") }
                    ?.substringAfter("dur=")
                    ?.toDoubleOrNull()
            }

    private fun percentileOrNull(
        values: List<Double>,
        percentile: Double,
    ): Double? {
        if (values.isEmpty()) return null
        require(percentile in 0.0..1.0)
        val rank = ceil(percentile * values.size).toInt().coerceAtLeast(1)
        return values.sorted()[rank - 1]
    }

    private data class Sample(
        val fullRttMs: Double,
        val tokenRefreshMs: Double?,
        val inferenceMs: Double?,
        val apiMs: Double?,
        val statusCode: Int?,
        val successful: Boolean,
        val failureType: String?,
    )

    private companion object {
        const val DEFAULT_SAMPLE_COUNT = 30
        const val DEFAULT_WARMUP_COUNT = 3
        const val MAX_SAMPLE_COUNT = 200
        const val MAX_WARMUP_COUNT = 10
        const val REQUEST_TIMEOUT_SECONDS = 20L
        const val TOKEN_TIMEOUT_SECONDS = 30L
        const val RTT_LIMIT_MS = 3_000.0
        const val NANOS_PER_MILLI = 1_000_000.0
        const val TEST_DESCRIPTION = "Experienced Android engineer mentoring teams in mobile application development."
        val JSON_MEDIA_TYPE = "application/json; charset=utf-8".toMediaType()
    }
}
