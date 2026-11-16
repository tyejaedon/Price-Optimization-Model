package dev.tyejaedon.pricing.admin.viewmodel

import dev.tyejaedon.pricing.admin.data.network.dto.AdminProfileDTO
import dev.tyejaedon.pricing.admin.data.network.dto.ArtifactStatusDTO
import dev.tyejaedon.pricing.admin.data.network.dto.DriftSummaryDTO
import dev.tyejaedon.pricing.admin.data.network.dto.GridSearchConfigDTO
import dev.tyejaedon.pricing.admin.data.network.dto.HealthStatusDTO
import dev.tyejaedon.pricing.admin.data.network.dto.MetricsResponseDTO
import dev.tyejaedon.pricing.admin.data.network.dto.QuoteFeedbackRecordDTO
import dev.tyejaedon.pricing.admin.data.network.dto.RetrainResponseDTO
import dev.tyejaedon.pricing.admin.data.network.dto.TransactionAuditDTO

sealed interface AdminSessionState {
    data object Locked : AdminSessionState

    data object Unlocking : AdminSessionState

    data object Unlocked : AdminSessionState

    data class Error(
        val message: String,
    ) : AdminSessionState
}

enum class AdminTab(
    val label: String,
) {
    OVERVIEW("Overview"),
    MLOPS("MLOps"),
    DRIFT("Drift & Feedback"),
    PROFILES("Profiles & Audit"),
}

data class AdminDashboardUiState(
    val isLoading: Boolean = false,
    val selectedTab: AdminTab = AdminTab.OVERVIEW,
    val health: HealthStatusDTO? = null,
    val metrics: MetricsResponseDTO? = null,
    val artifacts: ArtifactStatusDTO? = null,
    val tuning: GridSearchConfigDTO = GridSearchConfigDTO(),
    val retrainStatus: RetrainResponseDTO? = null,
    val drift: DriftSummaryDTO? = null,
    val feedback: List<QuoteFeedbackRecordDTO> = emptyList(),
    val profiles: List<AdminProfileDTO> = emptyList(),
    val history: List<TransactionAuditDTO> = emptyList(),
    val statusMessage: String? = null,
    val errorMessage: String? = null,
)
