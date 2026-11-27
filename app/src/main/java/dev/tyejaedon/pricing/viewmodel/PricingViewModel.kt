package dev.tyejaedon.pricing.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dev.tyejaedon.pricing.data.network.dto.PricingQueryDTO
import dev.tyejaedon.pricing.data.network.dto.QuoteFeedbackRequestDTO
import dev.tyejaedon.pricing.data.network.dto.QuoteHistoryItemDTO
import dev.tyejaedon.pricing.data.network.dto.SelfListingDTO
import dev.tyejaedon.pricing.data.network.dto.SelfListingUpsertDTO
import dev.tyejaedon.pricing.data.network.dto.SelfProfileUpsertDTO
import dev.tyejaedon.pricing.domain.IPricingRepository
import dev.tyejaedon.pricing.domain.PricingOutcome
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

    private val _profileState = MutableStateFlow<ProfileUiState>(ProfileUiState.Loading)
    val profileState: StateFlow<ProfileUiState> = _profileState.asStateFlow()

    private val _workspaceState = MutableStateFlow(MentorWorkspaceState())
    val workspaceState: StateFlow<MentorWorkspaceState> = _workspaceState.asStateFlow()

    fun setQuoteStep(step: Int) {
        _workspaceState.update { it.copy(quoteStep = step.coerceIn(0, 2)) }
    }

    fun openQuoteDetail() {
        if (_uiState.value is PricingUiState.Success) {
            _workspaceState.update { it.copy(isQuoteDetailOpen = true) }
        }
    }

    fun closeQuoteDetail() {
        _workspaceState.update { it.copy(isQuoteDetailOpen = false) }
    }

    fun selectTab(tab: MentorTab) {
        _workspaceState.update {
            it.copy(
                selectedTab = tab,
                isQuoteDetailOpen = false,
                statusMessage = null,
                errorMessage = null,
            )
        }
        when (tab) {
            MentorTab.LISTINGS -> loadListings()
            MentorTab.HISTORY -> loadHistory()
            MentorTab.QUOTE -> Unit
        }
    }

    fun loadMetadata() {
        viewModelScope.launch {
            val outcome = repository.fetchMetadata()
            if (outcome is PricingOutcome.Success) {
                _workspaceState.update {
                    it.copy(
                        modelsLoaded = outcome.value.modelsLoaded,
                        industries = outcome.value.industries.ifEmpty { it.industries },
                    )
                }
            }
        }
    }

    fun loadListings() {
        _workspaceState.update { it.copy(isLoading = true, errorMessage = null) }
        viewModelScope.launch {
            when (val outcome = repository.fetchMyListings()) {
                is PricingOutcome.Success ->
                    _workspaceState.update { it.copy(isLoading = false, listings = outcome.value) }
                is PricingOutcome.Failure ->
                    _workspaceState.update { it.copy(isLoading = false, errorMessage = outcome.error.message) }
            }
        }
    }

    fun saveListing(
        listingId: String,
        title: String,
        industryId: String,
        rawText: String,
        verifiedRate: Float,
    ) {
        val cleanId = listingId.trim().ifBlank { "listing-${System.currentTimeMillis()}" }
        _workspaceState.update { it.copy(isLoading = true, statusMessage = null, errorMessage = null) }
        viewModelScope.launch {
            val payload =
                SelfListingUpsertDTO(
                    title = title.trim(),
                    industryId = industryId,
                    rawText = rawText.trim(),
                    verifiedRate = verifiedRate,
                )
            when (val outcome = repository.upsertMyListing(cleanId, payload)) {
                is PricingOutcome.Success -> {
                    _workspaceState.update {
                        it.copy(isLoading = false, statusMessage = "Saved listing \"${outcome.value.title}\".")
                    }
                    loadListings()
                }
                is PricingOutcome.Failure ->
                    _workspaceState.update { it.copy(isLoading = false, errorMessage = outcome.error.message) }
            }
        }
    }

    fun applyListingToQuote(listing: SelfListingDTO) {
        updateForm {
            it.copy(
                listingId = listing.listingId,
                rawDescription = listing.rawText,
                selectedIndustry = listing.industryId,
                baseRateFloor = listing.baseRateFloor?.toString() ?: it.baseRateFloor,
                validationError = null,
            )
        }
        _workspaceState.update {
            it.copy(
                selectedTab = MentorTab.QUOTE,
                quoteStep = 1,
                statusMessage = "Loaded \"${listing.title}\" — confirm your countries to calculate.",
            )
        }
    }

    fun applyHistoryItemToQuote(item: QuoteHistoryItemDTO) {
        val matchedListing =
            item.listingId?.let { id ->
                _workspaceState.value.listings.firstOrNull { it.listingId == id }
            }
        updateForm { current ->
            current.copy(
                listingId = matchedListing?.listingId ?: current.listingId,
                rawDescription = matchedListing?.rawText ?: current.rawDescription,
                selectedIndustry = item.selectedIndustry ?: matchedListing?.industryId ?: current.selectedIndustry,
                mentorCountry = item.mentorCountryCode?.uppercase() ?: current.mentorCountry,
                clientCountry = item.clientCountryCode?.uppercase() ?: current.clientCountry,
                validationError = null,
            )
        }
        val effectiveDescription = matchedListing?.rawText ?: _uiState.value.form.rawDescription
        val nextStep = if (effectiveDescription.trim().length >= 20) 1 else 0
        val mentorCode = item.mentorCountryCode ?: "KE"
        val clientCode = item.clientCountryCode ?: "US"
        _workspaceState.update {
            it.copy(
                selectedTab = MentorTab.QUOTE,
                quoteStep = nextStep,
                isQuoteDetailOpen = false,
                statusMessage = "Loaded corridor $mentorCode -> $clientCode into Quote.",
            )
        }
    }

    fun loadHistory() {
        _workspaceState.update { it.copy(isLoading = true, errorMessage = null) }
        viewModelScope.launch {
            when (val outcome = repository.fetchMyHistory()) {
                is PricingOutcome.Success ->
                    _workspaceState.update { it.copy(isLoading = false, history = outcome.value) }
                is PricingOutcome.Failure ->
                    _workspaceState.update { it.copy(isLoading = false, errorMessage = outcome.error.message) }
            }
        }
    }

    fun submitFeedback(
        transactionId: String,
        outcomeValue: String,
        actualRate: Float? = null,
        notes: String? = null,
    ) {
        _workspaceState.update { it.copy(isLoading = true, statusMessage = null, errorMessage = null) }
        viewModelScope.launch {
            val payload = QuoteFeedbackRequestDTO(outcome = outcomeValue, actualRate = actualRate, notes = notes)
            when (val outcome = repository.submitQuoteFeedback(transactionId, payload)) {
                is PricingOutcome.Success ->
                    _workspaceState.update { current ->
                        current.copy(
                            isLoading = false,
                            feedbackStatusByTx = current.feedbackStatusByTx + (transactionId to outcome.value.outcome),
                            statusMessage = "Recorded feedback (${outcome.value.outcome}) for $transactionId.",
                        )
                    }
                is PricingOutcome.Failure ->
                    _workspaceState.update { it.copy(isLoading = false, errorMessage = outcome.error.message) }
            }
        }
    }

    fun loadMyProfile() {
        _profileState.value = ProfileUiState.Loading
        viewModelScope.launch {
            when (val outcome = repository.fetchMyProfile()) {
                is PricingOutcome.Success -> {
                    val profile = outcome.value
                    if (profile == null) {
                        _profileState.value = ProfileUiState.NeedsOnboarding
                    } else {
                        _profileState.value = ProfileUiState.Ready(profile)
                        updateForm {
                            it.copy(
                                mentorId = profile.profileId,
                                mentorCountry = it.mentorCountry.ifBlank { profile.countryCode.uppercase() },
                            )
                        }
                    }
                }
                is PricingOutcome.Failure -> {
                    _profileState.value = ProfileUiState.Error(outcome.error.message)
                }
            }
        }
    }

    fun saveMyProfile(
        fullName: String,
        email: String,
        countryCode: String,
    ) {
        val trimmedName = fullName.trim()
        val trimmedEmail = email.trim()
        val normalizedCountry = countryCode.trim().uppercase()
        if (trimmedName.isBlank() || trimmedEmail.isBlank() || !Regex("[A-Za-z]{2}").matches(normalizedCountry)) {
            _profileState.value = ProfileUiState.Error("Enter your name, email, and a 2-letter country code.")
            return
        }
        _profileState.value = ProfileUiState.Loading
        viewModelScope.launch {
            val payload =
                SelfProfileUpsertDTO(
                    fullName = trimmedName,
                    email = trimmedEmail,
                    countryCode = normalizedCountry,
                )
            when (val outcome = repository.upsertMyProfile(payload)) {
                is PricingOutcome.Success -> {
                    val profile = outcome.value
                    _profileState.value = ProfileUiState.Ready(profile)
                    updateForm {
                        it.copy(
                            mentorId = profile.profileId,
                            mentorCountry = profile.countryCode.uppercase(),
                        )
                    }
                }
                is PricingOutcome.Failure -> {
                    _profileState.value = ProfileUiState.Error(outcome.error.message)
                }
            }
        }
    }

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
        val validationMessage = form.validate()
        if (validationMessage != null) {
            _uiState.update { PricingUiState.Error(form.copy(validationError = validationMessage), validationMessage) }
            return
        }

        _workspaceState.update { it.copy(isQuoteDetailOpen = false) }
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
        val currentForm = _uiState.value.form
        val readyProfile = (_profileState.value as? ProfileUiState.Ready)?.profile
        val preservedMentorId = readyProfile?.profileId ?: currentForm.mentorId
        val preservedMentorCountry = readyProfile?.countryCode?.uppercase().orEmpty()
        _workspaceState.update {
            it.copy(
                quoteStep = 0,
                isQuoteDetailOpen = false,
                statusMessage = null,
                errorMessage = null,
            )
        }
        _uiState.update {
            PricingUiState.Idle(
                PricingFormState(
                    mentorId = preservedMentorId,
                    mentorCountry = preservedMentorCountry,
                ),
            )
        }
    }

    private fun constructQueryPayload(form: PricingFormState): PricingQueryDTO =
        PricingQueryDTO(
            mentorId = form.mentorId.trim(),
            listingId = form.listingId,
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
