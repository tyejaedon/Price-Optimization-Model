package dev.tyejaedon.pricing.viewmodel

import dev.tyejaedon.pricing.data.network.dto.PredictionResultDTO
import dev.tyejaedon.pricing.data.network.dto.QuoteHistoryItemDTO
import dev.tyejaedon.pricing.data.network.dto.SelfListingDTO
import dev.tyejaedon.pricing.data.network.dto.SelfProfileDTO
import dev.tyejaedon.pricing.ui.pricing.components.SupportedIndustries

/**
 * Matches the class diagram's `PricingUiState` dataType plus a sealed `PricingUiState` wrapper for
 * the four screen states called out in issue #74 (Idle/Loading/Success/Error). [PricingFormState]
 * holds in-progress form input and is retained across Loading/Error so the user's text is never lost.
 */
data class PricingFormState(
    val listingId: String? = null,
    val rawDescription: String = "",
    val mentorId: String = "",
    val selectedIndustry: String = "",
    val mentorCountry: String = "",
    val clientCountry: String = "",
    val competitivenessScore: Float = 0.5f,
    val baseRateFloor: String = "",
    val validationError: String? = null,
) {
    fun validate(): String? =
        when {
            rawDescription.trim().length < 20 -> "Description must be at least 20 characters."
            rawDescription.trim().length > 2000 -> "Description must be at most 2000 characters."
            mentorId.isBlank() -> "Enter your mentor profile ID."
            selectedIndustry.isBlank() -> "Select an industry."
            !ISO_2_COUNTRY_CODE.matches(mentorCountry) ->
                "Enter a 2-letter country code for your country."
            !ISO_2_COUNTRY_CODE.matches(clientCountry) ->
                "Enter a 2-letter country code for the client."
            !isBaseRateFloorValid() ->
                "Minimum rate must be a finite, non-negative number."
            else -> null
        }

    fun isFormValid(): Boolean = validate() == null

    private fun isBaseRateFloorValid(): Boolean {
        if (baseRateFloor.isBlank()) return true
        val floor = baseRateFloor.toFloatOrNull() ?: return false
        return floor.isFinite() && floor >= 0f
    }

    private companion object {
        val ISO_2_COUNTRY_CODE =
            Regex(
                "[A-Za-z]{2}",
            )
    }
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

sealed interface ProfileUiState {
    data object Loading : ProfileUiState

    data object NeedsOnboarding : ProfileUiState

    data class Ready(
        val profile: SelfProfileDTO,
    ) : ProfileUiState

    data class Error(
        val message: String,
    ) : ProfileUiState
}

enum class MentorTab(
    val label: String,
) {
    QUOTE("Quote"),
    LISTINGS("Listings"),
    HISTORY("History"),
}

data class MentorWorkspaceState(
    val selectedTab: MentorTab = MentorTab.QUOTE,
    val quoteStep: Int = 0,
    val modelsLoaded: Boolean = true,
    val industries: List<String> = SupportedIndustries,
    val listings: List<SelfListingDTO> = emptyList(),
    val history: List<QuoteHistoryItemDTO> = emptyList(),
    val feedbackStatusByTx: Map<String, String> = emptyMap(),
    val isLoading: Boolean = false,
    val statusMessage: String? = null,
    val errorMessage: String? = null,
)
