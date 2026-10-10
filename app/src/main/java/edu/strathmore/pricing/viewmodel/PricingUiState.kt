package edu.strathmore.pricing.viewmodel

import edu.strathmore.pricing.data.network.dto.PredictionResultDTO

/**
 * Matches the class diagram's `PricingUiState` dataType plus a sealed `PricingUiState` wrapper for
 * the four screen states called out in issue #74 (Idle/Loading/Success/Error). [PricingFormState]
 * holds in-progress form input and is retained across Loading/Error so the user's text is never lost.
 */
data class PricingFormState(
    val rawDescription: String = "",
    val selectedIndustry: String = "",
    val mentorCountry: String = "",
    val clientCountry: String = "",
    val competitivenessScore: Float = 0.5f,
    val baseRateFloor: String = "",
    val validationError: String? = null,
) {
    fun isFormValid(): Boolean =
        rawDescription.trim().length >= 20 &&
            selectedIndustry.isNotBlank() &&
            mentorCountry.length == 2 &&
            clientCountry.length == 2
}

sealed interface PricingUiState {
    val form: PricingFormState

    data class Idle(
        override val form: PricingFormState = PricingFormState(),
    ) : PricingUiState

    data class Loading(
        override val form: PricingFormState,
    ) : PricingUiState

    data class Success(
        override val form: PricingFormState,
        val result: PredictionResultDTO,
    ) : PricingUiState

    data class Error(
        override val form: PricingFormState,
        val message: String,
    ) : PricingUiState

    fun hasData(): Boolean = this is Success
}
