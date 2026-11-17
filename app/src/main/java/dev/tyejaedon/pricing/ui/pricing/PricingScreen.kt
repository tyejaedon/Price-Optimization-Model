package dev.tyejaedon.pricing.ui.pricing

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import dev.tyejaedon.pricing.data.network.dto.SelfListingDTO
import dev.tyejaedon.pricing.ui.components.InlineErrorText
import dev.tyejaedon.pricing.ui.components.PrimaryActionButton
import dev.tyejaedon.pricing.ui.pricing.components.CapabilityInputForm
import dev.tyejaedon.pricing.ui.pricing.components.CountryDropdown
import dev.tyejaedon.pricing.ui.pricing.components.IndustryDropdown
import dev.tyejaedon.pricing.ui.pricing.components.PricingResultCard
import dev.tyejaedon.pricing.ui.pricing.components.SaturationSlider
import dev.tyejaedon.pricing.ui.pricing.components.formatIndustryLabel
import dev.tyejaedon.pricing.ui.theme.PricingSpacing
import dev.tyejaedon.pricing.viewmodel.MentorTab
import dev.tyejaedon.pricing.viewmodel.MentorWorkspaceState
import dev.tyejaedon.pricing.viewmodel.PricingUiState
import dev.tyejaedon.pricing.viewmodel.PricingViewModel
import dev.tyejaedon.pricing.viewmodel.ProfileUiState

/**
 * `PricingScreen` boundary from the class diagram: renders [PricingUiState] and forwards user
 * events to [PricingViewModel]. Covers the Idle/Loading/Success/Error states required by issue
 * #74's canonical Sprint 4 acceptance.
 */
