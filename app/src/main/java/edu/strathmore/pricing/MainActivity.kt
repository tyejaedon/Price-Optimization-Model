package edu.strathmore.pricing

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.viewModels
import edu.strathmore.pricing.ui.pricing.PricingScreen
import edu.strathmore.pricing.ui.theme.PricingTheme
import edu.strathmore.pricing.viewmodel.PricingViewModel
import edu.strathmore.pricing.viewmodel.PricingViewModelFactory

class MainActivity : ComponentActivity() {

    private val viewModel by viewModels<PricingViewModel>(
        factoryProducer = {
            PricingViewModelFactory((application as PricingApplication).container.pricingRepository)
        },
    )

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            PricingTheme {
                PricingScreen(viewModel = viewModel)
            }
        }
    }
}
