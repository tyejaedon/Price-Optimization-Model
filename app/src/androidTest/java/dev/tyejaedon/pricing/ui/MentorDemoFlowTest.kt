package dev.tyejaedon.pricing.ui

import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performTextInput
import dev.tyejaedon.pricing.data.repository.FakePricingRepository
import dev.tyejaedon.pricing.ui.pricing.PricingScreen
import dev.tyejaedon.pricing.ui.theme.PricingTheme
import dev.tyejaedon.pricing.viewmodel.PricingViewModel
import org.junit.Rule
import org.junit.Test

class MentorDemoFlowTest {
    @get:Rule
    val composeRule = createComposeRule()

    @Test
    fun mentorDemoFlowNavigatesQuoteListingsAndHistory() {
        val viewModel = PricingViewModel(FakePricingRepository(simulatedLatencyMs = 0))
        composeRule.setContent {
            PricingTheme {
                PricingScreen(viewModel = viewModel, demoMode = true)
            }
        }

        // 1. Quote Tab: fill form, select industry & countries, calculate rate
        composeRule.onNodeWithContentDescription("Service description input")
            .performTextInput("Senior Android Jetpack Compose architecture and mentoring session")
        composeRule.onNodeWithContentDescription("Industry selector, currently ")
            .performClick()
        composeRule.onNodeWithText("Mobile Development").performClick()

        composeRule.onNodeWithContentDescription("Your country ISO 2-letter code")
            .performClick()
        composeRule.onAllNodesWithText("Kenya (KE)")[0].performClick()

        composeRule.onNodeWithContentDescription("Client country ISO 2-letter code")
            .performClick()
        composeRule.onAllNodesWithText("United States (US)")[0].performClick()

        composeRule.onNodeWithContentDescription("Calculate recommended hourly rate")
            .performScrollTo()
            .performClick()

        composeRule.waitUntil(timeoutMillis = 5_000) {
            composeRule.onAllNodesWithText("Recommended rate").fetchSemanticsNodes().isNotEmpty()
        }

        // 2. Listings Tab: verify demo listing and apply to quote
        composeRule.onNodeWithText("Listings").performClick()
        composeRule.onNodeWithText("Android & Kotlin Architecture Mentoring").assertExists()

        // 3. History Tab: verify past quote and submit feedback
        composeRule.onNodeWithText("History").performClick()
        composeRule.onNodeWithText("Accepted").performClick()
        composeRule.waitUntil(timeoutMillis = 5_000) {
            composeRule.onAllNodesWithText("Feedback recorded: accepted").fetchSemanticsNodes().isNotEmpty()
        }
    }
}
