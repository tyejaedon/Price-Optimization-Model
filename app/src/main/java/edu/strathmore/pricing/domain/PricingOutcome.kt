package edu.strathmore.pricing.domain

/**
 * Minimal success/typed-failure wrapper so the ViewModel never has to catch raw exceptions from
 * the repository layer. Mirrors Kotlin's `Result` but keeps a stable, testable failure type.
 */
sealed interface PricingOutcome<out T> {
    data class Success<T>(
        val value: T,
    ) : PricingOutcome<T>

    data class Failure(
        val error: PricingFailure,
    ) : PricingOutcome<Nothing>
}

/** Explicit, user-presentable failure categories (extended with HTTP mapping in #76). */
sealed class PricingFailure(
    val message: String,
) {
    data class Validation(
        val field: String,
        val detail: String,
    ) : PricingFailure(detail)

    data object Unauthorized : PricingFailure("Your session expired. Please sign in again.")

    data object Network : PricingFailure("No connection. Check your network and try again.")

    data object ServiceUnavailable : PricingFailure("The pricing service is temporarily unavailable.")

    data class Unknown(
        val detail: String,
    ) : PricingFailure(detail)
}
