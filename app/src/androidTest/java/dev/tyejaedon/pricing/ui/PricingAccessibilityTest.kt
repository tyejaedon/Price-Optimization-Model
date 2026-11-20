package dev.tyejaedon.pricing.ui

import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.test.hasClickAction
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.unit.Density
import dev.tyejaedon.pricing.data.repository.FakePricingRepository
import dev.tyejaedon.pricing.ui.pricing.PricingScreen
import dev.tyejaedon.pricing.ui.theme.MinTouchTarget
import dev.tyejaedon.pricing.ui.theme.PricingTheme
import dev.tyejaedon.pricing.viewmodel.PricingViewModel
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test

class PricingAccessibilityTest {
    @get:Rule
    val composeRule = createComposeRule()

    @Test
    fun pricingControlsHaveAccessibleNamesAndActionTargets() {
        val viewModel = PricingViewModel(FakePricingRepository(simulatedLatencyMs = 0))
        composeRule.setContent {
            PricingTheme {
                PricingScreen(viewModel = viewModel)
            }
        }

        // Step 1
        listOf(
            "Service description input",
            "Industry selector, currently ",
            "Continue to next step",
        ).forEach { composeRule.onNodeWithContentDescription(it).assertExists() }

        // Step 2
        composeRule.runOnIdle { viewModel.setQuoteStep(1) }
        composeRule.waitForIdle()
        listOf(
            "Your country ISO 2-letter code",
            "Client country ISO 2-letter code",
            "Back to previous step",
        ).forEach { composeRule.onNodeWithContentDescription(it).assertExists() }

        // Step 3
        composeRule.runOnIdle { viewModel.setQuoteStep(2) }
        composeRule.waitForIdle()
        listOf(
            "Niche competitiveness slider, 50 percent",
            "Calculate recommended hourly rate",
        ).forEach { composeRule.onNodeWithContentDescription(it).assertExists() }

        val interactiveNodes =
            composeRule
                .onAllNodes(hasClickAction(), useUnmergedTree = false)
                .fetchSemanticsNodes()
        assertTrue(interactiveNodes.isNotEmpty())
        interactiveNodes.forEach { node ->
            val labels =
                if (node.config.contains(SemanticsProperties.ContentDescription)) {
                    node.config[SemanticsProperties.ContentDescription]
                } else {
                    emptyList()
                }
            val text =
                if (node.config.contains(SemanticsProperties.Text)) {
                    node.config[SemanticsProperties.Text]
                } else {
                    emptyList()
                }
            val accessibleName = labels.joinToString() + text.joinToString { it.text }
            assertTrue(accessibleName.isNotBlank())
        }
    }

    @Test
    fun pricingShellRendersAtDoubleSystemFontScale() {
        composeRule.setContent {
            val density = LocalDensity.current
            CompositionLocalProvider(LocalDensity provides Density(density.density, fontScale = 2f)) {
                PricingTheme {
                    PricingScreen(viewModel = PricingViewModel(FakePricingRepository(simulatedLatencyMs = 0)))
                }
            }
        }

        composeRule.onNodeWithContentDescription("Service description input").assertExists()
        composeRule.onNodeWithContentDescription("Continue to next step").assertExists()
    }

    @Test
    fun primaryActionMeetsMinimumTouchTarget() {
        composeRule.setContent {
            PricingTheme {
                PricingScreen(viewModel = PricingViewModel(FakePricingRepository(simulatedLatencyMs = 0)))
            }
        }

        val target = composeRule.onNodeWithContentDescription("Continue to next step").fetchSemanticsNode()
        val minimumHeightPx = with(composeRule.density) { MinTouchTarget.toPx() }
        assertTrue(target.boundsInRoot.height >= minimumHeightPx)
    }
}
