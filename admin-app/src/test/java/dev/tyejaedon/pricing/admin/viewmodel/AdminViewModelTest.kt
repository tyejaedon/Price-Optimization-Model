package dev.tyejaedon.pricing.admin.viewmodel

import com.google.common.truth.Truth.assertThat
import dev.tyejaedon.pricing.admin.data.network.dto.GridSearchConfigDTO
import dev.tyejaedon.pricing.admin.data.repository.FakeAdminRepository
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class AdminViewModelTest {
    private val dispatcher = StandardTestDispatcher()

    @Before
    fun setUp() {
        Dispatchers.setMain(dispatcher)
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    @Test
    fun `unlock with valid token loads dashboard state`() =
        runTest(dispatcher) {
            val viewModel = AdminViewModel(FakeAdminRepository(simulatedLatencyMs = 0))

            viewModel.unlock("admin-secret")
            dispatcher.scheduler.advanceUntilIdle()

            assertThat(viewModel.sessionState.value).isEqualTo(AdminSessionState.Unlocked)
            assertThat(
                viewModel.dashboardState.value.artifacts
                    ?.modelsLoaded,
            ).isTrue()
            assertThat(
                viewModel.dashboardState.value.drift
                    ?.totalTransactions,
            ).isEqualTo(42)
        }

    @Test
    fun `updateTuning and triggerRetrain update dashboard state`() =
        runTest(dispatcher) {
            val viewModel = AdminViewModel(FakeAdminRepository(simulatedLatencyMs = 0))
            viewModel.unlock("admin-secret")
            dispatcher.scheduler.advanceUntilIdle()

            viewModel.updateTuning(GridSearchConfigDTO(textWeight = 1.5f))
            dispatcher.scheduler.advanceUntilIdle()
            assertThat(viewModel.dashboardState.value.tuning.textWeight).isEqualTo(1.5f)

            viewModel.triggerRetrain()
            dispatcher.scheduler.advanceUntilIdle()
            assertThat(
                viewModel.dashboardState.value.retrainStatus
                    ?.jobId,
            ).isEqualTo("retrain-demo-01")

            viewModel.pollRetrainStatus()
            dispatcher.scheduler.advanceUntilIdle()
            assertThat(
                viewModel.dashboardState.value.retrainStatus
                    ?.status,
            ).isEqualTo("succeeded")
        }
}
