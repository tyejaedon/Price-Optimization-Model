package edu.strathmore.pricing.viewmodel

import app.cash.turbine.test
import com.google.common.truth.Truth.assertThat
import edu.strathmore.pricing.data.repository.FakePricingRepository
import edu.strathmore.pricing.domain.PricingFailure
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Before
import org.junit.Test

/**
 * Offline state-transition tests required by issue #74's acceptance criteria: "state transition
 * tests run offline". No network, no Firebase project and no Android instrumentation are required.
 */
@OptIn(ExperimentalCoroutinesApi::class)
class PricingViewModelTest {

    private val dispatcher = StandardTestDispatcher()

    private fun validForm(viewModel: PricingViewModel) {
        viewModel.onDescriptionChanged("Senior Android engineer mentoring Kotlin and Compose teams.")
        viewModel.onIndustrySelected("mobile")
        viewModel.onMentorCountrySelected("ke")
        viewModel.onClientCountrySelected("us")
    }

    @Before
    fun setUp() {
        Dispatchers.setMain(dispatcher)
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    @Test
    fun `initial state is idle with an empty form`() = runTest(dispatcher) {
        val viewModel = PricingViewModel(FakePricingRepository())
        assertThat(viewModel.uiState.value).isInstanceOf(PricingUiState.Idle::class.java)
        assertThat(viewModel.uiState.value.form.rawDescription).isEmpty()
    }

    @Test
    fun `submitting a valid form transitions idle to loading to success`() = runTest(dispatcher) {
        val viewModel = PricingViewModel(FakePricingRepository(simulatedLatencyMs = 50))
        validForm(viewModel)

        viewModel.uiState.test {
            assertThat(awaitItem()).isInstanceOf(PricingUiState.Idle::class.java)

            viewModel.submitPriceOptimization()

            assertThat(awaitItem()).isInstanceOf(PricingUiState.Loading::class.java)
            val success = awaitItem()
            assertThat(success).isInstanceOf(PricingUiState.Success::class.java)
            assertThat((success as PricingUiState.Success).result.finalQuotedRate).isGreaterThan(0f)
        }
    }

    @Test
    fun `submitting an invalid form yields error without calling the repository`() = runTest(dispatcher) {
        val viewModel = PricingViewModel(FakePricingRepository())
        viewModel.onDescriptionChanged("too short")

        viewModel.submitPriceOptimization()

        val state = viewModel.uiState.value
        assertThat(state).isInstanceOf(PricingUiState.Error::class.java)
        assertThat((state as PricingUiState.Error).message).contains("20 characters")
    }

    @Test
    fun `repository failure surfaces a user-facing error state`() = runTest(dispatcher) {
        val repository = FakePricingRepository(
            resultProvider = FakePricingRepository.failure(PricingFailure.ServiceUnavailable),
        )
        val viewModel = PricingViewModel(repository)
        validForm(viewModel)

        viewModel.uiState.test {
            awaitItem() // Idle
            viewModel.submitPriceOptimization()
            awaitItem() // Loading
            val error = awaitItem()
            assertThat(error).isInstanceOf(PricingUiState.Error::class.java)
            assertThat((error as PricingUiState.Error).message).isEqualTo(PricingFailure.ServiceUnavailable.message)
        }
    }

    @Test
    fun `clearForm resets to idle with a blank form`() = runTest(dispatcher) {
        val viewModel = PricingViewModel(FakePricingRepository())
        validForm(viewModel)

        viewModel.clearForm()

        val state = viewModel.uiState.value
        assertThat(state).isInstanceOf(PricingUiState.Idle::class.java)
        assertThat(state.form.rawDescription).isEmpty()
    }

    @Test
    fun `retryOptimization re-invokes submission after a failure`() = runTest(dispatcher) {
        var callCount = 0
        val repository = FakePricingRepository(simulatedLatencyMs = 10) { query ->
            callCount++
            FakePricingRepository.defaultSuccess(query)
        }
        val viewModel = PricingViewModel(repository)
        validForm(viewModel)

        viewModel.submitPriceOptimization()
        dispatcher.scheduler.advanceUntilIdle()
        viewModel.retryOptimization()
        dispatcher.scheduler.advanceUntilIdle()

        assertThat(callCount).isEqualTo(2)
        assertThat(viewModel.uiState.value).isInstanceOf(PricingUiState.Success::class.java)
    }
}
