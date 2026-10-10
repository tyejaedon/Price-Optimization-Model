package edu.strathmore.pricing.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewmodel.CreationExtras
import edu.strathmore.pricing.domain.IPricingRepository

/** Simple factory since the scaffold avoids a DI framework dependency (see di/AppContainer.kt). */
class PricingViewModelFactory(
    private val repository: IPricingRepository,
) : ViewModelProvider.Factory {

    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>, extras: CreationExtras): T {
        require(modelClass.isAssignableFrom(PricingViewModel::class.java)) {
            "Unknown ViewModel class: ${modelClass.name}"
        }
        return PricingViewModel(repository) as T
    }
}
