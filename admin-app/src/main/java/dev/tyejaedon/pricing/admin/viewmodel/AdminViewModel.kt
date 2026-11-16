package dev.tyejaedon.pricing.admin.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dev.tyejaedon.pricing.admin.data.network.dto.GridSearchConfigDTO
import dev.tyejaedon.pricing.admin.domain.AdminOutcome
import dev.tyejaedon.pricing.admin.domain.IAdminRepository
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

class AdminViewModel(
    private val repository: IAdminRepository,
) : ViewModel() {
    private val _sessionState = MutableStateFlow<AdminSessionState>(AdminSessionState.Locked)
    val sessionState: StateFlow<AdminSessionState> = _sessionState.asStateFlow()

    private val _dashboardState = MutableStateFlow(AdminDashboardUiState())
    val dashboardState: StateFlow<AdminDashboardUiState> = _dashboardState.asStateFlow()

    fun unlock(token: String) {
        if (token.isBlank()) {
            _sessionState.value = AdminSessionState.Error("Enter an administrator token.")
            return
        }
        _sessionState.value = AdminSessionState.Unlocking
        repository.setAdminToken(token)
        viewModelScope.launch {
            when (val outcome = repository.fetchMetrics()) {
                is AdminOutcome.Success -> {
                    _sessionState.value = AdminSessionState.Unlocked
                    _dashboardState.update {
                        it.copy(metrics = outcome.value, tuning = outcome.value.tuning, errorMessage = null)
                    }
                    refreshAll()
                }
                is AdminOutcome.Failure -> {
                    repository.clearAdminToken()
                    _sessionState.value = AdminSessionState.Error(outcome.error.message)
                }
            }
        }
    }

    fun lock() {
        repository.clearAdminToken()
        _sessionState.value = AdminSessionState.Locked
        _dashboardState.value = AdminDashboardUiState()
    }

    fun selectTab(tab: AdminTab) {
        _dashboardState.update { it.copy(selectedTab = tab) }
    }

    fun refreshAll() {
        _dashboardState.update { it.copy(isLoading = true, errorMessage = null) }
        viewModelScope.launch {
            val healthDef = async { repository.fetchHealth() }
            val metricsDef = async { repository.fetchMetrics() }
            val artifactsDef = async { repository.fetchArtifacts() }
            val driftDef = async { repository.fetchDrift() }
            val feedbackDef = async { repository.listFeedback() }
            val profilesDef = async { repository.listProfiles() }
            val historyDef = async { repository.listHistory() }

            val health = (healthDef.await() as? AdminOutcome.Success)?.value
            val metricsOutcome = metricsDef.await()
            val artifacts = (artifactsDef.await() as? AdminOutcome.Success)?.value
            val drift = (driftDef.await() as? AdminOutcome.Success)?.value
            val feedback = (feedbackDef.await() as? AdminOutcome.Success)?.value.orEmpty()
            val profiles = (profilesDef.await() as? AdminOutcome.Success)?.value.orEmpty()
            val history = (historyDef.await() as? AdminOutcome.Success)?.value.orEmpty()

            val firstError = (metricsOutcome as? AdminOutcome.Failure)?.error?.message
            _dashboardState.update { current ->
                current.copy(
                    isLoading = false,
                    health = health,
                    metrics = (metricsOutcome as? AdminOutcome.Success)?.value ?: current.metrics,
                    tuning = (metricsOutcome as? AdminOutcome.Success)?.value?.tuning ?: current.tuning,
                    artifacts = artifacts,
                    drift = drift,
                    feedback = feedback,
                    profiles = profiles,
                    history = history,
                    errorMessage = firstError,
                )
            }
        }
    }

    fun updateTuning(config: GridSearchConfigDTO) {
        _dashboardState.update { it.copy(isLoading = true, statusMessage = null, errorMessage = null) }
        viewModelScope.launch {
            when (val outcome = repository.updateGridSearch(config)) {
                is AdminOutcome.Success ->
                    _dashboardState.update {
                        it.copy(isLoading = false, tuning = outcome.value, statusMessage = "Grid-search config saved.")
                    }
                is AdminOutcome.Failure ->
                    _dashboardState.update { it.copy(isLoading = false, errorMessage = outcome.error.message) }
            }
        }
    }

    fun triggerRetrain() {
        _dashboardState.update { it.copy(isLoading = true, statusMessage = null, errorMessage = null) }
        viewModelScope.launch {
            when (val outcome = repository.triggerRetrain()) {
                is AdminOutcome.Success ->
                    _dashboardState.update {
                        it.copy(
                            isLoading = false,
                            retrainStatus = outcome.value,
                            statusMessage = "Retrain job ${outcome.value.jobId}: ${outcome.value.status}",
                        )
                    }
                is AdminOutcome.Failure ->
                    _dashboardState.update { it.copy(isLoading = false, errorMessage = outcome.error.message) }
            }
        }
    }

    fun pollRetrainStatus() {
        val jobId = _dashboardState.value.retrainStatus?.jobId ?: return
        viewModelScope.launch {
            when (val outcome = repository.fetchRetrainStatus(jobId)) {
                is AdminOutcome.Success ->
                    _dashboardState.update {
                        it.copy(
                            retrainStatus = outcome.value,
                            statusMessage = "Job ${outcome.value.jobId}: ${outcome.value.status}",
                        )
                    }
                is AdminOutcome.Failure ->
                    _dashboardState.update { it.copy(errorMessage = outcome.error.message) }
            }
        }
    }

    fun seedPlatformMentors() {
        _dashboardState.update { it.copy(isLoading = true, statusMessage = null, errorMessage = null) }
        viewModelScope.launch {
            when (val outcome = repository.seedPlatformMentors()) {
                is AdminOutcome.Success -> {
                    _dashboardState.update { it.copy(isLoading = false, statusMessage = "Platform mentors seeded.") }
                    refreshAll()
                }
                is AdminOutcome.Failure ->
                    _dashboardState.update { it.copy(isLoading = false, errorMessage = outcome.error.message) }
            }
        }
    }
}
