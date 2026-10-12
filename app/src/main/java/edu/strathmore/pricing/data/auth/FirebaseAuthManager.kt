package edu.strathmore.pricing.data.auth

import android.content.Context
import com.google.firebase.FirebaseApp
import com.google.firebase.FirebaseException
import com.google.firebase.FirebaseOptions
import com.google.firebase.auth.FirebaseAuth
import com.google.firebase.auth.FirebaseAuthException
import edu.strathmore.pricing.BuildConfig
import kotlinx.coroutines.tasks.await

/** Firebase owns the persisted refresh session; the app never stores ID tokens itself. */
class FirebaseAuthManager private constructor(
    private val firebaseAuth: FirebaseAuth?,
) : IAuthTokenProvider {
    override suspend fun signIn(
        email: String,
        password: String,
    ): String {
        val auth = requireAuth()
        if (email.isBlank() || password.isBlank()) {
            throw AuthSessionException("Enter your email and password.")
        }
        return try {
            auth
                .signInWithEmailAndPassword(email.trim(), password)
                .await()
                .user
                ?.uid
                ?: throw AuthSessionException("Firebase sign-in returned no user.")
        } catch (error: FirebaseAuthException) {
            throw AuthSessionException(authErrorMessage(error), error)
        } catch (error: FirebaseException) {
            throw AuthSessionException("Unable to sign in. Check your connection and try again.", error)
        }
    }

    override suspend fun getActiveBearerToken(): String {
        val user = requireAuth().currentUser ?: throw AuthSessionException("Sign in to request a quote.")
        return try {
            user.getIdToken(true).await().token
                ?: throw AuthSessionException("Firebase returned no ID token.")
        } catch (error: FirebaseException) {
            throw AuthSessionException("Your session could not be refreshed. Sign in again.", error)
        }
    }

    override suspend fun signOut() {
        firebaseAuth?.signOut()
    }

    override fun currentUserId(): String? = firebaseAuth?.currentUser?.uid

    private fun requireAuth(): FirebaseAuth =
        firebaseAuth ?: throw AuthSessionException(
            "Firebase is not configured. Set the Firebase project properties and rebuild the app.",
        )

    private fun authErrorMessage(error: FirebaseAuthException): String =
        when (error.errorCode) {
            "ERROR_INVALID_EMAIL" -> "Enter a valid email address."
            "ERROR_USER_NOT_FOUND", "ERROR_WRONG_PASSWORD", "ERROR_INVALID_CREDENTIAL" ->
                "Email or password is incorrect."
            "ERROR_USER_DISABLED" -> "This account has been disabled."
            else -> "Unable to sign in. Check your connection and try again."
        }

    companion object {
        fun create(context: Context): FirebaseAuthManager {
            val app =
                FirebaseApp.getApps(context).firstOrNull { it.name == FirebaseApp.DEFAULT_APP_NAME }
                    ?: createConfiguredApp(context)
            return FirebaseAuthManager(app?.let(FirebaseAuth::getInstance))
        }

        private fun createConfiguredApp(context: Context): FirebaseApp? {
            val apiKey = BuildConfig.FIREBASE_API_KEY
            val applicationId = BuildConfig.FIREBASE_APPLICATION_ID
            val projectId = BuildConfig.FIREBASE_PROJECT_ID
            if (apiKey.isBlank() || applicationId.isBlank() || projectId.isBlank()) return null

            val options =
                FirebaseOptions
                    .Builder()
                    .setApiKey(apiKey)
                    .setApplicationId(applicationId)
                    .setProjectId(projectId)
                    .build()
            return FirebaseApp.initializeApp(context, options)
        }
    }
}

class AuthSessionException(
    message: String,
    cause: Throwable? = null,
) : Exception(message, cause)
