package dev.tyejaedon.pricing.admin.domain

sealed interface AdminOutcome<out T> {
    data class Success<T>(
        val value: T,
    ) : AdminOutcome<T>

    data class Failure(
        val error: AdminFailure,
    ) : AdminOutcome<Nothing>
}

sealed class AdminFailure(
    val message: String,
) {
    data object Forbidden : AdminFailure("Invalid or missing administrator token.")

    data object Network : AdminFailure("No connection. Check your network and try again.")

    data object ServiceUnavailable : AdminFailure("The pricing service is temporarily unavailable.")

    data class Validation(
        val detail: String,
    ) : AdminFailure(detail)

    data class Unknown(
        val detail: String,
    ) : AdminFailure(detail)
}
