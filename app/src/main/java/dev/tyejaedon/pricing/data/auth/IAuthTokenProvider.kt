package dev.tyejaedon.pricing.data.auth

/** Keeps Firebase SDK details outside the repository and presentation layers. */
interface IAuthTokenProvider {
    suspend fun signIn(
        email: String,
        password: String,
    ): String

    suspend fun signUp(
        email: String,
        password: String,
    ): String = signIn(email, password)

    suspend fun sendPasswordReset(email: String) = Unit

    /** Returns a valid ID token (cached or refreshed). Throws if signed out or refresh fails. */
    suspend fun getActiveBearerToken(): String

    suspend fun signOut()

    fun currentUserId(): String?

    fun currentUserEmail(): String? = null
}
