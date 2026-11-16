package dev.tyejaedon.pricing.admin.di

import com.google.gson.GsonBuilder
import dev.tyejaedon.pricing.admin.BuildConfig
import dev.tyejaedon.pricing.admin.data.network.AdminApiService
import dev.tyejaedon.pricing.admin.data.repository.AdminRepositoryImpl
import dev.tyejaedon.pricing.admin.data.repository.FakeAdminRepository
import dev.tyejaedon.pricing.admin.domain.IAdminRepository
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

class AdminContainer {
    private val okHttpClient: OkHttpClient by lazy {
        OkHttpClient
            .Builder()
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .writeTimeout(30, TimeUnit.SECONDS)
            .callTimeout(60, TimeUnit.SECONDS)
            .apply {
                if (BuildConfig.DEBUG) {
                    addInterceptor(HttpLoggingInterceptor().apply { level = HttpLoggingInterceptor.Level.BASIC })
                }
            }.build()
    }

    private val apiService: AdminApiService by lazy {
        Retrofit
            .Builder()
            .baseUrl(BuildConfig.PRICING_API_BASE_URL)
            .client(okHttpClient)
            .addConverterFactory(GsonConverterFactory.create(GsonBuilder().create()))
            .build()
            .create(AdminApiService::class.java)
    }

    val adminRepository: IAdminRepository by lazy {
        if (BuildConfig.USE_LIVE_BACKEND) {
            AdminRepositoryImpl(apiService)
        } else {
            FakeAdminRepository()
        }
    }
}
