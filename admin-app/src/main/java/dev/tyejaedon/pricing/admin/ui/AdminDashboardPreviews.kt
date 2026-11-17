package dev.tyejaedon.pricing.admin.ui

import android.content.res.Configuration
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.tooling.preview.Preview
import dev.tyejaedon.pricing.admin.data.network.dto.AdminProfileDTO
import dev.tyejaedon.pricing.admin.data.network.dto.ArtifactStatusDTO
import dev.tyejaedon.pricing.admin.data.network.dto.DriftSummaryDTO
import dev.tyejaedon.pricing.admin.data.network.dto.GridSearchConfigDTO
import dev.tyejaedon.pricing.admin.data.network.dto.HealthStatusDTO
import dev.tyejaedon.pricing.admin.data.network.dto.QuoteFeedbackRecordDTO
import dev.tyejaedon.pricing.admin.data.network.dto.RetrainResponseDTO
import dev.tyejaedon.pricing.admin.data.network.dto.TransactionAuditDTO
import dev.tyejaedon.pricing.admin.viewmodel.AdminDashboardUiState
import dev.tyejaedon.pricing.admin.viewmodel.AdminTab

private val previewBaseState =
    AdminDashboardUiState(
        health =
            HealthStatusDTO(
                status = "healthy",
                service = "price-optimization-api",
                unit = "KES/hour",
                modelsLoaded = true,
                version = "2.4.0",
            ),
        artifacts =
            ArtifactStatusDTO(
                modelsLoaded = true,
                artifactVersion = "v2026.11.01",
                datasetVersion = "mentors_2026_q4",
                sourceType = "gcs",
                validationStatus = "passed",
            ),
        tuning =
            GridSearchConfigDTO(
                kNeighbors = listOf(3, 5, 7, 10),
                textWeight = 0.65f,
                metadataWeight = 0.35f,
                allowFallback = true,
            ),
        retrainStatus =
            RetrainResponseDTO(
                jobId = "job_4812",
                status = "completed",
                artifactVersion = "v2026.11.01",
            ),
        drift =
            DriftSummaryDTO(
                totalTransactions = 142,
                byIndustry = mapOf("mobile" to 54, "data_ai" to 48, "web_backend" to 40),
                byCorridor = mapOf("KE->US" to 62, "KE->GB" to 38, "KE->KE" to 42),
                averageFinalRate = 2740f,
            ),
        feedback =
            listOf(
                QuoteFeedbackRecordDTO(
                    feedbackId = "fb_001",
                    transactionId = "tx_901",
                    outcome = "booked",
                    actualRate = 2550f,
                ),
                QuoteFeedbackRecordDTO(
                    feedbackId = "fb_002",
                    transactionId = "tx_902",
                    outcome = "adjusted",
                    actualRate = 2900f,
                ),
            ),
        profiles =
            listOf(
                AdminProfileDTO(
                    profileId = "mentor_001",
                    fullName = "Ada Lovelace",
                    email = "ada@strathmore.edu",
                    countryCode = "KE",
                ),
                AdminProfileDTO(
                    profileId = "mentor_002",
                    fullName = "Alan Turing",
                    email = "alan@strathmore.edu",
                    countryCode = "GB",
                ),
            ),
        history =
            listOf(
                TransactionAuditDTO(
                    transactionId = "tx_901",
                    selectedIndustry = "mobile",
                    finalQuotedRate = 2557f,
                ),
                TransactionAuditDTO(
                    transactionId = "tx_902",
                    selectedIndustry = "data_ai",
                    finalQuotedRate = 3075f,
                ),
            ),
    )

@Preview(name = "Overview - Light", showBackground = true)
@Composable
private fun AdminDashboardOverviewLightPreview() {
    MaterialTheme {
        AdminDashboardScreenContent(
            state = previewBaseState.copy(selectedTab = AdminTab.OVERVIEW),
        )
    }
}

@Preview(name = "Overview - Dark", uiMode = Configuration.UI_MODE_NIGHT_YES, showBackground = true)
@Composable
private fun AdminDashboardOverviewDarkPreview() {
    MaterialTheme(colorScheme = darkColorScheme()) {
        AdminDashboardScreenContent(
            state = previewBaseState.copy(selectedTab = AdminTab.OVERVIEW),
        )
    }
}

@Preview(name = "MLOps Tab", showBackground = true)
@Composable
private fun AdminDashboardMlopsPreview() {
    MaterialTheme {
        AdminDashboardScreenContent(
            state =
                previewBaseState.copy(
                    selectedTab = AdminTab.MLOPS,
                    statusMessage = "Tuning saved.",
                ),
        )
    }
}

@Preview(name = "Drift & Feedback Tab", showBackground = true)
@Composable
private fun AdminDashboardDriftPreview() {
    MaterialTheme {
        AdminDashboardScreenContent(
            state = previewBaseState.copy(selectedTab = AdminTab.DRIFT),
        )
    }
}

@Preview(name = "Profiles & Audit Tab", showBackground = true)
@Composable
private fun AdminDashboardProfilesPreview() {
    MaterialTheme {
        AdminDashboardScreenContent(
            state = previewBaseState.copy(selectedTab = AdminTab.PROFILES),
        )
    }
}
