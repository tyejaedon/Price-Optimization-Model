package dev.tyejaedon.pricing.ui.pricing

import android.content.res.Configuration
import androidx.compose.runtime.Composable
import androidx.compose.ui.tooling.preview.Preview
import dev.tyejaedon.pricing.data.network.dto.PeerMatchDTO
import dev.tyejaedon.pricing.data.network.dto.PredictionResultDTO
import dev.tyejaedon.pricing.data.network.dto.QuoteHistoryItemDTO
import dev.tyejaedon.pricing.data.network.dto.SelfListingDTO
import dev.tyejaedon.pricing.data.network.dto.SelfProfileDTO
import dev.tyejaedon.pricing.ui.theme.PricingTheme
import dev.tyejaedon.pricing.viewmodel.MentorTab
import dev.tyejaedon.pricing.viewmodel.MentorWorkspaceState
import dev.tyejaedon.pricing.viewmodel.PricingFormState
import dev.tyejaedon.pricing.viewmodel.PricingUiState
import dev.tyejaedon.pricing.viewmodel.ProfileUiState

private val previewForm =
    PricingFormState(
        rawDescription = "Senior Android & Kotlin Multiplatform mentorship and architecture reviews",
        mentorId = "mentor_001",
        selectedIndustry = "mobile",
        mentorCountry = "KE",
        clientCountry = "US",
        competitivenessScore = 0.65f,
        baseRateFloor = "2000",
    )

private val previewResult =
    PredictionResultDTO(
        basePredictedRate = 2500f,
        mpesaTariffSurcharge = 57f,
        finalQuotedRate = 2557f,
        minQuotedRate = 2125f,
        maxQuotedRate = 3375f,
        kNeighborsUsed = 5,
        bilateralArbitrageFactor = 1.0f,
        confidenceScore = 0.89f,
        comparables =
            listOf(
                PeerMatchDTO("list_001", "Senior Android Architect", 2600f, 0.92f, 0.41f),
                PeerMatchDTO("list_045", "Kotlin Mentor", 2400f, 0.88f, 0.55f),
            ),
        reason = "Weighted from 5 indexed peers in KES/hour; corridor excludes the M-Pesa surcharge.",
        timestamp = "2026-10-10T00:00:00Z",
    )

private val previewReadyProfile =
    ProfileUiState.Ready(
        SelfProfileDTO(
            profileId = "mentor_001",
            fullName = "Ada Lovelace",
            email = "ada@strathmore.edu",
            countryCode = "KE",
        ),
    )

private val previewListings =
    listOf(
        SelfListingDTO(
            listingId = "list_101",
            mentorId = "mentor_001",
            industryId = "mobile",
            title = "Jetpack Compose Architecture Review",
            rawText = "Hands-on code review and state-management guidance for Compose apps.",
            verifiedRate = 2800f,
        ),
        SelfListingDTO(
            listingId = "list_102",
            mentorId = "mentor_001",
            industryId = "data_ai",
            title = "ML Model Serving Workshop",
            rawText = "FastAPI inference deployment and latency optimization for Python models.",
            verifiedRate = 3200f,
        ),
    )

private val previewHistory =
    listOf(
        QuoteHistoryItemDTO(
            transactionId = "tx_901",
            selectedIndustry = "mobile",
            mentorCountryCode = "KE",
            clientCountryCode = "US",
            basePredictedRate = 2500f,
            mpesaTariffSurcharge = 57f,
            finalQuotedRate = 2557f,
            executedAt = "2026-11-10T14:22:00Z",
        ),
        QuoteHistoryItemDTO(
            transactionId = "tx_902",
            selectedIndustry = "data_ai",
            mentorCountryCode = "KE",
            clientCountryCode = "GB",
            basePredictedRate = 3000f,
            mpesaTariffSurcharge = 75f,
            finalQuotedRate = 3075f,
            executedAt = "2026-11-12T09:15:00Z",
        ),
    )

@Preview(name = "Quote Idle - Light", showBackground = true)
@Composable
private fun PricingScreenQuoteIdleLightPreview() {
    PricingTheme(darkTheme = false) {
        PricingScreenContent(
            uiState = PricingUiState.Idle(previewForm),
            profileState = previewReadyProfile,
            workspaceState = MentorWorkspaceState(selectedTab = MentorTab.QUOTE),
        )
    }
}

@Preview(name = "Quote Success - Dark", uiMode = Configuration.UI_MODE_NIGHT_YES, showBackground = true)
@Composable
private fun PricingScreenQuoteSuccessDarkPreview() {
    PricingTheme(darkTheme = true) {
        PricingScreenContent(
            uiState = PricingUiState.Success(previewForm, previewResult),
            profileState = previewReadyProfile,
            workspaceState = MentorWorkspaceState(selectedTab = MentorTab.QUOTE),
        )
    }
}

@Preview(name = "Quote Loading", showBackground = true)
@Composable
private fun PricingScreenQuoteLoadingPreview() {
    PricingTheme(darkTheme = false) {
        PricingScreenContent(
            uiState = PricingUiState.Loading(previewForm),
            profileState = previewReadyProfile,
            workspaceState = MentorWorkspaceState(selectedTab = MentorTab.QUOTE, modelsLoaded = false),
        )
    }
}

@Preview(name = "Quote Error", showBackground = true)
@Composable
private fun PricingScreenQuoteErrorPreview() {
    PricingTheme(darkTheme = false) {
        PricingScreenContent(
            uiState = PricingUiState.Error(previewForm, "Unable to reach pricing API. Check your connection."),
            profileState = previewReadyProfile,
            workspaceState = MentorWorkspaceState(selectedTab = MentorTab.QUOTE),
        )
    }
}

@Preview(name = "Onboarding", showBackground = true)
@Composable
private fun PricingScreenOnboardingPreview() {
    PricingTheme(darkTheme = false) {
        PricingScreenContent(
            uiState = PricingUiState.Idle(),
            profileState = ProfileUiState.NeedsOnboarding,
            autoLoadProfile = true,
            userEmail = "mentor@strathmore.edu",
        )
    }
}

@Preview(name = "Listings Tab", showBackground = true)
@Composable
private fun PricingScreenListingsTabPreview() {
    PricingTheme(darkTheme = false) {
        PricingScreenContent(
            uiState = PricingUiState.Idle(previewForm),
            profileState = previewReadyProfile,
            workspaceState =
                MentorWorkspaceState(
                    selectedTab = MentorTab.LISTINGS,
                    listings = previewListings,
                ),
        )
    }
}

@Preview(name = "History Tab", showBackground = true)
@Composable
private fun PricingScreenHistoryTabPreview() {
    PricingTheme(darkTheme = false) {
        PricingScreenContent(
            uiState = PricingUiState.Idle(previewForm),
            profileState = previewReadyProfile,
            workspaceState =
                MentorWorkspaceState(
                    selectedTab = MentorTab.HISTORY,
                    history = previewHistory,
                    feedbackStatusByTx = mapOf("tx_902" to "booked"),
                ),
        )
    }
}
