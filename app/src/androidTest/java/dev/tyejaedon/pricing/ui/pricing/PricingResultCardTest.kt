package dev.tyejaedon.pricing.ui.pricing

import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import dev.tyejaedon.pricing.data.network.dto.PeerMatchDTO
import dev.tyejaedon.pricing.data.network.dto.PredictionResultDTO
import dev.tyejaedon.pricing.data.network.dto.PricingQueryDTO
import dev.tyejaedon.pricing.data.network.dto.QuoteExplanationDTO
import dev.tyejaedon.pricing.domain.IPricingRepository
import dev.tyejaedon.pricing.domain.PricingFailure
import dev.tyejaedon.pricing.domain.PricingOutcome
import dev.tyejaedon.pricing.ui.pricing.components.PricingResultCard
import dev.tyejaedon.pricing.ui.theme.PricingTheme
import dev.tyejaedon.pricing.viewmodel.PricingFormState
import dev.tyejaedon.pricing.viewmodel.PricingViewModel
import kotlinx.coroutines.CompletableDeferred
import org.junit.Rule
import org.junit.Test

class PricingResultCardTest {
    @get:Rule
    val composeRule = createComposeRule()

    @Test
    fun pricingScreenTransitionsFromIdleThroughLoadingToSuccessAndDetailScreen() {
        val repository = PendingPricingRepository()
        val viewModel = PricingViewModel(repository)
        composeRule.setContent {
            PricingTheme {
                PricingScreen(viewModel = viewModel)
            }
        }

        composeRule.onNodeWithText("Describe your service").assertExists()
        composeRule.onNodeWithText("Recommended rate").assertDoesNotExist()
        makeFormValid(viewModel)

        composeRule.onNodeWithContentDescription("Calculate recommended hourly rate").performClick()
        composeRule.onNodeWithContentDescription("Finding peer-matched rates").assertExists()
        composeRule.runOnIdle {
            repository.response.complete(PricingOutcome.Success(resultWithPeers))
        }
        composeRule.waitUntil(timeoutMillis = 5_000) {
            composeRule.onAllNodesWithText("Recommended rate").fetchSemanticsNodes().isNotEmpty()
        }

        // Compact summary card keeps the Quote tab uncluttered
        composeRule.onNodeWithText("5 peers • 92% match").assertExists()
        composeRule.onNodeWithText("You net 2,500 KES + 57 KES M-Pesa fee").assertExists()
        composeRule.onNodeWithText("Confidence (uncalibrated)").assertDoesNotExist()
        composeRule.onNodeWithContentDescription("Save quoted service to catalog").assertExists()

        // Tapping opens the full Quote Breakdown detail screen
        composeRule.onNodeWithContentDescription("Open full quote breakdown").performClick()
        composeRule.waitUntil(timeoutMillis = 5_000) {
            composeRule.onAllNodesWithText("Quote Breakdown").fetchSemanticsNodes().isNotEmpty()
        }

        composeRule.onNodeWithText("M-Pesa transfer pass-through").assertExists()
        composeRule.onNodeWithText("kotlin").performScrollTo().assertExists()
        composeRule.onNodeWithText("62% quote weight").performScrollTo().assertExists()
        composeRule.onNodeWithText("Similarity: 92%").performScrollTo().assertExists()
        composeRule.onNodeWithText("Confidence (uncalibrated)").performScrollTo().assertExists()
        composeRule.onNodeWithContentDescription("Share client quote proposal").performScrollTo().assertExists()

        // Tapping Glossary opens the plain-language technical terms sheet
        composeRule.onNodeWithText("New to these pricing terms?").performScrollTo().performClick()
        composeRule.waitUntil(timeoutMillis = 5_000) {
            composeRule.onAllNodesWithText("Pricing Glossary").fetchSemanticsNodes().isNotEmpty()
        }
        composeRule
            .onNodeWithText("IDW Quote Weight (Inverse Distance Weighting)")
            .performScrollTo()
            .assertExists()
        composeRule.onNodeWithContentDescription("Close pricing glossary").performClick()

        // Navigating back returns to the Quote tab
        composeRule.onNodeWithContentDescription("Back to quote").performClick()
        composeRule.waitUntil(timeoutMillis = 5_000) {
            composeRule.onAllNodesWithText("Recommended rate").fetchSemanticsNodes().isNotEmpty()
        }
    }

