package dev.tyejaedon.pricing.admin.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
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
import dev.tyejaedon.pricing.admin.viewmodel.AdminDashboardUiState
import dev.tyejaedon.pricing.admin.viewmodel.AdminTab
import dev.tyejaedon.pricing.admin.viewmodel.AdminViewModel

@OptIn(ExperimentalMaterial3Api::class)
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

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Pricing MLOps Console") },
                actions = {
                    TextButton(onClick = viewModel::refreshAll) { Text("Refresh") }
                    if (!demoMode) {
                        TextButton(onClick = viewModel::lock) { Text("Lock") }
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
                        onClick = { viewModel.selectTab(tab) },
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
                    AdminTab.MLOPS -> MlopsTab(state, viewModel)
                    AdminTab.DRIFT -> DriftTab(state)
                    AdminTab.PROFILES -> ProfilesTab(state, viewModel)
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
    viewModel: AdminViewModel,
) {
    var textWeight by remember(state.tuning) { mutableStateOf(state.tuning.textWeight.toString()) }
    var metadataWeight by remember(state.tuning) { mutableStateOf(state.tuning.metadataWeight.toString()) }
    var allowFallback by remember(state.tuning) { mutableStateOf(state.tuning.allowFallback) }

    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Grid Search Hyperparameters", style = MaterialTheme.typography.titleMedium)
            Text("kNeighbors: ${state.tuning.kNeighbors.joinToString(", ")}")
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
                    val tw = textWeight.toFloatOrNull() ?: state.tuning.textWeight
                    val mw = metadataWeight.toFloatOrNull() ?: state.tuning.metadataWeight
                    viewModel.updateTuning(
                        state.tuning.copy(
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
                Button(onClick = viewModel::triggerRetrain, modifier = Modifier.weight(1f)) {
                    Text("Trigger Retrain")
                }
                OutlinedButton(
                    onClick = viewModel::pollRetrainStatus,
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
    viewModel: AdminViewModel,
) {
    Button(onClick = viewModel::seedPlatformMentors, modifier = Modifier.fillMaxWidth()) {
        Text("Seed Platform Mentors")
    }
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("Mentor Profiles (${state.profiles.size})", style = MaterialTheme.typography.titleMedium)
            state.profiles.forEach { profile ->
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
