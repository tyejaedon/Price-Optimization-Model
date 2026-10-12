package edu.strathmore.pricing.ui

import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.test.hasClickAction
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.unit.Density
import edu.strathmore.pricing.data.repository.FakePricingRepository
import edu.strathmore.pricing.ui.pricing.PricingScreen
import edu.strathmore.pricing.ui.theme.MinTouchTarget
import edu.strathmore.pricing.ui.theme.PricingTheme
import edu.strathmore.pricing.viewmodel.PricingViewModel
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test

class PricingAccessibilityTest {
    @get:Rule
    val composeRule = createComposeRule()

    @Test
    fun pricingControlsHaveAccessibleNamesAndActionTargets() {
        composeRule.setContent {
            PricingTheme {
                PricingScreen(viewModel = PricingViewModel(FakePricingRepository(simulatedLatencyMs = 0)))
            }
        }

        val descriptions =
            listOf(
                "Service description input",
                "Industry selector, currently ",
                "Your country ISO 2-letter code",
                "Client country ISO 2-letter code",
                "Niche competitiveness slider, 50 percent",
                "Calculate recommended hourly rate",
            )
        descriptions.forEach { description ->
            composeRule.onNodeWithContentDescription(description).assertExists()
        }

        val interactiveNodes =
            composeRule
                .onAllNodes(hasClickAction(), useUnmergedTree = true)
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
        composeRule.onNodeWithContentDescription("Calculate recommended hourly rate").assertExists()
    }

    @Test
    fun primaryActionMeetsMinimumTouchTarget() {
        composeRule.setContent {
            PricingTheme {
                PricingScreen(viewModel = PricingViewModel(FakePricingRepository(simulatedLatencyMs = 0)))
            }
        }

        val target = composeRule.onNodeWithContentDescription("Calculate recommended hourly rate").fetchSemanticsNode()
        val minimumHeightPx = with(composeRule.density) { MinTouchTarget.toPx() }
        assertTrue(target.boundsInRoot.height >= minimumHeightPx)
    }
}
