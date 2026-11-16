package dev.tyejaedon.pricing

import android.app.Application
import dev.tyejaedon.pricing.di.AppContainer

/**
 * Application entry point. Owns the single [AppContainer] used for manual dependency injection
 * (see di/AppContainer.kt) so [dev.tyejaedon.pricing.viewmodel.PricingViewModel] instances can be
 * constructed without a DI framework dependency for this scaffold (issue #74).
 */
class PricingApplication : Application() {
    lateinit var container: AppContainer
        private set

    override fun onCreate() {
        super.onCreate()
        container = AppContainer(applicationContext)
    }
}
