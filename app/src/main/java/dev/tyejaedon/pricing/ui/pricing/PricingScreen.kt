package dev.tyejaedon.pricing.ui.pricing

import androidx.compose.animation.AnimatedContent
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.Workspaces
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import dev.tyejaedon.pricing.data.network.dto.QuoteHistoryItemDTO
import dev.tyejaedon.pricing.data.network.dto.SelfListingDTO
import dev.tyejaedon.pricing.designsystem.GlassCard
import dev.tyejaedon.pricing.designsystem.GlassFloatingNavDock
import dev.tyejaedon.pricing.designsystem.GlassInsetDivider
import dev.tyejaedon.pricing.designsystem.GlassModalBottomSheet
import dev.tyejaedon.pricing.designsystem.GlassSecondaryButton
import dev.tyejaedon.pricing.designsystem.GlassStatusBadge
import dev.tyejaedon.pricing.designsystem.GlassTextField
import dev.tyejaedon.pricing.designsystem.LocalOneUiGlassColors
import dev.tyejaedon.pricing.designsystem.OneUiEmptyStateCard
import dev.tyejaedon.pricing.designsystem.OneUiGlassScaffold
import dev.tyejaedon.pricing.designsystem.OneUiMultiStepContainer
import dev.tyejaedon.pricing.designsystem.OneUiStepMeta
import dev.tyejaedon.pricing.ui.components.InlineErrorText
import dev.tyejaedon.pricing.ui.components.PrimaryActionButton
import dev.tyejaedon.pricing.ui.pricing.components.CapabilityCorridorStep
import dev.tyejaedon.pricing.ui.pricing.components.CapabilityPositioningStep
import dev.tyejaedon.pricing.ui.pricing.components.CapabilityServiceStep
import dev.tyejaedon.pricing.ui.pricing.components.CountryDropdown
import dev.tyejaedon.pricing.ui.pricing.components.IndustryDropdown
import dev.tyejaedon.pricing.ui.pricing.components.PricingGlossarySheet
import dev.tyejaedon.pricing.ui.pricing.components.PricingResultCard
import dev.tyejaedon.pricing.ui.pricing.components.formatIndustryLabel
import dev.tyejaedon.pricing.ui.pricing.formatting.formatKesRate
import dev.tyejaedon.pricing.ui.theme.PricingSpacing
import dev.tyejaedon.pricing.viewmodel.MentorTab
import dev.tyejaedon.pricing.viewmodel.MentorWorkspaceState
import dev.tyejaedon.pricing.viewmodel.PricingUiState
import dev.tyejaedon.pricing.viewmodel.PricingViewModel
import dev.tyejaedon.pricing.viewmodel.ProfileUiState
import kotlin.math.roundToInt

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
        onSelectQuoteStep = viewModel::setQuoteStep,
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
        onOpenQuoteDetail = viewModel::openQuoteDetail,
        onCloseQuoteDetail = viewModel::closeQuoteDetail,
        onApplyListingToQuote = viewModel::applyListingToQuote,
        onApplyHistoryItemToQuote = viewModel::applyHistoryItemToQuote,
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
    onSelectQuoteStep: (Int) -> Unit = {},
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
    onOpenQuoteDetail: () -> Unit = {},
    onCloseQuoteDetail: () -> Unit = {},
    onApplyListingToQuote: (SelfListingDTO) -> Unit = {},
    onApplyHistoryItemToQuote: (QuoteHistoryItemDTO) -> Unit = {},
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
    val glass = LocalOneUiGlassColors.current
    val showDetail = workspaceState.isQuoteDetailOpen && state is PricingUiState.Success

    AnimatedContent(
        targetState = showDetail,
        label = "quoteDetailTransition",
    ) { detailOpen ->
        if (detailOpen && state is PricingUiState.Success) {
            QuoteDetailScreen(
                result = state.result,
                form = state.form,
                onBack = onCloseQuoteDetail,
            )
        } else {
            var showGlossary by remember { mutableStateOf(false) }
            var activeGlossaryTermId by remember { mutableStateOf<String?>(null) }
            var showSaveQuoteAsListingSheet by remember { mutableStateOf(false) }

            if (showGlossary) {
                PricingGlossarySheet(
                    onDismiss = { showGlossary = false },
                    initialExpandedTermId = activeGlossaryTermId,
                )
            }

            if (showSaveQuoteAsListingSheet && state is PricingUiState.Success) {
                val form = state.form
                val defaultTitle =
                    remember(form.selectedIndustry) {
                        "${formatIndustryLabel(form.selectedIndustry.ifBlank { "general_tech" })} Mentorship"
                    }
                var draftTitle by remember(defaultTitle) { mutableStateOf(defaultTitle) }
                var draftIndustry by remember(form.selectedIndustry) {
                    mutableStateOf(form.selectedIndustry.ifBlank { "general_tech" })
                }
                var draftText by remember(form.rawDescription) { mutableStateOf(form.rawDescription) }
                var draftRate by remember(state.result.basePredictedRate) {
                    mutableStateOf(state.result.basePredictedRate.roundToInt().toString())
                }

                GlassModalBottomSheet(
                    onDismissRequest = { showSaveQuoteAsListingSheet = false },
                    title = "Save quote to service catalog",
                    actions = {
                        GlassSecondaryButton(
                            text = "Cancel",
                            onClick = { showSaveQuoteAsListingSheet = false },
                            modifier = Modifier.weight(1f),
                        )
                        PrimaryActionButton(
                            text = "Save Listing",
                            onClick = {
                                onSaveListing(
                                    "",
                                    draftTitle,
                                    draftIndustry,
                                    draftText,
                                    draftRate.toFloatOrNull() ?: state.result.basePredictedRate,
                                )
                                showSaveQuoteAsListingSheet = false
                            },
                            enabled = draftTitle.isNotBlank() && draftText.trim().length >= 20,
                            modifier = Modifier.weight(1f),
                        )
                    },
                ) {
                    Text(
                        text = "Pre-filled from your quote so you can reuse this service anytime.",
                        style = MaterialTheme.typography.bodyMedium,
                        color = glass.textSecondary,
                    )
                    GlassTextField(
                        value = draftTitle,
                        onValueChange = { draftTitle = it },
                        label = "Listing title",
                        singleLine = true,
                    )
                    IndustryDropdown(
                        selectedIndustry = draftIndustry,
                        onIndustrySelected = { draftIndustry = it },
                        industries = workspaceState.industries,
                    )
                    GlassTextField(
                        value = draftText,
                        onValueChange = { draftText = it },
                        label = "Service description",
                        singleLine = false,
                        minLines = 3,
                    )
                    GlassTextField(
                        value = draftRate,
                        onValueChange = { draftRate = it },
                        label = "Base rate (KES/hour)",
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                        singleLine = true,
                    )
                }
            }

            OneUiGlassScaffold(
                title = workspaceState.selectedTab.title,
                actions = {
                    GlassSecondaryButton(
                        text = "Glossary",
                        onClick = {
                            activeGlossaryTermId = null
                            showGlossary = true
                        },
                        contentDescription = "Open pricing glossary",
                    )
                    if (!demoMode) {
                        GlassSecondaryButton(
                            text = "Sign out",
                            onClick = onSignOut,
                        )
                    }
                },
                bottomBar = {
                    GlassFloatingNavDock(
                        items = MentorTab.entries,
                        selectedItem = workspaceState.selectedTab,
                        onSelectItem = onSelectTab,
                        labelProvider = { it.label },
                    )
                },
            ) { padding ->
                Column(
                    modifier =
                        Modifier
                            .fillMaxSize()
                            .padding(padding)
                            .padding(top = 28.dp)
                            .padding(horizontal = PricingSpacing.Medium)
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
                        GlassStatusBadge(
                            text = "Demo mode: sample quote only; no live backend request is sent.",
                            tint = glass.infoTint,
                        )
                    }

                    if (workspaceState.isLoading) {
                        LinearProgressIndicator(
                            modifier = Modifier.fillMaxWidth(),
                            color = glass.primaryAccent,
                            trackColor = glass.recessedWellFill,
                        )
                    }
                    if (!workspaceState.modelsLoaded) {
                        GlassStatusBadge(
                            text = "Warming up pricing engine… Quotes may take a few extra seconds.",
                            tint = glass.warningTint,
                        )
                    }
                    workspaceState.statusMessage?.let {
                        GlassStatusBadge(text = it, tint = glass.successTint)
                    }
                    workspaceState.errorMessage?.let { InlineErrorText(message = it, modifier = Modifier.fillMaxWidth()) }

                    when (workspaceState.selectedTab) {
                        MentorTab.QUOTE -> {
                            val form = state.form
                            val steps =
                                remember {
                                    listOf(
                                        OneUiStepMeta(
                                            title = "Describe your service",
                                            subtitle = "Tell us what you offer so we can match you with similar mentors.",
                                        ),
                                        OneUiStepMeta(
                                            title = "Choose your market corridor",
                                            subtitle = "Select your country and your client's country for fair rate calibration.",
                                        ),
                                        OneUiStepMeta(
                                            title = "Set floor & positioning",
                                            subtitle = "Add an optional minimum rate and indicate how crowded your niche is.",
                                        ),
                                    )
                                }
                            val currentStep = workspaceState.quoteStep.coerceIn(0, steps.lastIndex)
                            val canProceed =
                                when (currentStep) {
                                    0 -> form.rawDescription.trim().length >= 20 && form.selectedIndustry.isNotBlank()
                                    1 -> form.mentorCountry.length == 2 && form.clientCountry.length == 2
                                    else -> true
                                }

                            OneUiMultiStepContainer(
                                currentStep = currentStep,
                                steps = steps,
                                onBack = { onSelectQuoteStep(currentStep - 1) },
                                onNext = {
                                    if (currentStep < steps.lastIndex) {
                                        onSelectQuoteStep(currentStep + 1)
                                    } else {
                                        onSubmitPriceOptimization()
                                    }
                                },
                                canProceed = canProceed,
                                finalActionLabel = "Get Recommended Rate",
                                finalActionContentDescription = "Calculate recommended hourly rate",
                                secondaryResetLabel = "Reset Inputs",
                                onSecondaryReset = onClearForm,
                                isBusy = state is PricingUiState.Loading,
                            ) { stepIndex ->
                                when (stepIndex) {
                                    0 ->
                                        CapabilityServiceStep(
                                            rawDescription = form.rawDescription,
                                            onDescriptionChanged = onDescriptionChanged,
                                            selectedIndustry = form.selectedIndustry,
                                            onIndustrySelected = onIndustrySelected,
                                            industries = workspaceState.industries,
                                        )
                                    1 ->
                                        CapabilityCorridorStep(
                                            mentorCountry = form.mentorCountry,
                                            onMentorCountryChanged = onMentorCountrySelected,
                                            clientCountry = form.clientCountry,
                                            onClientCountryChanged = onClientCountrySelected,
                                        )
                                    else ->
                                        CapabilityPositioningStep(
                                            baseRateFloor = form.baseRateFloor,
                                            onBaseRateFloorChanged = onBaseRateFloorChanged,
                                            competitivenessScore = form.competitivenessScore,
                                            onCompetitivenessScoreChanged = onCompetitivenessScoreChanged,
                                            onOpenGlossaryTerm = { termId ->
                                                activeGlossaryTermId = termId
                                                showGlossary = true
                                            },
                                        )
                                }
                            }

                            form.validationError?.let { InlineErrorText(message = it, modifier = Modifier.fillMaxWidth()) }

                            when (state) {
                                is PricingUiState.Loading -> LoadingIndicator()
                                is PricingUiState.Error ->
                                    ErrorSection(
                                        message = state.message,
                                        onRetry = onRetryOptimization,
                                    )
                                is PricingUiState.Success -> {
                                    PricingResultCard(
                                        result = state.result,
                                        onOpenDetails = onOpenQuoteDetail,
                                    )
                                    GlassCard(modifier = Modifier.fillMaxWidth()) {
                                        Column(verticalArrangement = Arrangement.spacedBy(PricingSpacing.Small)) {
                                            Text(
                                                text = "Next steps",
                                                style = MaterialTheme.typography.titleMedium,
                                                color = glass.textPrimary,
                                            )
                                            Text(
                                                text = "Save this service to your catalog for 1-tap future quotes, or review past quotes in History.",
                                                style = MaterialTheme.typography.bodyMedium,
                                                color = glass.textSecondary,
                                            )
                                            GlassSecondaryButton(
                                                text = "Save to Catalog",
                                                onClick = { showSaveQuoteAsListingSheet = true },
                                                modifier = Modifier.fillMaxWidth(),
                                                contentDescription = "Save quoted service to catalog",
                                            )
                                            Row(
                                                modifier = Modifier.fillMaxWidth(),
                                                horizontalArrangement = Arrangement.spacedBy(PricingSpacing.Small),
                                            ) {
                                                GlassSecondaryButton(
                                                    text = "View History",
                                                    onClick = { onSelectTab(MentorTab.HISTORY) },
                                                    modifier = Modifier.weight(1f),
                                                )
                                                PrimaryActionButton(
                                                    text = "Start New Quote",
                                                    onClick = onClearForm,
                                                    modifier = Modifier.weight(1f),
                                                )
                                            }
                                        }
                                    }
                                }
                                is PricingUiState.Idle -> Unit
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
                                onApplyHistoryItemToQuote = onApplyHistoryItemToQuote,
                                onStartNewQuote = { onSelectTab(MentorTab.QUOTE) },
                            )
                    }
                    Spacer(modifier = Modifier.height(PricingSpacing.Medium))
                }
            }
        }
    }
}