    @Test
    fun pricingScreenShowsRecoverableError() {
        val viewModel =
            PricingViewModel(
                ImmediatePricingRepository(PricingOutcome.Failure(PricingFailure.Network)),
            )
        composeRule.setContent {
            PricingTheme {
                PricingScreen(viewModel = viewModel)
            }
        }
        makeFormValid(viewModel)

        composeRule.onNodeWithContentDescription("Calculate recommended hourly rate").performClick()
        composeRule.waitUntil(timeoutMillis = 5_000) {
            composeRule.onAllNodesWithText(PricingFailure.Network.message).fetchSemanticsNodes().isNotEmpty()
        }

        composeRule.onNodeWithContentDescription("Retry calculation").assertExists()
    }

    @Test
    fun resultCardAndDetailScreenExplainEmptyComparablesWithoutInventingPeers() {
        composeRule.setContent {
            PricingTheme {
                QuoteDetailScreen(
                    result = resultWithPeers.copy(comparables = emptyList()),
                    form = sampleForm,
                    onBack = {},
                )
            }
        }

        composeRule
            .onNodeWithText("No listing-backed comparables are available for this quote yet.")
            .performScrollTo()
            .assertExists()
        composeRule.onNodeWithText("listing-01").assertDoesNotExist()
    }

    @Test
    fun detailScreenShowsAllProvenanceForPartialComparableResults() {
        composeRule.setContent {
            PricingTheme {
                QuoteDetailScreen(
                    result = resultWithPeers,
                    form = sampleForm,
                    onBack = {},
                )
            }
        }

        composeRule
            .onNodeWithText("Showing 1 of 5 indexed peers; some listings lack public provenance.")
            .performScrollTo()
            .assertExists()
        composeRule.onNodeWithText("Senior Android Architect").performScrollTo().assertExists()
        composeRule.onNodeWithText("2,600 KES/hour").performScrollTo().assertExists()
        composeRule.onNodeWithText("62% quote weight").performScrollTo().assertExists()
        composeRule.onNodeWithText("Similarity: 92%").performScrollTo().assertExists()
    }

    @Test
    fun summaryCardRendersFallbackAndFloorBadgesCleanly() {
        composeRule.setContent {
            PricingTheme {
                PricingResultCard(
                    result =
                        resultWithPeers.copy(
                            explanation =
                                QuoteExplanationDTO(
                                    requestedPartition = "mobile",
                                    routedPartition = "general_tech",
                                    usedFallbackPartition = true,
                                    floorExceedsBase = true,
                                ),
                        ),
                    onOpenDetails = {},
                )
            }
        }

        composeRule.onNodeWithText("Your floor is above market median").assertExists()
        composeRule.onNodeWithText("View full breakdown & 1 peers").assertExists()
    }

    private fun makeFormValid(viewModel: PricingViewModel) {
        composeRule.runOnIdle {
            viewModel.onDescriptionChanged("Native Android application development")
            viewModel.onMentorIdChanged("mentor-01")
            viewModel.onIndustrySelected("mobile")
            viewModel.onMentorCountrySelected("KE")
            viewModel.onClientCountrySelected("US")
            viewModel.setQuoteStep(2)
        }
        composeRule.waitForIdle()
    }

    private class PendingPricingRepository : IPricingRepository {
        val response = CompletableDeferred<PricingOutcome<PredictionResultDTO>>()

        override suspend fun calculateOptimalRate(query: PricingQueryDTO) = response.await()
    }

    private class ImmediatePricingRepository(
        private val outcome: PricingOutcome<PredictionResultDTO>,
    ) : IPricingRepository {
        override suspend fun calculateOptimalRate(query: PricingQueryDTO) = outcome
    }

    private companion object {
        val sampleForm =
            PricingFormState(
                rawDescription = "Native Android application development",
                mentorId = "mentor-01",
                selectedIndustry = "mobile",
                mentorCountry = "KE",
                clientCountry = "US",
            )

        val resultWithPeers =
            PredictionResultDTO(
                basePredictedRate = 2_500f,
                mpesaTariffSurcharge = 57f,
                finalQuotedRate = 2_557f,
                minQuotedRate = 2_125f,
                maxQuotedRate = 3_375f,
                kNeighborsUsed = 5,
                bilateralArbitrageFactor = 0.51f,
                confidenceScore = 0f,
                comparables =
                    listOf(
                        PeerMatchDTO(
                            listingId = "listing-01",
                            jobTitle = "Senior Android Architect",
                            verifiedRate = 2_600f,
                            similarityScore = 0.92f,
                            euclideanDistance = 0.41f,
                            idwWeight = 0.62f,
                        ),
                    ),
                reason = "Weighted from indexed peers.",
                explanation =
                    QuoteExplanationDTO(
                        requestedPartition = "mobile",
                        routedPartition = "mobile",
                        peerRateStddev = 240f,
                        corridorUpliftMultiplier = 1.49f,
                        topMatchedTerms = listOf("android", "kotlin"),
                    ),
                timestamp = "2026-10-10T00:00:00Z",
            )
    }
}
