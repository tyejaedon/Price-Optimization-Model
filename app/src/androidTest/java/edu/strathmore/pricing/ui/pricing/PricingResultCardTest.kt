package edu.strathmore.pricing.ui.pricing

import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import edu.strathmore.pricing.data.network.dto.PeerMatchDTO
import edu.strathmore.pricing.data.network.dto.PredictionResultDTO
import edu.strathmore.pricing.data.network.dto.PricingQueryDTO
import edu.strathmore.pricing.domain.IPricingRepository
import edu.strathmore.pricing.domain.PricingFailure
import edu.strathmore.pricing.domain.PricingOutcome
import edu.strathmore.pricing.ui.pricing.components.PricingResultCard
import edu.strathmore.pricing.ui.theme.PricingTheme
import edu.strathmore.pricing.viewmodel.PricingViewModel
import kotlinx.coroutines.CompletableDeferred
import org.junit.Rule
import org.junit.Test

class PricingResultCardTest {
    @get:Rule
    val composeRule = createComposeRule()

    @Test
    fun pricingScreenTransitionsFromIdleThroughLoadingToSuccess() {
        val repository = PendingPricingRepository()
        val viewModel = PricingViewModel(repository)
        composeRule.setContent {
            PricingTheme {
                PricingScreen(viewModel = viewModel)
            }
        }

        composeRule.onNodeWithText("Price your service").assertExists()
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

        composeRule.onNodeWithText("Confidence (uncalibrated)").assertExists()
        composeRule.onNodeWithText("M-Pesa transfer fee").assertExists()
        composeRule.onNodeWithText("Listing ID: listing-01").assertExists()
        composeRule.onNodeWithText("Similarity: 92%").assertExists()
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
    fun resultCardExplainsEmptyComparablesWithoutInventingPeers() {
        composeRule.setContent {
            PricingTheme {
                PricingResultCard(result = resultWithPeers.copy(comparables = emptyList()))
            }
        }

        composeRule.onNodeWithText("No listing-backed comparables are available for this quote yet.").assertExists()
        composeRule.onNodeWithText("listing-01").assertDoesNotExist()
    }

    @Test
    fun resultCardShowsAllProvenanceForPartialComparableResults() {
        composeRule.setContent {
            PricingTheme {
                PricingResultCard(result = resultWithPeers)
            }
        }

        composeRule.onNodeWithText("Showing 1 of 5 indexed peers; some listings lack public provenance.").assertExists()
        composeRule.onNodeWithText("Senior Android Architect").assertExists()
        composeRule.onNodeWithText("Listing ID: listing-01").assertExists()
        composeRule.onNodeWithText("2,600 KES/hour").assertExists()
        composeRule.onNodeWithText("Similarity: 92%").assertExists()
    }

    private fun makeFormValid(viewModel: PricingViewModel) {
        composeRule.runOnIdle {
            viewModel.onDescriptionChanged("Native Android application development")
            viewModel.onIndustrySelected("mobile")
            viewModel.onMentorCountrySelected("KE")
            viewModel.onClientCountrySelected("US")
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
        val resultWithPeers =
            PredictionResultDTO(
                basePredictedRate = 2_500f,
                mpesaTariffSurcharge = 57f,
                finalQuotedRate = 2_557f,
                minQuotedRate = 2_125f,
                maxQuotedRate = 3_375f,
                kNeighborsUsed = 5,
                bilateralArbitrageFactor = 1f,
                confidenceScore = 0f,
                comparables =
                    listOf(
                        PeerMatchDTO(
                            listingId = "listing-01",
                            jobTitle = "Senior Android Architect",
                            verifiedRate = 2_600f,
                            similarityScore = 0.92f,
                            euclideanDistance = 0.41f,
                        ),
                    ),
                reason = "Weighted from indexed peers.",
                timestamp = "2026-10-10T00:00:00Z",
            )
    }
}