@Composable
private fun LoadingIndicator() {
    val glass = LocalOneUiGlassColors.current
    GlassCard(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .semantics {
                        liveRegion = androidx.compose.ui.semantics.LiveRegionMode.Polite
                        contentDescription = "Finding peer-matched rates"
                    },
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(PricingSpacing.Small),
        ) {
            CircularProgressIndicator(color = glass.primaryAccent)
            Text(
                text = "Finding peer-matched rates…",
                style = MaterialTheme.typography.bodyMedium,
                color = glass.textSecondary,
            )
        }
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
        verticalArrangement = Arrangement.spacedBy(PricingSpacing.Small),
    ) {
        InlineErrorText(message = message, modifier = Modifier.fillMaxWidth())
        PrimaryActionButton(
            text = "Try again",
            onClick = onRetry,
            contentDescription = "Retry calculation",
            modifier = Modifier.fillMaxWidth(),
        )
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
    val glass = LocalOneUiGlassColors.current

    GlassCard(modifier = Modifier.fillMaxWidth()) {
        Column(verticalArrangement = Arrangement.spacedBy(PricingSpacing.Medium)) {
            Text(
                text = "Complete your mentor profile",
                style = MaterialTheme.typography.titleMedium,
                color = glass.textPrimary,
            )
            Text(
                text = "Your profile links your Firebase account to your pricing quotes automatically.",
                style = MaterialTheme.typography.bodyMedium,
                color = glass.textSecondary,
            )
            GlassTextField(
                value = fullName,
                onValueChange = { fullName = it },
                label = "Full name",
                singleLine = true,
            )
            GlassTextField(
                value = email,
                onValueChange = { email = it },
                label = "Email",
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email),
                singleLine = true,
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
    }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
private fun ListingsTab(
    workspaceState: MentorWorkspaceState,
    onApplyListingToQuote: (SelfListingDTO) -> Unit,
    onSaveListing: (listingId: String, title: String, industryId: String, rawText: String, verifiedRate: Float) -> Unit,
) {
    var showListingSheet by remember { mutableStateOf(false) }
    var editingListingId by remember { mutableStateOf("") }
    var title by remember { mutableStateOf("") }
    var industryId by remember(workspaceState.industries) {
        mutableStateOf(workspaceState.industries.firstOrNull() ?: "mobile")
    }
    var rawText by remember { mutableStateOf("") }
    var verifiedRate by remember { mutableStateOf("2500") }
    var selectedIndustryFilter by remember { mutableStateOf("all") }
    val glass = LocalOneUiGlassColors.current

    val openCreateSheet = {
        editingListingId = ""
        title = ""
        industryId = workspaceState.industries.firstOrNull() ?: "mobile"
        rawText = ""
        verifiedRate = "2500"
        showListingSheet = true
    }

    val openEditSheet: (SelfListingDTO) -> Unit = { listing ->
        editingListingId = listing.listingId
        title = listing.title
        industryId = listing.industryId
        rawText = listing.rawText
        verifiedRate = listing.verifiedRate.roundToInt().toString()
        showListingSheet = true
    }

    if (showListingSheet) {
        val isEditing = editingListingId.isNotBlank()
        GlassModalBottomSheet(
            onDismissRequest = { showListingSheet = false },
            title = if (isEditing) "Edit service listing" else "Create service listing",
            actions = {
                GlassSecondaryButton(
                    text = "Keep Editing",
                    onClick = { showListingSheet = false },
                    modifier = Modifier.weight(1f),
                )
                PrimaryActionButton(
                    text = if (isEditing) "Update Listing" else "Save Service Listing",
                    onClick = {
                        onSaveListing(
                            editingListingId,
                            title,
                            industryId,
                            rawText,
                            verifiedRate.toFloatOrNull() ?: 1f,
                        )
                        editingListingId = ""
                        title = ""
                        rawText = ""
                        showListingSheet = false
                    },
                    enabled = title.isNotBlank() && rawText.trim().length >= 20,
                    modifier = Modifier.weight(1f),
                )
            },
        ) {
            Text(
                text = "Save a service once to generate future quotes in one tap.",
                style = MaterialTheme.typography.bodyMedium,
                color = glass.textSecondary,
            )
            GlassTextField(
                value = title,
                onValueChange = { title = it },
                label = "Listing title",
                singleLine = true,
            )
            IndustryDropdown(
                selectedIndustry = industryId,
                onIndustrySelected = { industryId = it },
                industries = workspaceState.industries,
            )
            val trimmedLen = rawText.trim().length
            GlassTextField(
                value = rawText,
                onValueChange = { rawText = it },
                label = "Service description",
                supportingText =
                    if (trimmedLen < 20) {
                        "Add at least ${20 - trimmedLen} more characters ($trimmedLen/20)."
                    } else {
                        "Ready to save ($trimmedLen characters)."
                    },
                singleLine = false,
                minLines = 3,
            )
            GlassTextField(
                value = verifiedRate,
                onValueChange = { verifiedRate = it },
                label = "Base rate (KES/hour)",
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                singleLine = true,
            )
        }
    }

    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            text = "Saved service listings (${workspaceState.listings.size})",
            style = MaterialTheme.typography.titleMedium,
            color = glass.textPrimary,
        )
        if (workspaceState.listings.isNotEmpty()) {
            GlassSecondaryButton(
                text = "Add Listing",
                onClick = openCreateSheet,
            )
        }
    }

    if (workspaceState.listings.isEmpty()) {
        OneUiEmptyStateCard(
            icon = Icons.Filled.Workspaces,
            title = "Build your service catalog",
            description = "Save your recurring mentorship offerings so you can pre-fill and calculate quotes in one tap.",
            actionLabel = "Create First Listing",
            onAction = openCreateSheet,
        )
    } else {
        val availableIndustries =
            remember(workspaceState.listings) {
                workspaceState.listings.map { it.industryId }.distinct()
            }
        if (availableIndustries.size > 1) {
            FlowRow(
                horizontalArrangement = Arrangement.spacedBy(PricingSpacing.Small),
                verticalArrangement = Arrangement.spacedBy(PricingSpacing.Small),
            ) {
                val filterOptions = listOf("all" to "All (${workspaceState.listings.size})") +
                    availableIndustries.map { id -> id to formatIndustryLabel(id) }
                filterOptions.forEach { (filterKey, label) ->
                    val selected = selectedIndustryFilter == filterKey
                    Box(
                        modifier =
                            Modifier
                                .clip(CircleShape)
                                .background(
                                    color =
                                        if (selected) {
                                            glass.primaryAccent.copy(alpha = 0.22f)
                                        } else {
                                            glass.recessedWellFill
                                        },
                                    shape = CircleShape,
                                ).border(
                                    width = 1.dp,
                                    color = if (selected) glass.primaryAccent else glass.recessedWellBorder,
                                    shape = CircleShape,
                                ).clickable(
                                    role = Role.Tab,
                                    onClick = { selectedIndustryFilter = filterKey },
                                ).padding(horizontal = 12.dp, vertical = 6.dp),
                    ) {
                        Text(
                            text = label,
                            style = MaterialTheme.typography.labelLarge,
                            color = if (selected) glass.primaryAccent else glass.textSecondary,
                        )
                    }
                }
            }
        }

        val displayedListings =
            remember(workspaceState.listings, selectedIndustryFilter) {
                if (selectedIndustryFilter == "all") {
                    workspaceState.listings
                } else {
                    workspaceState.listings.filter { it.industryId == selectedIndustryFilter }
                }
            }

        displayedListings.forEach { listing ->
            GlassCard(
                modifier = Modifier.fillMaxWidth(),
                onClick = { onApplyListingToQuote(listing) },
            ) {
                Column(verticalArrangement = Arrangement.spacedBy(PricingSpacing.Small)) {
                    Text(
                        text = listing.title,
                        style = MaterialTheme.typography.titleMedium,
                        color = glass.textPrimary,
                    )
                    GlassStatusBadge(
                        text = "${formatIndustryLabel(listing.industryId)} • ${formatKesRate(listing.verifiedRate)} KES/hour",
                        tint = glass.secondaryAccent,
                    )
                    Text(
                        text = listing.rawText,
                        style = MaterialTheme.typography.bodyMedium,
                        color = glass.textSecondary,
                    )
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(PricingSpacing.Small),
                    ) {
                        GlassSecondaryButton(
                            text = "Load Into Quote",
                            onClick = { onApplyListingToQuote(listing) },
                            modifier = Modifier.weight(1f),
                        )
                        GlassSecondaryButton(
                            text = "Edit",
                            onClick = { openEditSheet(listing) },
                            contentDescription = "Edit ${listing.title}",
                        )
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
private fun HistoryTab(
    workspaceState: MentorWorkspaceState,
    onSubmitFeedback: (transactionId: String, outcomeValue: String, actualRate: Float?, notes: String?) -> Unit,
    onApplyHistoryItemToQuote: (QuoteHistoryItemDTO) -> Unit = {},
    onStartNewQuote: () -> Unit = {},
) {
    var adjustingTxId by remember { mutableStateOf<String?>(null) }
    var adjustedRateInput by remember { mutableStateOf("") }
    var adjustedNotesInput by remember { mutableStateOf("") }
    val glass = LocalOneUiGlassColors.current

    adjustingTxId?.let { txId ->
        GlassModalBottomSheet(
            onDismissRequest = { adjustingTxId = null },
            title = "Report adjusted rate",
            actions = {
                GlassSecondaryButton(
                    text = "Keep Editing",
                    onClick = { adjustingTxId = null },
                    modifier = Modifier.weight(1f),
                )
                PrimaryActionButton(
                    text = "Save Adjusted Rate",
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
                    modifier = Modifier.weight(1f),
                )
            },
        ) {
            Text(
                text = "Sharing the final rate agreed with your client helps calibrate future peer benchmarks.",
                style = MaterialTheme.typography.bodyMedium,
                color = glass.textSecondary,
            )
            GlassTextField(
                value = adjustedRateInput,
                onValueChange = { adjustedRateInput = it },
                label = "Actual rate agreed (KES/hour)",
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                singleLine = true,
            )
            GlassTextField(
                value = adjustedNotesInput,
                onValueChange = { adjustedNotesInput = it },
                label = "Notes (optional)",
                singleLine = true,
            )
        }
    }

    var editingTxId by remember { mutableStateOf<String?>(null) }

    Text(
        text = "Quote history (${workspaceState.history.size})",
        style = MaterialTheme.typography.titleMedium,
        color = glass.textPrimary,
    )
    if (workspaceState.history.isEmpty()) {
        OneUiEmptyStateCard(
            icon = Icons.Filled.History,
            title = "No quotes recorded yet",
            description = "Once you calculate a rate, it appears here so you can track client outcomes and sharpen future recommendations.",
            actionLabel = "Create Your First Quote",
            onAction = onStartNewQuote,
        )
        return
    }

    HistoryAnalyticsSummaryCard(
        history = workspaceState.history,
        feedbackStatusByTx = workspaceState.feedbackStatusByTx,
    )

    workspaceState.history.forEach { item ->
        val recordedOutcome = workspaceState.feedbackStatusByTx[item.transactionId]
        val isEditing = editingTxId == item.transactionId || recordedOutcome == null
        val quotedRate = item.finalQuotedRate ?: 0f

        GlassCard(modifier = Modifier.fillMaxWidth()) {
            Column(verticalArrangement = Arrangement.spacedBy(PricingSpacing.Small)) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(
                        text = "${formatIndustryLabel(item.selectedIndustry ?: "general")} • ${formatKesRate(quotedRate)} KES/hour",
                        style = MaterialTheme.typography.titleMedium,
                        color = glass.textPrimary,
                        modifier = Modifier.weight(1f),
                    )
                    GlassSecondaryButton(
                        text = "Re-quote",
                        onClick = { onApplyHistoryItemToQuote(item) },
                        contentDescription = "Re-quote ${item.mentorCountryCode ?: "KE"} to ${item.clientCountryCode ?: "US"} corridor",
                    )
                }
                val dateLabel =
                    item.executedAt
                        ?.take(10)
                        ?.let { " • $it" }
                        .orEmpty()
                Text(
                    text = "Corridor: ${item.mentorCountryCode ?: "?"} -> ${item.clientCountryCode ?: "?"}$dateLabel",
                    style = MaterialTheme.typography.bodySmall,
                    color = glass.textMuted,
                )
                if (item.basePredictedRate != null) {
                    val surcharge = item.mpesaTariffSurcharge ?: 0f
                    Text(
                        text = "Take-home: ${formatKesRate(item.basePredictedRate)} KES/hr + ${formatKesRate(surcharge)} KES M-Pesa fee",
                        style = MaterialTheme.typography.bodySmall,
                        color = glass.textSecondary,
                    )
                }
                if (recordedOutcome != null && !isEditing) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        GlassStatusBadge(
                            text = "Feedback recorded: $recordedOutcome",
                            tint = glass.successTint,
                        )
                        androidx.compose.material3.TextButton(
                            onClick = { editingTxId = item.transactionId },
                        ) {
                            Text(text = "Update outcome", color = glass.primaryAccent)
                        }
                    }
                } else {
                    Text(
                        text = if (recordedOutcome != null) "Update outcome for this quote:" else "How did this quote go? Your feedback sharpens future rates.",
                        style = MaterialTheme.typography.bodySmall,
                        color = glass.textSecondary,
                    )
                    FlowRow(
                        horizontalArrangement = Arrangement.spacedBy(PricingSpacing.Small),
                        verticalArrangement = Arrangement.spacedBy(PricingSpacing.Small),
                    ) {
                        GlassSecondaryButton(
                            text = "Accepted",
                            onClick = {
                                editingTxId = null
                                onSubmitFeedback(item.transactionId, "accepted", null, null)
                            },
                        )
                        GlassSecondaryButton(
                            text = "Booked",
                            onClick = {
                                editingTxId = null
                                onSubmitFeedback(
                                    item.transactionId,
                                    "booked",
                                    item.finalQuotedRate,
                                    null,
                                )
                            },
                        )
                        GlassSecondaryButton(
                            text = "Adjusted",
                            onClick = {
                                editingTxId = null
                                adjustedRateInput =
                                    item.finalQuotedRate
                                        ?.toInt()
                                        ?.toString()
                                        .orEmpty()
                                adjustingTxId = item.transactionId
                            },
                        )
                        GlassSecondaryButton(
                            text = "Declined",
                            onClick = {
                                editingTxId = null
                                onSubmitFeedback(item.transactionId, "declined", null, null)
                            },
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun HistoryAnalyticsSummaryCard(
    history: List<QuoteHistoryItemDTO>,
    feedbackStatusByTx: Map<String, String>,
) {
    val glass = LocalOneUiGlassColors.current
    val quotedRates = history.mapNotNull { it.finalQuotedRate }
    val avgQuote = if (quotedRates.isNotEmpty()) quotedRates.average().toFloat() else 0f
    val topCorridor =
        history
            .mapNotNull { item ->
                val mentor = item.mentorCountryCode?.takeIf { it.isNotBlank() } ?: return@mapNotNull null
                val client = item.clientCountryCode?.takeIf { it.isNotBlank() } ?: return@mapNotNull null
                "$mentor -> $client"
            }.groupingBy { it }
            .eachCount()
            .maxByOrNull { it.value }
            ?.key
            ?: "KE -> US"

    val totalFeedback = feedbackStatusByTx.size
    val positiveCount =
        feedbackStatusByTx.values.count { outcome ->
            outcome.equals("accepted", ignoreCase = true) || outcome.equals("booked", ignoreCase = true)
        }
    val winRateLabel =
        if (totalFeedback > 0) {
            "${((positiveCount.toFloat() / totalFeedback) * 100f).roundToInt()}% ($positiveCount/$totalFeedback)"
        } else {
            "Log outcomes below"
        }

    GlassCard(modifier = Modifier.fillMaxWidth()) {
        Column(verticalArrangement = Arrangement.spacedBy(PricingSpacing.Small)) {
            Text(
                text = "Outcome analytics",
                style = MaterialTheme.typography.titleMedium,
                color = glass.textPrimary,
            )
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                Column {
                    Text(
                        text = "Average quote",
                        style = MaterialTheme.typography.bodySmall,
                        color = glass.textMuted,
                    )
                    Text(
                        text = "${formatKesRate(avgQuote)} KES/hr",
                        style = MaterialTheme.typography.bodyMedium,
                        color = glass.primaryAccent,
                    )
                }
                Column(horizontalAlignment = Alignment.End) {
                    Text(
                        text = "Top corridor",
                        style = MaterialTheme.typography.bodySmall,
                        color = glass.textMuted,
                    )
                    Text(
                        text = topCorridor,
                        style = MaterialTheme.typography.bodyMedium,
                        color = glass.textPrimary,
                    )
                }
            }
            GlassInsetDivider(startIndent = 0.dp)
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = "Client acceptance / booking rate",
                    style = MaterialTheme.typography.bodySmall,
                    color = glass.textSecondary,
                )
                GlassStatusBadge(
                    text = winRateLabel,
                    tint = if (totalFeedback > 0) glass.successTint else glass.infoTint,
                )
            }
        }
    }
}
