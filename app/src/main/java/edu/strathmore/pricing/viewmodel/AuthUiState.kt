package edu.strathmore.pricing.viewmodel

sealed interface AuthUiState {
    data object SignedOut : AuthUiState

    data object SigningIn : AuthUiState

    data class SignedIn(
        val userId: String,
    ) : AuthUiState

    data class Error(
        val message: String,
    ) : AuthUiState
}