@Composable
fun PricingScreen(
    viewModel: PricingViewModel,
    onSignOut: () -> Unit = {},
    demoMode: Boolean = false,
    userEmail: String = "",
    autoLoadProfile: Boolean = false,
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    val profileState by viewModel.profileState.collectAsStateWithLifecycle()
    val workspaceState by viewModel.workspaceState.collectAsStateWithLifecycle()

    LaunchedEffect(demoMode, autoLoadProfile) {
        viewModel.loadMetadata()
        if (demoMode && uiState.form.mentorId.isBlank()) {
            viewModel.onMentorIdChanged("demo-mentor")
        } else if (!demoMode && autoLoadProfile) {
            viewModel.loadMyProfile()
        }
    }

    PricingScreenContent(
        uiState = uiState,
        profileState = profileState,
        workspaceState = workspaceState,
        onSignOut = onSignOut,
        demoMode = demoMode,
        userEmail = userEmail,
        autoLoadProfile = autoLoadProfile,
        onLoadMyProfile = viewModel::loadMyProfile,
        onSaveMyProfile = viewModel::saveMyProfile,
        onSelectTab = viewModel::selectTab,
        onDescriptionChanged = viewModel::onDescriptionChanged,
        onMentorIdChanged = viewModel::onMentorIdChanged,
        onIndustrySelected = viewModel::onIndustrySelected,
        onMentorCountrySelected = viewModel::onMentorCountrySelected,
        onClientCountrySelected = viewModel::onClientCountrySelected,
        onBaseRateFloorChanged = viewModel::onBaseRateFloorChanged,
        onCompetitivenessScoreChanged = viewModel::onCompetitivenessScoreChanged,
        onRetryOptimization = viewModel::retryOptimization,
        onClearForm = viewModel::clearForm,
        onSubmitPriceOptimization = viewModel::submitPriceOptimization,
        onApplyListingToQuote = viewModel::applyListingToQuote,
        onSaveListing = viewModel::saveListing,
        onSubmitFeedback = viewModel::submitFeedback,
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PricingScreenContent(
    uiState: PricingUiState,
    profileState: ProfileUiState = ProfileUiState.Loading,
    workspaceState: MentorWorkspaceState = MentorWorkspaceState(),
    onSignOut: () -> Unit = {},
    demoMode: Boolean = false,
    userEmail: String = "",
    autoLoadProfile: Boolean = false,
    onLoadMyProfile: () -> Unit = {},
    onSaveMyProfile: (fullName: String, email: String, countryCode: String) -> Unit = { _, _, _ -> },
    onSelectTab: (MentorTab) -> Unit = {},
    onDescriptionChanged: (String) -> Unit = {},
    onMentorIdChanged: (String) -> Unit = {},
    onIndustrySelected: (String) -> Unit = {},
    onMentorCountrySelected: (String) -> Unit = {},
    onClientCountrySelected: (String) -> Unit = {},
    onBaseRateFloorChanged: (String) -> Unit = {},
    onCompetitivenessScoreChanged: (Float) -> Unit = {},
    onRetryOptimization: () -> Unit = {},
    onClearForm: () -> Unit = {},
    onSubmitPriceOptimization: () -> Unit = {},
    onApplyListingToQuote: (SelfListingDTO) -> Unit = {},
    onSaveListing: (
        listingId: String,
        title: String,
        industryId: String,
        rawText: String,
        verifiedRate: Float,
    ) -> Unit = { _, _, _, _, _ -> },
    onSubmitFeedback: (
        transactionId: String,
        outcomeValue: String,
        actualRate: Float?,
        notes: String?,
    ) -> Unit = { _, _, _, _ -> },
) {
    val state = uiState

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(text = "Price your service") },
                actions = {
                    if (!demoMode) {
                        TextButton(onClick = onSignOut) {
                            Text(text = "Sign out")
                        }
                    }
                },
            )
        },
    ) { padding ->
        Column(
            modifier =
                Modifier
                    .fillMaxSize()
                    .padding(padding)
                    .padding(PricingSpacing.Medium)
                    .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(PricingSpacing.Medium),
        ) {
            if (!demoMode && autoLoadProfile) {
                when (val profile = profileState) {
                    ProfileUiState.Loading -> {
                        LoadingIndicator()
                        return@Column
                    }
                    ProfileUiState.NeedsOnboarding -> {
                        MentorOnboardingForm(
                            defaultEmail = userEmail,
                            onSave = onSaveMyProfile,
                        )
                        return@Column
                    }
                    is ProfileUiState.Error -> {
                        ErrorSection(
                            message = profile.message,
                            onRetry = onLoadMyProfile,
                        )
                        MentorOnboardingForm(
                            defaultEmail = userEmail,
                            onSave = onSaveMyProfile,
                        )
                        return@Column
                    }
                    is ProfileUiState.Ready -> Unit
                }
            }

            if (demoMode) {
                Text(
                    text = "Demo mode: sample quote only; no live backend request is sent.",
                    style = MaterialTheme.typography.bodySmall,
                )
            }

            TabRow(selectedTabIndex = workspaceState.selectedTab.ordinal) {
                MentorTab.entries.forEach { tab ->
                    Tab(
                        selected = workspaceState.selectedTab == tab,
                        onClick = { onSelectTab(tab) },
                        text = { Text(tab.label, maxLines = 1) },
                    )
                }
            }

            if (workspaceState.isLoading) {
                LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
            }
            if (!workspaceState.modelsLoaded) {
                Text(
                    text = "Warming up pricing engine… Quotes may take a few extra seconds.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.secondary,
                )
            }
            workspaceState.statusMessage?.let {
                Text(text = it, color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.bodySmall)
            }
            workspaceState.errorMessage?.let { InlineErrorText(message = it) }

            when (workspaceState.selectedTab) {
                MentorTab.QUOTE -> {
                    Text(
                        text = "Get a peer-backed KES/hour rate, instantly.",
                        style = MaterialTheme.typography.bodyMedium,
                    )

                    val form = state.form
                    CapabilityInputForm(
                        rawDescription = form.rawDescription,
                        onDescriptionChanged = onDescriptionChanged,
                        mentorId = form.mentorId,
                        onMentorIdChanged = onMentorIdChanged,
                        selectedIndustry = form.selectedIndustry,
                        onIndustrySelected = onIndustrySelected,
                        industries = workspaceState.industries,
                        mentorCountry = form.mentorCountry,
                        onMentorCountryChanged = onMentorCountrySelected,
                        clientCountry = form.clientCountry,
                        onClientCountryChanged = onClientCountrySelected,
                        baseRateFloor = form.baseRateFloor,
                        onBaseRateFloorChanged = onBaseRateFloorChanged,
                    )

                    SaturationSlider(
                        score = form.competitivenessScore,
                        onScoreChanged = onCompetitivenessScoreChanged,
                    )

                    form.validationError?.let { InlineErrorText(message = it) }

                    when (state) {
                        is PricingUiState.Loading -> LoadingIndicator()
                        is PricingUiState.Error ->
                            ErrorSection(
                                message = state.message,
                                onRetry = onRetryOptimization,
                            )
                        is PricingUiState.Success -> PricingResultCard(result = state.result)
                        is PricingUiState.Idle -> Unit
                    }

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(PricingSpacing.Small),
                    ) {
                        OutlinedButton(
                            onClick = onClearForm,
                            enabled = state !is PricingUiState.Loading,
                        ) {
                            Text("Clear")
                        }
                        PrimaryActionButton(
                            text = "Calculate rate",
                            onClick = onSubmitPriceOptimization,
                            enabled = state !is PricingUiState.Loading,
                            contentDescription = "Calculate recommended hourly rate",
                            modifier = Modifier.weight(1f),
                        )
                    }
                }
                MentorTab.LISTINGS ->
                    ListingsTab(
                        workspaceState = workspaceState,
                        onApplyListingToQuote = onApplyListingToQuote,
                        onSaveListing = onSaveListing,
                    )
                MentorTab.HISTORY ->
                    HistoryTab(
                        workspaceState = workspaceState,
                        onSubmitFeedback = onSubmitFeedback,
                    )
            }
        }
    }
}

