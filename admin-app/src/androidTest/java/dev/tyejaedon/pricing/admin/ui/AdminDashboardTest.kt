package dev.tyejaedon.pricing.admin.ui

import androidx.compose.material3.MaterialTheme
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import dev.tyejaedon.pricing.admin.data.repository.FakeAdminRepository
import dev.tyejaedon.pricing.admin.viewmodel.AdminViewModel
import org.junit.Rule
import org.junit.Test

class AdminDashboardTest {
    @get:Rule
    val composeRule = createComposeRule()

    @Test
    fun dashboardLoadsOverviewAndNavigatesTabs() {
        val viewModel = AdminViewModel(FakeAdminRepository(simulatedLatencyMs = 0))
        composeRule.setContent {
            MaterialTheme {
                AdminDashboardScreen(viewModel = viewModel, demoMode = true)
            }
        }

        composeRule.waitUntil(timeoutMillis = 5_000) {
            composeRule.onAllNodesWithText("Status: HEALTHY").fetchSemanticsNodes().isNotEmpty()
        }
        composeRule.onNodeWithText("Version: v1:ab12cd34ef56").assertExists()

        composeRule.onNodeWithText("MLOps").performClick()
        composeRule.onNodeWithText("Trigger Retrain").assertExists()

        composeRule.onNodeWithText("Drift & Feedback").performClick()
        composeRule.onNodeWithText("Total Transactions: 42").assertExists()

        composeRule.onNodeWithText("Profiles & Audit").performClick()
        composeRule.onNodeWithText("Seed Platform Mentors").assertExists()
    }
}
