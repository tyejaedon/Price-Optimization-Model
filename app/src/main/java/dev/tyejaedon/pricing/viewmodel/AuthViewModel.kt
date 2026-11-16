package dev.tyejaedon.pricing.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dev.tyejaedon.pricing.data.auth.AuthSessionException
import dev.tyejaedon.pricing.data.auth.IAuthTokenProvider
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class AuthViewModel(
    private val authTokenProvider: IAuthTokenProvider,
) : ViewModel() {
    private val _uiState =
        MutableStateFlow<AuthUiState>(
            authTokenProvider.currentUserId()?.let(AuthUiState::SignedIn) ?: AuthUiState.SignedOut,
        )
    val uiState: StateFlow<AuthUiState> = _uiState.asStateFlow()

    fun signIn(
        email: String,
        password: String,
    ) {
        _uiState.value = AuthUiState.SigningIn
        viewModelScope.launch {
            try {
                _uiState.value = AuthUiState.SignedIn(authTokenProvider.signIn(email, password))
            } catch (error: AuthSessionException) {
                _uiState.value = AuthUiState.Error(error.message ?: "Unable to sign in.")
            }
        }
    }

    fun signUp(
        email: String,
        password: String,
    ) {
        _uiState.value = AuthUiState.SigningIn
        viewModelScope.launch {
            try {
                _uiState.value = AuthUiState.SignedIn(authTokenProvider.signUp(email, password))
            } catch (error: AuthSessionException) {
                _uiState.value = AuthUiState.Error(error.message ?: "Unable to create account.")
            }
        }
    }

    fun signOut() {
        viewModelScope.launch {
            authTokenProvider.signOut()
            _uiState.value = AuthUiState.SignedOut
        }
    }
}
