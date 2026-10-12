package edu.strathmore.pricing.di

import android.content.Context
import com.google.gson.GsonBuilder
import edu.strathmore.pricing.BuildConfig
import edu.strathmore.pricing.data.auth.FirebaseAuthManager
import edu.strathmore.pricing.data.auth.IAuthTokenProvider
import edu.strathmore.pricing.data.network.PricingApiService
import edu.strathmore.pricing.data.repository.FakePricingRepository
import edu.strathmore.pricing.data.repository.PricingRepositoryImpl
import edu.strathmore.pricing.domain.IPricingRepository
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

/**
 * Minimal manual dependency container (no Hilt/Koin). [pricingRepository] selects the live protected
 * API only when `useLiveBackend=true` is supplied at build time; offline builds use the fake repo.
 */
class AppContainer(
    private val context: Context,
) {
    val authManager: IAuthTokenProvider by lazy { FirebaseAuthManager.create(context) }

    private val okHttpClient: OkHttpClient by lazy {
        OkHttpClient
            .Builder()
            .connectTimeout(10, TimeUnit.SECONDS)
            .readTimeout(15, TimeUnit.SECONDS)
            .writeTimeout(15, TimeUnit.SECONDS)
            .callTimeout(20, TimeUnit.SECONDS)
            .apply {
                if (BuildConfig.DEBUG) {
                    addInterceptor(HttpLoggingInterceptor().apply { level = HttpLoggingInterceptor.Level.BASIC })
                }
            }.build()
    }

    private val apiService: PricingApiService by lazy {
        Retrofit
            .Builder()
            .baseUrl(BuildConfig.PRICING_API_BASE_URL)
            .client(okHttpClient)
            .addConverterFactory(GsonConverterFactory.create(GsonBuilder().create()))
            .build()
            .create(PricingApiService::class.java)
    }

    val pricingRepository: IPricingRepository by lazy {
        if (BuildConfig.USE_LIVE_BACKEND) {
            PricingRepositoryImpl(apiService, authManager)
        } else {
            FakePricingRepository()
        }
    }
}
