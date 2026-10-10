package edu.strathmore.pricing

import android.app.Application
import edu.strathmore.pricing.di.AppContainer

/**
 * Application entry point. Owns the single [AppContainer] used for manual dependency injection
 * (see di/AppContainer.kt) so [edu.strathmore.pricing.viewmodel.PricingViewModel] instances can be
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

