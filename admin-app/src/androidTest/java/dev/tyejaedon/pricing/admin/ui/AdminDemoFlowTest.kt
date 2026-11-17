package dev.tyejaedon.pricing.admin.ui

import androidx.compose.material3.MaterialTheme
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performTextInput
import dev.tyejaedon.pricing.admin.data.repository.FakeAdminRepository
import dev.tyejaedon.pricing.admin.viewmodel.AdminViewModel
import org.junit.Rule
import org.junit.Test

class AdminDemoFlowTest {
    @get:Rule
    val composeRule = createComposeRule()

    @Test
    fun adminDemoFlowExercisesAllTabs() {
        val viewModel = AdminViewModel(FakeAdminRepository(simulatedLatencyMs = 0))
        composeRule.setContent {
            MaterialTheme {
                AdminDashboardScreen(viewModel = viewModel, demoMode = true)
            }
        }

        // 1. Overview
        composeRule.waitUntil(timeoutMillis = 5_000) {
            composeRule.onAllNodesWithText("Status: HEALTHY").fetchSemanticsNodes().isNotEmpty()
        }

        // 2. MLOps: Save tuning & trigger retrain
        composeRule.onNodeWithText("MLOps").performClick()
        composeRule.onNodeWithText("Save Tuning").performClick()
        composeRule.onNodeWithText("Trigger Retrain").performClick()
        composeRule.onNodeWithText("Start Retrain").performClick()

        // 3. Drift & Feedback
        composeRule.onNodeWithText("Drift & Feedback").performClick()
        composeRule.onNodeWithText("Total Transactions: 42").assertExists()

        // 4. Profiles & Audit: filter profiles
        composeRule.onNodeWithText("Profiles & Audit").performClick()
        composeRule.onNodeWithText("Filter profiles by name, ID, or country")
            .performTextInput("Alice")
        composeRule.onNodeWithText("Alice Mentor (mentor-001) — KE").assertExists()
    }
}
