package dev.tyejaedon.pricing.admin.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Analytics
import androidx.compose.material.icons.filled.Group
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
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
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import dev.tyejaedon.pricing.admin.data.network.dto.GridSearchConfigDTO
import dev.tyejaedon.pricing.admin.viewmodel.AdminDashboardUiState
import dev.tyejaedon.pricing.admin.viewmodel.AdminTab
import dev.tyejaedon.pricing.admin.viewmodel.AdminViewModel
import dev.tyejaedon.pricing.designsystem.GlassCard
import dev.tyejaedon.pricing.designsystem.GlassFloatingNavDock
import dev.tyejaedon.pricing.designsystem.GlassInsetDivider
import dev.tyejaedon.pricing.designsystem.GlassModalBottomSheet
import dev.tyejaedon.pricing.designsystem.GlassPrimaryButton
import dev.tyejaedon.pricing.designsystem.GlassSecondaryButton
import dev.tyejaedon.pricing.designsystem.GlassStatusBadge
import dev.tyejaedon.pricing.designsystem.GlassSwitch
import dev.tyejaedon.pricing.designsystem.GlassTextField
import dev.tyejaedon.pricing.designsystem.LocalOneUiGlassColors
import dev.tyejaedon.pricing.designsystem.OneUiEmptyStateCard
import dev.tyejaedon.pricing.designsystem.OneUiGlassScaffold
import dev.tyejaedon.pricing.designsystem.OneUiSpacing

