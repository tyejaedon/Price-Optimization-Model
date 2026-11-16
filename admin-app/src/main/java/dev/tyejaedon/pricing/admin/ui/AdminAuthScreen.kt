package dev.tyejaedon.pricing.admin.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import dev.tyejaedon.pricing.admin.viewmodel.AdminSessionState
import dev.tyejaedon.pricing.admin.viewmodel.AdminViewModel

@Composable
fun AdminAuthScreen(viewModel: AdminViewModel) {
    val sessionState by viewModel.sessionState.collectAsStateWithLifecycle()
    var adminToken by remember { mutableStateOf("") }

    Scaffold { padding ->
        Column(
            modifier =
                Modifier
                    .fillMaxSize()
                    .padding(padding)
                    .padding(16.dp)
                    .imePadding(),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Text(text = "MLOps & Admin Console", style = MaterialTheme.typography.headlineSmall)
            Text(
                text = "Enter your X-Admin-Token to manage model tuning, retraining, drift, and profiles.",
                style = MaterialTheme.typography.bodyMedium,
            )
            OutlinedTextField(
                value = adminToken,
                onValueChange = { adminToken = it },
                label = { Text("Administrator Token") },
                visualTransformation = PasswordVisualTransformation(),
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            when (val state = sessionState) {
                AdminSessionState.Locked, AdminSessionState.Unlocked -> Unit
                AdminSessionState.Unlocking -> CircularProgressIndicator()
                is AdminSessionState.Error ->
                    Text(text = state.message, color = MaterialTheme.colorScheme.error)
            }
            Button(
                onClick = { viewModel.unlock(adminToken) },
                enabled = adminToken.isNotBlank() && sessionState !is AdminSessionState.Unlocking,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("Unlock Console")
            }
        }
    }
}
