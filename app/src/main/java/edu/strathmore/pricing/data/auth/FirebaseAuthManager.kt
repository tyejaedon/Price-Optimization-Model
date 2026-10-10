package edu.strathmore.pricing.data.auth

import com.google.firebase.auth.FirebaseAuth
import kotlinx.coroutines.tasks.await

/**
 * Concrete Firebase-backed [IAuthTokenProvider] matching the class diagram's `FirebaseAuthManager`.
 *
 * NOTE (scope boundary): issue #74/#140 only need this type to exist and compile against the
 * class-diagram shape so other M12/M13 modules can wire against it. The full implementation --
 * `EncryptedSharedPreferences`-backed secure caching, token-expiry handling, sign-in/out flows and
 * fake-auth tests -- is the explicit scope of issue #75 (M12.2) and must not be considered done
 * here. Do not ship this class to production before #75 lands.
 */
class FirebaseAuthManager(
    private val firebaseAuth: FirebaseAuth = FirebaseAuth.getInstance(),
) : IAuthTokenProvider {
    override suspend fun getActiveBearerToken(): String {
        val user =
            firebaseAuth.currentUser
                ?: throw IllegalStateException("No authenticated user; sign-in flow is implemented in #75")
        val result = user.getIdToken(true).await()
        return result.token
            ?: throw IllegalStateException("Firebase returned no ID token")
    }

    override suspend fun signOut() {
        firebaseAuth.signOut()
    }
}
