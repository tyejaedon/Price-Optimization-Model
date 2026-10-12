package edu.strathmore.pricing.data.auth

/** Keeps Firebase SDK details outside the repository and presentation layers. */
interface IAuthTokenProvider {
    suspend fun signIn(
        email: String,
        password: String,
    ): String

    /** Returns a freshly refreshed ID token. Throws if signed out or refresh fails. */
    suspend fun getActiveBearerToken(): String

    suspend fun signOut()

    fun currentUserId(): String?
}
