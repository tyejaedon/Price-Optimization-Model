package edu.strathmore.pricing

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.viewModels
import androidx.compose.runtime.getValue
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import edu.strathmore.pricing.ui.auth.AuthenticationScreen
import edu.strathmore.pricing.ui.pricing.PricingScreen
import edu.strathmore.pricing.ui.theme.PricingTheme
import edu.strathmore.pricing.viewmodel.AuthUiState
import edu.strathmore.pricing.viewmodel.AuthViewModel
import edu.strathmore.pricing.viewmodel.AuthViewModelFactory
import edu.strathmore.pricing.viewmodel.PricingViewModel
import edu.strathmore.pricing.viewmodel.PricingViewModelFactory

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
                        PricingScreen(viewModel = viewModel, onSignOut = authViewModel::signOut)
                    else -> AuthenticationScreen(viewModel = authViewModel)
                }
            }
        }
    }
}
