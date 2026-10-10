package edu.strathmore.pricing.data.auth

/**
 * Abstraction over `FirebaseAuthManager` so the repository/ViewModel layer never depends on the
 * concrete Firebase SDK type directly (testability + matches the class diagram boundary). Full
 * sign-in, refresh, encrypted-storage and logout semantics are implemented in issue #75 (M12.2);
 * this interface only fixes the stable contract other M12/M13 work can build against.
 */
interface IAuthTokenProvider {
    /** Returns a currently valid bearer token, refreshing if necessary. Throws if signed out. */
    suspend fun getActiveBearerToken(): String

    suspend fun signOut()
}
