package edu.strathmore.pricing.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import edu.strathmore.pricing.data.network.dto.PricingQueryDTO
import edu.strathmore.pricing.domain.IPricingRepository
import edu.strathmore.pricing.domain.PricingOutcome
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/**
 * Matches the class diagram's `PricingViewModel`. The mentor profile document ID is entered
 * explicitly; the protected backend verifies it belongs to the signed-in Firebase UID.
 */
class PricingViewModel(
    private val repository: IPricingRepository,
) : ViewModel() {
    private val _uiState = MutableStateFlow<PricingUiState>(PricingUiState.Idle())
    val uiState: StateFlow<PricingUiState> = _uiState.asStateFlow()

    fun onDescriptionChanged(text: String) {
        updateForm { it.copy(rawDescription = text, validationError = null) }
    }

    fun onMentorIdChanged(mentorId: String) {
        updateForm { it.copy(mentorId = mentorId, validationError = null) }
    }

    fun onIndustrySelected(industry: String) {
        updateForm { it.copy(selectedIndustry = industry, validationError = null) }
    }

    fun onMentorCountrySelected(country: String) {
        updateForm { it.copy(mentorCountry = country.uppercase(), validationError = null) }
    }

    fun onClientCountrySelected(country: String) {
        updateForm { it.copy(clientCountry = country.uppercase(), validationError = null) }
    }

    fun onCompetitivenessScoreChanged(score: Float) {
        updateForm { it.copy(competitivenessScore = score.coerceIn(0f, 1f)) }
    }

    fun onBaseRateFloorChanged(value: String) {
        updateForm { it.copy(baseRateFloor = value) }
    }

    fun submitPriceOptimization() {
        val form = _uiState.value.form
        val validationMessage = validateFormInputs(form)
        if (validationMessage != null) {
            _uiState.update { PricingUiState.Error(form.copy(validationError = validationMessage), validationMessage) }
            return
        }

        _uiState.update { PricingUiState.Loading(form) }
        viewModelScope.launch {
            val query = constructQueryPayload(form)
            when (val outcome = repository.calculateOptimalRate(query)) {
                is PricingOutcome.Success -> _uiState.update { PricingUiState.Success(form, outcome.value) }
                is PricingOutcome.Failure -> _uiState.update { PricingUiState.Error(form, outcome.error.message) }
            }
        }
    }

    fun retryOptimization() {
        submitPriceOptimization()
    }

    fun clearForm() {
        _uiState.update { PricingUiState.Idle() }
    }

    private fun validateFormInputs(form: PricingFormState): String? =
        when {
            form.rawDescription.trim().length < 20 -> "Description must be at least 20 characters."
            form.rawDescription.trim().length > 2000 -> "Description must be at most 2000 characters."
            form.mentorId.isBlank() -> "Enter your mentor profile ID."
            form.selectedIndustry.isBlank() -> "Select an industry."
            !Regex("[A-Za-z]{2}").matches(form.mentorCountry) ->
                "Enter a 2-letter country code for your country."
            !Regex("[A-Za-z]{2}").matches(form.clientCountry) ->
                "Enter a 2-letter country code for the client."
            form.baseRateFloor.isNotBlank() &&
                (form.baseRateFloor.toFloatOrNull()?.let { !it.isFinite() || it < 0f } != false) ->
                "Minimum rate must be a finite, non-negative number."
            else -> null
        }

    private fun constructQueryPayload(form: PricingFormState): PricingQueryDTO =
        PricingQueryDTO(
            mentorId = form.mentorId.trim(),
            rawText = form.rawDescription.trim(),
            industry = form.selectedIndustry,
            mentorCountry = form.mentorCountry,
            clientCountry = form.clientCountry,
            competitivenessScore = form.competitivenessScore,
            baseRateFloor = form.baseRateFloor.toFloatOrNull(),
        )

    private inline fun updateForm(transform: (PricingFormState) -> PricingFormState) {
        _uiState.update { current ->
            when (current) {
                is PricingUiState.Idle -> current.copy(form = transform(current.form))
                is PricingUiState.Loading -> current // form is frozen while a request is in flight
                is PricingUiState.Success -> PricingUiState.Idle(transform(current.form))
                is PricingUiState.Error -> PricingUiState.Idle(transform(current.form))
            }
        }
    }
}
