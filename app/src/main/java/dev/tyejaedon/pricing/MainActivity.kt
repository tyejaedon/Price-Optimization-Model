package dev.tyejaedon.pricing

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.viewModels
import androidx.compose.runtime.getValue
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import dev.tyejaedon.pricing.ui.auth.AuthenticationScreen
import dev.tyejaedon.pricing.ui.pricing.PricingScreen
import dev.tyejaedon.pricing.ui.theme.PricingTheme
import dev.tyejaedon.pricing.viewmodel.AuthUiState
import dev.tyejaedon.pricing.viewmodel.AuthViewModel
import dev.tyejaedon.pricing.viewmodel.AuthViewModelFactory
import dev.tyejaedon.pricing.viewmodel.PricingViewModel
import dev.tyejaedon.pricing.viewmodel.PricingViewModelFactory

class MainActivity : ComponentActivity() {
    private val authViewModel by viewModels<AuthViewModel>(
        factoryProducer = {
            AuthViewModelFactory((application as PricingApplication).container.authManager)
        },
    )
    private val viewModel by viewModels<PricingViewModel>(
        factoryProducer = {
            PricingViewModelFactory((application as PricingApplication).container.pricingRepository)
        },
    )

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            PricingTheme {
                val authState by authViewModel.uiState.collectAsStateWithLifecycle()
                when {
                    !BuildConfig.USE_LIVE_BACKEND -> PricingScreen(viewModel = viewModel, demoMode = true)
                    authState is AuthUiState.SignedIn ->
                        PricingScreen(
                            viewModel = viewModel,
                            onSignOut = authViewModel::signOut,
                            userEmail =
                                (application as PricingApplication)
                                    .container.authManager
                                    .currentUserEmail()
                                    .orEmpty(),
                            autoLoadProfile = true,
                        )
                    else -> AuthenticationScreen(viewModel = authViewModel)
                }
            }
        }
    }
}