@Composable
fun AdminDashboardScreen(
    viewModel: AdminViewModel,
    demoMode: Boolean = false,
) {
    val state by viewModel.dashboardState.collectAsStateWithLifecycle()

    LaunchedEffect(demoMode) {
        if (demoMode) {
            viewModel.refreshAll()
        }
    }

    AdminDashboardScreenContent(
        state = state,
        demoMode = demoMode,
        onRefreshAll = viewModel::refreshAll,
        onLock = viewModel::lock,
        onSelectTab = viewModel::selectTab,
        onUpdateTuning = viewModel::updateTuning,
        onTriggerRetrain = viewModel::triggerRetrain,
        onPollRetrainStatus = viewModel::pollRetrainStatus,
        onSeedPlatformMentors = viewModel::seedPlatformMentors,
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AdminDashboardScreenContent(
    state: AdminDashboardUiState,
    demoMode: Boolean = false,
    onRefreshAll: () -> Unit = {},
    onLock: () -> Unit = {},
    onSelectTab: (AdminTab) -> Unit = {},
    onUpdateTuning: (GridSearchConfigDTO) -> Unit = {},
    onTriggerRetrain: () -> Unit = {},
    onPollRetrainStatus: () -> Unit = {},
    onSeedPlatformMentors: () -> Unit = {},
) {
    val glass = LocalOneUiGlassColors.current
    OneUiGlassScaffold(
        title = "Pricing MLOps Console",
        actions = {
            Row(horizontalArrangement = Arrangement.spacedBy(OneUiSpacing.Small)) {
                GlassSecondaryButton(text = "Sync Now", onClick = onRefreshAll)
                if (!demoMode) {
                    GlassSecondaryButton(text = "Lock", onClick = onLock)
                }
            }
        },
        bottomBar = {
            GlassFloatingNavDock(
                items = AdminTab.entries,
                selectedItem = state.selectedTab,
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
                    .padding(horizontal = OneUiSpacing.Medium)
                    .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(OneUiSpacing.Medium),
        ) {
            if (state.isLoading) {
                LinearProgressIndicator(
                    modifier = Modifier.fillMaxWidth(),
                    color = glass.primaryAccent,
                    trackColor = glass.recessedWellFill,
                )
            }
            state.statusMessage?.let {
                GlassStatusBadge(text = it, tint = glass.successTint)
            }
            state.errorMessage?.let {
                GlassStatusBadge(text = it, tint = glass.errorTint)
            }

            when (state.selectedTab) {
                AdminTab.OVERVIEW -> OverviewTab(state)
                AdminTab.MLOPS ->
                    MlopsTab(
                        state = state,
                        onUpdateTuning = onUpdateTuning,
                        onTriggerRetrain = onTriggerRetrain,
                        onPollRetrainStatus = onPollRetrainStatus,
                    )
                AdminTab.DRIFT -> DriftTab(state)
                AdminTab.PROFILES ->
                    ProfilesTab(
                        state = state,
                        onSeedPlatformMentors = onSeedPlatformMentors,
                    )
            }
            Spacer(modifier = Modifier.height(OneUiSpacing.Medium))
        }
    }
}

@Composable
private fun OverviewTab(state: AdminDashboardUiState) {
    val glass = LocalOneUiGlassColors.current
    GlassCard(modifier = Modifier.fillMaxWidth()) {
        Column(verticalArrangement = Arrangement.spacedBy(OneUiSpacing.Small)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text("Service Health", style = MaterialTheme.typography.titleMedium, color = glass.textPrimary)
                GlassStatusBadge(
                    text = state.health?.status ?: "Unknown",
                    tint = if (state.health?.modelsLoaded == true) glass.successTint else glass.warningTint,
                )
            }
            GlassInsetDivider(startIndent = 0.dp)
            Text("Status: ${state.health?.status ?: "Unknown"}", color = glass.textSecondary)
            Text("Models Loaded: ${state.health?.modelsLoaded ?: false}", color = glass.textSecondary)
            Text("Unit: ${state.health?.unit ?: "KES/hour"}", color = glass.textSecondary)
        }
    }
    GlassCard(modifier = Modifier.fillMaxWidth()) {
        Column(verticalArrangement = Arrangement.spacedBy(OneUiSpacing.Small)) {
            Text("Artifact Provenance", style = MaterialTheme.typography.titleMedium, color = glass.textPrimary)
            GlassInsetDivider(startIndent = 0.dp)
            Text("Version: ${state.artifacts?.artifactVersion ?: "Unavailable"}", color = glass.textSecondary)
            Text("Dataset: ${state.artifacts?.datasetVersion ?: "Unavailable"}", color = glass.textSecondary)
            Text("Validation: ${state.artifacts?.validationStatus ?: "Unavailable"}", color = glass.textSecondary)
            state.artifacts?.loadError?.let {
                GlassStatusBadge(text = "Load error: $it", tint = glass.errorTint)
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun MlopsTab(
    state: AdminDashboardUiState,
    onUpdateTuning: (GridSearchConfigDTO) -> Unit,
    onTriggerRetrain: () -> Unit,
    onPollRetrainStatus: () -> Unit,
) {
    var kNeighborsInput by remember(state.tuning) { mutableStateOf(state.tuning.kNeighbors.joinToString(", ")) }
    var textWeight by remember(state.tuning) { mutableStateOf(state.tuning.textWeight.toString()) }
    var metadataWeight by remember(state.tuning) { mutableStateOf(state.tuning.metadataWeight.toString()) }
    var allowFallback by remember(state.tuning) { mutableStateOf(state.tuning.allowFallback) }
    var confirmRetrain by remember { mutableStateOf(false) }
    val glass = LocalOneUiGlassColors.current

    if (confirmRetrain) {
        GlassModalBottomSheet(
            onDismissRequest = { confirmRetrain = false },
            title = "Trigger model retraining?",
            actions = {
                GlassSecondaryButton(
                    text = "Keep Editing",
                    onClick = { confirmRetrain = false },
                    modifier = Modifier.weight(1f),
                )
                GlassPrimaryButton(
                    text = "Start Retrain",
                    onClick = {
                        confirmRetrain = false
                        onTriggerRetrain()
                    },
                    modifier = Modifier.weight(1f),
                )
            },
        ) {
            Text(
                text = "This starts a background retraining job using the latest verified listings and quote feedback.",
                style = MaterialTheme.typography.bodyLarge,
                color = glass.textSecondary,
            )
        }
    }

    GlassCard(modifier = Modifier.fillMaxWidth()) {
        Column(verticalArrangement = Arrangement.spacedBy(OneUiSpacing.Medium)) {
            Text("Grid Search Hyperparameters", style = MaterialTheme.typography.titleMedium, color = glass.textPrimary)
            GlassTextField(
                value = kNeighborsInput,
                onValueChange = { kNeighborsInput = it },
                label = "kNeighbors (comma-separated)",
                singleLine = true,
            )
            GlassTextField(
                value = textWeight,
                onValueChange = { textWeight = it },
                label = "Text weight",
                singleLine = true,
            )
            GlassTextField(
                value = metadataWeight,
                onValueChange = { metadataWeight = it },
                label = "Metadata weight",
                singleLine = true,
            )
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                Text(
                    text = "Allow partition fallback",
                    color = glass.textPrimary,
                    style = MaterialTheme.typography.bodyLarge,
                    modifier = Modifier.weight(1f),
                )
                GlassSwitch(checked = allowFallback, onCheckedChange = { allowFallback = it })
            }
            GlassPrimaryButton(
                text = "Save Tuning",
                onClick = {
                    val parsedK =
                        kNeighborsInput
                            .split(",")
                            .mapNotNull { it.trim().toIntOrNull() }
                            .filter { it in 1..500 }
                            .distinct()
                            .sorted()
                            .ifEmpty { state.tuning.kNeighbors }
                    val tw = textWeight.toFloatOrNull() ?: state.tuning.textWeight
                    val mw = metadataWeight.toFloatOrNull() ?: state.tuning.metadataWeight
                    onUpdateTuning(
                        state.tuning.copy(
                            kNeighbors = parsedK,
                            textWeight = tw,
                            metadataWeight = mw,
                            allowFallback = allowFallback,
                        ),
                    )
                },
                modifier = Modifier.fillMaxWidth(),
            )
        }
    }

    GlassCard(modifier = Modifier.fillMaxWidth()) {
        Column(verticalArrangement = Arrangement.spacedBy(OneUiSpacing.Medium)) {
            Text("Model Retraining", style = MaterialTheme.typography.titleMedium, color = glass.textPrimary)
            state.retrainStatus?.let {
                GlassStatusBadge(text = "Job ${it.jobId}: ${it.status}", tint = glass.infoTint)
                it.artifactVersion?.let { ver -> Text("Artifact: $ver", color = glass.textSecondary) }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(OneUiSpacing.Small)) {
                GlassPrimaryButton(
                    text = "Trigger Retrain",
                    onClick = { confirmRetrain = true },
                    modifier = Modifier.weight(1f),
                )
                GlassSecondaryButton(
                    text = "Poll Status",
                    onClick = onPollRetrainStatus,
                    enabled = state.retrainStatus != null,
                    modifier = Modifier.weight(1f),
                )
            }
        }
    }
}

@Composable
private fun DriftTab(state: AdminDashboardUiState) {
    val glass = LocalOneUiGlassColors.current
    GlassCard(modifier = Modifier.fillMaxWidth()) {
        Column(verticalArrangement = Arrangement.spacedBy(OneUiSpacing.Small)) {
            Text("Distribution Drift Summary", style = MaterialTheme.typography.titleMedium, color = glass.textPrimary)
            GlassInsetDivider(startIndent = 0.dp)
            Text("Total Transactions: ${state.drift?.totalTransactions ?: 0}", color = glass.textSecondary)
            Text("Avg Quoted Rate: ${state.drift?.averageFinalRate ?: 0f} KES/hour", color = glass.textSecondary)
            state.drift?.byIndustry?.forEach { (industry, count) ->
                Text("• $industry: $count", color = glass.textSecondary)
            }
            state.drift?.byCorridor?.forEach { (corridor, count) ->
                Text("• Corridor $corridor: $count", color = glass.textSecondary)
            }
        }
    }

    if (state.feedback.isEmpty()) {
        OneUiEmptyStateCard(
            icon = Icons.Filled.Analytics,
            title = "No quote feedback yet",
            description = "Mentor feedback on accepted, booked, adjusted, or declined quotes will appear here.",
        )
    } else {
        GlassCard(modifier = Modifier.fillMaxWidth()) {
            Column(verticalArrangement = Arrangement.spacedBy(OneUiSpacing.Small)) {
                Text(
                    text = "Quote Outcome Feedback (${state.feedback.size})",
                    style = MaterialTheme.typography.titleMedium,
                    color = glass.textPrimary,
                )
                GlassInsetDivider(startIndent = 0.dp)
                state.feedback.forEach { item ->
                    Text(
                        text = "${item.transactionId}: ${item.outcome} (${item.actualRate ?: "-"} KES)",
                        color = glass.textSecondary,
                    )
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ProfilesTab(
    state: AdminDashboardUiState,
    onSeedPlatformMentors: () -> Unit,
) {
    var confirmSeed by remember { mutableStateOf(false) }
    var searchQuery by remember { mutableStateOf("") }
    val glass = LocalOneUiGlassColors.current

    if (confirmSeed) {
        GlassModalBottomSheet(
            onDismissRequest = { confirmSeed = false },
            title = "Seed platform mentors?",
            actions = {
                GlassSecondaryButton(
                    text = "Keep Editing",
                    onClick = { confirmSeed = false },
                    modifier = Modifier.weight(1f),
                )
                GlassPrimaryButton(
                    text = "Seed Mentors",
                    onClick = {
                        confirmSeed = false
                        onSeedPlatformMentors()
                    },
                    modifier = Modifier.weight(1f),
                )
            },
        ) {
            Text(
                text = "This imports baseline mentor profiles from the verified corpus so pricing has immediate peer coverage.",
                style = MaterialTheme.typography.bodyLarge,
                color = glass.textSecondary,
            )
        }
    }

    GlassPrimaryButton(
        text = "Seed Platform Mentors",
        onClick = { confirmSeed = true },
        modifier = Modifier.fillMaxWidth(),
    )
    GlassTextField(
        value = searchQuery,
        onValueChange = { searchQuery = it },
        label = "Filter profiles by name, ID, or country",
        leadingIcon = {
            Icon(
                imageVector = Icons.Filled.Search,
                contentDescription = null,
                tint = glass.textSecondary,
            )
        },
        singleLine = true,
    )
    val filteredProfiles =
        state.profiles.filter { profile ->
            val q = searchQuery.trim()
            q.isBlank() ||
                profile.fullName.contains(q, ignoreCase = true) ||
                profile.profileId.contains(q, ignoreCase = true) ||
                profile.countryCode.contains(q, ignoreCase = true)
        }
    if (filteredProfiles.isEmpty()) {
        OneUiEmptyStateCard(
            icon = Icons.Filled.Group,
            title = "No matching mentor profiles",
            description = "Try clearing your search filter or seed platform mentors to populate the directory.",
        )
    } else {
        GlassCard(modifier = Modifier.fillMaxWidth()) {
            Column(verticalArrangement = Arrangement.spacedBy(OneUiSpacing.Small)) {
                Text(
                    text = "Mentor Profiles (${filteredProfiles.size})",
                    style = MaterialTheme.typography.titleMedium,
                    color = glass.textPrimary,
                )
                GlassInsetDivider(startIndent = 0.dp)
                filteredProfiles.forEach { profile ->
                    Text(
                        text = "${profile.fullName} (${profile.profileId}) — ${profile.countryCode}",
                        color = glass.textSecondary,
                    )
                }
            }
        }
    }
    GlassCard(modifier = Modifier.fillMaxWidth()) {
        Column(verticalArrangement = Arrangement.spacedBy(OneUiSpacing.Small)) {
            Text(
                text = "Recent Quote Audits (${state.history.size})",
                style = MaterialTheme.typography.titleMedium,
                color = glass.textPrimary,
            )
            GlassInsetDivider(startIndent = 0.dp)
            state.history.forEach { tx ->
                Text(
                    text = "${tx.transactionId}: ${tx.selectedIndustry ?: "-"} (${tx.finalQuotedRate ?: 0f} KES)",
                    color = glass.textSecondary,
                )
            }
        }
    }
}
