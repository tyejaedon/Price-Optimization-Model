package dev.tyejaedon.pricing.admin.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
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
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import dev.tyejaedon.pricing.admin.data.network.dto.GridSearchConfigDTO
import dev.tyejaedon.pricing.admin.viewmodel.AdminDashboardUiState
import dev.tyejaedon.pricing.admin.viewmodel.AdminTab
import dev.tyejaedon.pricing.admin.viewmodel.AdminViewModel

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
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Pricing MLOps Console") },
                actions = {
                    TextButton(onClick = onRefreshAll) { Text("Refresh") }
                    if (!demoMode) {
                        TextButton(onClick = onLock) { Text("Lock") }
                    }
                },
            )
        },
    ) { padding ->
        Column(
            modifier =
                Modifier
                    .fillMaxSize()
                    .padding(padding),
        ) {
            if (state.isLoading) {
                LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
            }
            TabRow(selectedTabIndex = state.selectedTab.ordinal) {
                AdminTab.entries.forEach { tab ->
                    Tab(
                        selected = state.selectedTab == tab,
                        onClick = { onSelectTab(tab) },
                        text = { Text(tab.label, maxLines = 1) },
                    )
                }
            }
            Column(
                modifier =
                    Modifier
                        .fillMaxSize()
                        .padding(16.dp)
                        .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                state.statusMessage?.let { Text(text = it, color = MaterialTheme.colorScheme.primary) }
                state.errorMessage?.let { Text(text = it, color = MaterialTheme.colorScheme.error) }

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
            }
        }
    }
}

@Composable
private fun OverviewTab(state: AdminDashboardUiState) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("Service Health", style = MaterialTheme.typography.titleMedium)
            Text("Status: ${state.health?.status ?: "Unknown"}")
            Text("Models Loaded: ${state.health?.modelsLoaded ?: false}")
            Text("Unit: ${state.health?.unit ?: "KES/hour"}")
        }
    }
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("Artifact Provenance", style = MaterialTheme.typography.titleMedium)
            Text("Version: ${state.artifacts?.artifactVersion ?: "Unavailable"}")
            Text("Dataset: ${state.artifacts?.datasetVersion ?: "Unavailable"}")
            Text("Validation: ${state.artifacts?.validationStatus ?: "Unavailable"}")
            state.artifacts?.loadError?.let { Text("Load error: $it", color = MaterialTheme.colorScheme.error) }
        }
    }
}

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

    if (confirmRetrain) {
        AlertDialog(
            onDismissRequest = { confirmRetrain = false },
            title = { Text("Trigger model retraining?") },
            text = { Text("This starts an asynchronous retraining job on the server.") },
            confirmButton = {
                TextButton(
                    onClick = {
                        confirmRetrain = false
                        onTriggerRetrain()
                    },
                ) {
                    Text("Start Retrain")
                }
            },
            dismissButton = {
                TextButton(onClick = { confirmRetrain = false }) { Text("Cancel") }
            },
        )
    }

    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Grid Search Hyperparameters", style = MaterialTheme.typography.titleMedium)
            OutlinedTextField(
                value = kNeighborsInput,
                onValueChange = { kNeighborsInput = it },
                label = { Text("kNeighbors (comma-separated)") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            OutlinedTextField(
                value = textWeight,
                onValueChange = { textWeight = it },
                label = { Text("Text weight") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            OutlinedTextField(
                value = metadataWeight,
                onValueChange = { metadataWeight = it },
                label = { Text("Metadata weight") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceBetween) {
                Text("Allow partition fallback", modifier = Modifier.weight(1f))
                Switch(checked = allowFallback, onCheckedChange = { allowFallback = it })
            }
            Button(
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
            ) {
                Text("Save Tuning")
            }
        }
    }

    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Model Retraining", style = MaterialTheme.typography.titleMedium)
            state.retrainStatus?.let {
                Text("Job ${it.jobId}: ${it.status}")
                it.artifactVersion?.let { ver -> Text("Artifact: $ver") }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = { confirmRetrain = true }, modifier = Modifier.weight(1f)) {
                    Text("Trigger Retrain")
                }
                OutlinedButton(
                    onClick = onPollRetrainStatus,
                    enabled = state.retrainStatus != null,
                    modifier = Modifier.weight(1f),
                ) {
                    Text("Poll Status")
                }
            }
        }
    }
}

@Composable
private fun DriftTab(state: AdminDashboardUiState) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("Distribution Drift Summary", style = MaterialTheme.typography.titleMedium)
            Text("Total Transactions: ${state.drift?.totalTransactions ?: 0}")
            Text("Avg Quoted Rate: ${state.drift?.averageFinalRate ?: 0f} KES/hour")
            state.drift?.byIndustry?.forEach { (industry, count) ->
                Text("• $industry: $count")
            }
            state.drift?.byCorridor?.forEach { (corridor, count) ->
                Text("• Corridor $corridor: $count")
            }
        }
    }

    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("Quote Outcome Feedback (${state.feedback.size})", style = MaterialTheme.typography.titleMedium)
            state.feedback.forEach { item ->
                Text("${item.transactionId}: ${item.outcome} (${item.actualRate ?: "-"} KES)")
            }
        }
    }
}

@Composable
private fun ProfilesTab(
    state: AdminDashboardUiState,
    onSeedPlatformMentors: () -> Unit,
) {
    var confirmSeed by remember { mutableStateOf(false) }
    var searchQuery by remember { mutableStateOf("") }

    if (confirmSeed) {
        AlertDialog(
            onDismissRequest = { confirmSeed = false },
            title = { Text("Seed platform mentors?") },
            text = { Text("This will upsert platform mentor profiles from the corpus into the repository.") },
            confirmButton = {
                TextButton(
                    onClick = {
                        confirmSeed = false
                        onSeedPlatformMentors()
                    },
                ) {
                    Text("Seed Mentors")
                }
            },
            dismissButton = {
                TextButton(onClick = { confirmSeed = false }) { Text("Cancel") }
            },
        )
    }

    Button(onClick = { confirmSeed = true }, modifier = Modifier.fillMaxWidth()) {
        Text("Seed Platform Mentors")
    }
    OutlinedTextField(
        value = searchQuery,
        onValueChange = { searchQuery = it },
        label = { Text("Filter profiles by name, ID, or country") },
        singleLine = true,
        modifier = Modifier.fillMaxWidth(),
    )
    val filteredProfiles =
        state.profiles.filter { profile ->
            val q = searchQuery.trim()
            q.isBlank() ||
                profile.fullName.contains(q, ignoreCase = true) ||
                profile.profileId.contains(q, ignoreCase = true) ||
                profile.countryCode.contains(q, ignoreCase = true)
        }
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("Mentor Profiles (${filteredProfiles.size})", style = MaterialTheme.typography.titleMedium)
            filteredProfiles.forEach { profile ->
                Text("${profile.fullName} (${profile.profileId}) — ${profile.countryCode}")
            }
        }
    }
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("Recent Quote Audits (${state.history.size})", style = MaterialTheme.typography.titleMedium)
            state.history.forEach { tx ->
                Text("${tx.transactionId}: ${tx.selectedIndustry ?: "-"} (${tx.finalQuotedRate ?: 0f} KES)")
            }
        }
    }
}
