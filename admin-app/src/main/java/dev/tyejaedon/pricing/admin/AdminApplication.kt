package dev.tyejaedon.pricing.admin

import android.app.Application
import dev.tyejaedon.pricing.admin.di.AdminContainer

class AdminApplication : Application() {
    lateinit var container: AdminContainer
        private set

    override fun onCreate() {
        super.onCreate()
        container = AdminContainer()
    }
}