@Composable
private fun LoadingIndicator() {
    Column(
        modifier =
            Modifier
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
private fun ErrorSection(
    message: String,
    onRetry: () -> Unit,
) {
    Column(
        modifier =
            Modifier
                .fillMaxWidth()
                .semantics { liveRegion = androidx.compose.ui.semantics.LiveRegionMode.Assertive },
    ) {
        InlineErrorText(message = message)
        PrimaryActionButton(text = "Try again", onClick = onRetry, contentDescription = "Retry calculation")
    }
}

@Composable
private fun MentorOnboardingForm(
    defaultEmail: String,
    onSave: (fullName: String, email: String, countryCode: String) -> Unit,
) {
    var fullName by remember { mutableStateOf("") }
    var email by remember(defaultEmail) { mutableStateOf(defaultEmail) }
    var countryCode by remember { mutableStateOf("KE") }

    Text(
        text = "Complete your mentor profile",
        style = MaterialTheme.typography.titleMedium,
    )
    Text(
        text = "Your profile links your Firebase account to your pricing quotes automatically.",
        style = MaterialTheme.typography.bodyMedium,
    )
    OutlinedTextField(
        value = fullName,
        onValueChange = { fullName = it },
        label = { Text("Full name") },
        singleLine = true,
        modifier = Modifier.fillMaxWidth(),
    )
    OutlinedTextField(
        value = email,
        onValueChange = { email = it },
        label = { Text("Email") },
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email),
        singleLine = true,
        modifier = Modifier.fillMaxWidth(),
    )
    CountryDropdown(
        label = "Your country",
        selectedCode = countryCode,
        onCountrySelected = { countryCode = it },
        contentDescriptionText = "Your country ISO 2-letter code",
    )
    PrimaryActionButton(
        text = "Save mentor profile",
        onClick = { onSave(fullName, email, countryCode) },
        enabled = fullName.isNotBlank() && email.isNotBlank() && countryCode.length == 2,
        modifier = Modifier.fillMaxWidth(),
    )
}

@Composable
private fun ListingsTab(
    workspaceState: MentorWorkspaceState,
    onApplyListingToQuote: (SelfListingDTO) -> Unit,
    onSaveListing: (listingId: String, title: String, industryId: String, rawText: String, verifiedRate: Float) -> Unit,
) {
    var title by remember { mutableStateOf("") }
    var industryId by remember(workspaceState.industries) {
        mutableStateOf(workspaceState.industries.firstOrNull() ?: "mobile")
    }
    var rawText by remember { mutableStateOf("") }
    var verifiedRate by remember { mutableStateOf("2500") }

    Text(text = "Saved service listings (${workspaceState.listings.size})", style = MaterialTheme.typography.titleMedium)
    workspaceState.listings.forEach { listing ->
        Card(modifier = Modifier.fillMaxWidth()) {
            Column(modifier = Modifier.padding(PricingSpacing.Medium), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text(text = listing.title, style = MaterialTheme.typography.titleSmall)
                Text(
                    text = "${formatIndustryLabel(listing.industryId)} • ${listing.verifiedRate} KES/hour",
                    style = MaterialTheme.typography.bodySmall,
                )
                Text(text = listing.rawText, style = MaterialTheme.typography.bodySmall)
                OutlinedButton(onClick = { onApplyListingToQuote(listing) }) {
                    Text("Use in Quote")
                }
            }
        }
    }

    Text(text = "Add service listing", style = MaterialTheme.typography.titleMedium)
    OutlinedTextField(
        value = title,
        onValueChange = { title = it },
        label = { Text("Listing title") },
        singleLine = true,
        modifier = Modifier.fillMaxWidth(),
    )
    IndustryDropdown(
        selectedIndustry = industryId,
        onIndustrySelected = { industryId = it },
        industries = workspaceState.industries,
    )
    OutlinedTextField(
        value = rawText,
        onValueChange = { rawText = it },
        label = { Text("Service description (min 20 chars)") },
        minLines = 3,
        modifier = Modifier.fillMaxWidth(),
    )
    OutlinedTextField(
        value = verifiedRate,
        onValueChange = { verifiedRate = it },
        label = { Text("Base rate (KES/hour)") },
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
        singleLine = true,
        modifier = Modifier.fillMaxWidth(),
    )
    PrimaryActionButton(
        text = "Save listing",
        onClick = {
            onSaveListing(
                "",
                title,
                industryId,
                rawText,
                verifiedRate.toFloatOrNull() ?: 1f,
            )
            title = ""
            rawText = ""
        },
        enabled = title.isNotBlank() && rawText.trim().length >= 20,
        modifier = Modifier.fillMaxWidth(),
    )
}

@Composable
private fun HistoryTab(
    workspaceState: MentorWorkspaceState,
    onSubmitFeedback: (transactionId: String, outcomeValue: String, actualRate: Float?, notes: String?) -> Unit,
) {
    var adjustingTxId by remember { mutableStateOf<String?>(null) }
    var adjustedRateInput by remember { mutableStateOf("") }
    var adjustedNotesInput by remember { mutableStateOf("") }

    adjustingTxId?.let { txId ->
        AlertDialog(
            onDismissRequest = { adjustingTxId = null },
            title = { Text("Report adjusted rate") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(PricingSpacing.Small)) {
                    OutlinedTextField(
                        value = adjustedRateInput,
                        onValueChange = { adjustedRateInput = it },
                        label = { Text("Actual rate agreed (KES/hour)") },
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                        singleLine = true,
                    )
                    OutlinedTextField(
                        value = adjustedNotesInput,
                        onValueChange = { adjustedNotesInput = it },
                        label = { Text("Notes (optional)") },
                        singleLine = true,
                    )
                }
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        onSubmitFeedback(
                            txId,
                            "adjusted",
                            adjustedRateInput.toFloatOrNull(),
                            adjustedNotesInput.trim().takeIf { it.isNotBlank() },
                        )
                        adjustingTxId = null
                        adjustedRateInput = ""
                        adjustedNotesInput = ""
                    },
                ) {
                    Text("Submit")
                }
            },
            dismissButton = {
                TextButton(onClick = { adjustingTxId = null }) {
                    Text("Cancel")
                }
            },
        )
    }

    Text(text = "Quote history (${workspaceState.history.size})", style = MaterialTheme.typography.titleMedium)
    if (workspaceState.history.isEmpty()) {
        Text(text = "No past quotes recorded yet.", style = MaterialTheme.typography.bodyMedium)
        return
    }
    workspaceState.history.forEach { item ->
        val recordedOutcome = workspaceState.feedbackStatusByTx[item.transactionId]
        Card(modifier = Modifier.fillMaxWidth()) {
            Column(modifier = Modifier.padding(PricingSpacing.Medium), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text(
                    text = "${formatIndustryLabel(item.selectedIndustry ?: "general")} • ${item.finalQuotedRate ?: 0f} KES/hour",
                    style = MaterialTheme.typography.titleSmall,
                )
                val dateLabel =
                    item.executedAt
                        ?.take(10)
                        ?.let { " • $it" }
                        .orEmpty()
                Text(
                    text = "Corridor: ${item.mentorCountryCode ?: "?"} -> ${item.clientCountryCode ?: "?"}$dateLabel",
                    style = MaterialTheme.typography.bodySmall,
                )
                if (recordedOutcome != null) {
                    Text(
                        text = "Feedback recorded: $recordedOutcome",
                        color = MaterialTheme.colorScheme.primary,
                        style = MaterialTheme.typography.bodySmall,
                    )
                } else {
                    Row(horizontalArrangement = Arrangement.spacedBy(PricingSpacing.ExtraSmall)) {
                        OutlinedButton(onClick = { onSubmitFeedback(item.transactionId, "accepted", null, null) }) {
                            Text("Accepted")
                        }
                        OutlinedButton(
                            onClick = {
                                onSubmitFeedback(
                                    item.transactionId,
                                    "booked",
                                    item.finalQuotedRate,
                                    null,
                                )
                            },
                        ) {
                            Text("Booked")
                        }
                        OutlinedButton(
                            onClick = {
                                adjustedRateInput =
                                    item.finalQuotedRate
                                        ?.toInt()
                                        ?.toString()
                                        .orEmpty()
                                adjustingTxId = item.transactionId
                            },
                        ) {
                            Text("Adjusted")
                        }
                        OutlinedButton(onClick = { onSubmitFeedback(item.transactionId, "declined", null, null) }) {
                            Text("Declined")
                        }
                    }
                }
            }
        }
    }
}
