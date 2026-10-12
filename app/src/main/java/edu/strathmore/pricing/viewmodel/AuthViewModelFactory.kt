package edu.strathmore.pricing.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import edu.strathmore.pricing.data.auth.IAuthTokenProvider

class AuthViewModelFactory(
    private val authTokenProvider: IAuthTokenProvider,
) : ViewModelProvider.Factory {
    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        require(modelClass.isAssignableFrom(AuthViewModel::class.java)) {
            "Unsupported ViewModel type: ${modelClass.name}"
        }
        return AuthViewModel(authTokenProvider) as T
    }
}
