package dev.tyejaedon.pricing.admin

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.viewModels
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.getValue
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import dev.tyejaedon.pricing.admin.ui.AdminAuthScreen
import dev.tyejaedon.pricing.admin.ui.AdminDashboardScreen
import dev.tyejaedon.pricing.admin.viewmodel.AdminSessionState
import dev.tyejaedon.pricing.admin.viewmodel.AdminViewModel
import dev.tyejaedon.pricing.admin.viewmodel.AdminViewModelFactory

class AdminActivity : ComponentActivity() {
    private val viewModel by viewModels<AdminViewModel>(
        factoryProducer = {
            AdminViewModelFactory((application as AdminApplication).container.adminRepository)
        },
    )

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme {
                val sessionState by viewModel.sessionState.collectAsStateWithLifecycle()
                when {
                    !BuildConfig.USE_LIVE_BACKEND || sessionState is AdminSessionState.Unlocked -> {
                        AdminDashboardScreen(
                            viewModel = viewModel,
                            demoMode = !BuildConfig.USE_LIVE_BACKEND,
                        )
                    }
                    else -> {
                        AdminAuthScreen(viewModel = viewModel)
                    }
                }
            }
        }
    }
}
