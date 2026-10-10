package edu.strathmore.pricing.ui.pricing

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import edu.strathmore.pricing.ui.components.InlineErrorText
import edu.strathmore.pricing.ui.components.PrimaryActionButton
import edu.strathmore.pricing.ui.pricing.components.CapabilityInputForm
import edu.strathmore.pricing.ui.pricing.components.PricingResultCard
import edu.strathmore.pricing.ui.pricing.components.SaturationSlider
import edu.strathmore.pricing.ui.theme.PricingSpacing
import edu.strathmore.pricing.viewmodel.PricingUiState
import edu.strathmore.pricing.viewmodel.PricingViewModel

/**
 * `PricingScreen` boundary from the class diagram: renders [PricingUiState] and forwards user
 * events to [PricingViewModel]. Covers the Idle/Loading/Success/Error states required by issue
 * #74's canonical Sprint 4 acceptance.
 */
@Composable
fun PricingScreen(viewModel: PricingViewModel) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    val state = uiState

    Scaffold { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(PricingSpacing.Medium)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(PricingSpacing.Medium),
        ) {
            Text(text = "Price your service", style = MaterialTheme.typography.headlineSmall)
            Text(
                text = "Get a peer-backed KES/hour rate, instantly.",
                style = MaterialTheme.typography.bodyMedium,
            )

            val form = state.form
            CapabilityInputForm(
                rawDescription = form.rawDescription,
                onDescriptionChanged = viewModel::onDescriptionChanged,
                selectedIndustry = form.selectedIndustry,
                onIndustrySelected = viewModel::onIndustrySelected,
                mentorCountry = form.mentorCountry,
                onMentorCountryChanged = viewModel::onMentorCountrySelected,
                clientCountry = form.clientCountry,
                onClientCountryChanged = viewModel::onClientCountrySelected,
            )

            SaturationSlider(
                score = form.competitivenessScore,
                onScoreChanged = viewModel::onCompetitivenessScoreChanged,
            )

            form.validationError?.let { InlineErrorText(message = it) }

            when (state) {
                is PricingUiState.Loading -> LoadingIndicator()
                is PricingUiState.Error -> ErrorSection(
                    message = state.message,
                    onRetry = viewModel::retryOptimization,
                )
                is PricingUiState.Success -> PricingResultCard(result = state.result)
                is PricingUiState.Idle -> Unit
            }

            PrimaryActionButton(
                text = "Calculate rate",
                onClick = viewModel::submitPriceOptimization,
                enabled = state !is PricingUiState.Loading && form.isFormValid(),
                contentDescription = "Calculate recommended hourly rate",
                modifier = Modifier.fillMaxWidth(),
            )
        }
    }
}

@Composable
private fun LoadingIndicator() {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .semantics {
                liveRegion = androidx.compose.ui.semantics.LiveRegionMode.Polite
                contentDescription = "Finding peer-matched rates"
            },
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        CircularProgressIndicator()
        Text(text = "Finding peer-matched rates…", style = MaterialTheme.typography.bodyMedium)
    }
}

@Composable
private fun ErrorSection(message: String, onRetry: () -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .semantics { liveRegion = androidx.compose.ui.semantics.LiveRegionMode.Assertive },
    ) {
        InlineErrorText(message = message)
        PrimaryActionButton(text = "Try again", onClick = onRetry, contentDescription = "Retry calculation")
    }
}

