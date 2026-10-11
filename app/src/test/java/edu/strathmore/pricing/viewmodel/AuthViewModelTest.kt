package edu.strathmore.pricing.viewmodel

import app.cash.turbine.test
import com.google.common.truth.Truth.assertThat
import edu.strathmore.pricing.data.auth.AuthSessionException
import edu.strathmore.pricing.data.auth.IAuthTokenProvider
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class AuthViewModelTest {
    private val dispatcher = StandardTestDispatcher()
    private val authProvider = FakeAuthTokenProvider()

    @Before
    fun setUp() {
        Dispatchers.setMain(dispatcher)
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    @Test
    fun `successful sign in opens an authenticated session`() =
        runTest(dispatcher) {
            val viewModel = AuthViewModel(authProvider)
            viewModel.uiState.test {
                assertThat(awaitItem()).isEqualTo(AuthUiState.SignedOut)
                viewModel.signIn("mentor@example.test", "password")
                assertThat(awaitItem()).isEqualTo(AuthUiState.SigningIn)
                assertThat(awaitItem()).isEqualTo(AuthUiState.SignedIn("firebase-uid"))
                cancelAndIgnoreRemainingEvents()
            }
            assertThat(authProvider.currentUserId()).isEqualTo("firebase-uid")
        }

    @Test
    fun `failed sign in leaves the client signed out with a safe error`() =
        runTest(dispatcher) {
            authProvider.signInFailure = AuthSessionException("Email or password is incorrect.")
            val viewModel = AuthViewModel(authProvider)
            viewModel.uiState.test {
                awaitItem()
                viewModel.signIn("mentor@example.test", "wrong")
                assertThat(awaitItem()).isEqualTo(AuthUiState.SigningIn)
                assertThat(awaitItem()).isEqualTo(AuthUiState.Error("Email or password is incorrect."))
                cancelAndIgnoreRemainingEvents()
            }
            assertThat(authProvider.currentUserId()).isNull()
        }

    @Test
    fun `sign out clears the restored session`() =
        runTest(dispatcher) {
            authProvider.userId = "firebase-uid"
            val viewModel = AuthViewModel(authProvider)
            viewModel.uiState.test {
                assertThat(awaitItem()).isEqualTo(AuthUiState.SignedIn("firebase-uid"))
                viewModel.signOut()
                assertThat(awaitItem()).isEqualTo(AuthUiState.SignedOut)
                cancelAndIgnoreRemainingEvents()
            }
            assertThat(authProvider.currentUserId()).isNull()
        }
}

private class FakeAuthTokenProvider : IAuthTokenProvider {
    var userId: String? = null
    var signInFailure: AuthSessionException? = null

    override suspend fun signIn(
        email: String,
        password: String,
    ): String {
        signInFailure?.let { throw it }
        return "firebase-uid".also { userId = it }
    }

    override suspend fun getActiveBearerToken(): String = if (userId != null) "fresh-token" else throw AuthSessionException("Signed out")

    override suspend fun signOut() {
        userId = null
    }

    override fun currentUserId(): String? = userId
}
