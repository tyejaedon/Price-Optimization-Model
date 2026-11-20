package dev.tyejaedon.pricing.admin.ui

import android.content.res.Configuration
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Key
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import dev.tyejaedon.pricing.admin.viewmodel.AdminSessionState
import dev.tyejaedon.pricing.admin.viewmodel.AdminViewModel
import dev.tyejaedon.pricing.designsystem.GlassCard
import dev.tyejaedon.pricing.designsystem.GlassPrimaryButton
import dev.tyejaedon.pricing.designsystem.GlassStatusBadge
import dev.tyejaedon.pricing.designsystem.GlassTextField
import dev.tyejaedon.pricing.designsystem.LocalOneUiGlassColors
import dev.tyejaedon.pricing.designsystem.OneUiGlassScaffold
import dev.tyejaedon.pricing.designsystem.OneUiGlassTheme
import dev.tyejaedon.pricing.designsystem.OneUiSpacing

@Composable
fun AdminAuthScreen(viewModel: AdminViewModel) {
    val sessionState by viewModel.sessionState.collectAsStateWithLifecycle()
    AdminAuthScreenContent(
        sessionState = sessionState,
        onUnlock = viewModel::unlock,
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AdminAuthScreenContent(
    sessionState: AdminSessionState,
    onUnlock: (String) -> Unit = {},
    initialToken: String = "",
) {
    var adminToken by remember { mutableStateOf(initialToken) }
    val glass = LocalOneUiGlassColors.current

    OneUiGlassScaffold(
        title = "MLOps & Admin Console",
    ) { padding ->
        Column(
            modifier =
                Modifier
                    .fillMaxSize()
                    .padding(padding)
                    .padding(horizontal = OneUiSpacing.Medium)
                    .verticalScroll(rememberScrollState())
                    .imePadding(),
            verticalArrangement = Arrangement.spacedBy(OneUiSpacing.Medium),
        ) {
            Text(
                text = "Enter your X-Admin-Token to manage model tuning, retraining, drift, and profiles.",
                style = MaterialTheme.typography.bodyLarge,
                color = glass.textSecondary,
            )

            Spacer(modifier = Modifier.height(OneUiSpacing.Small))

            GlassCard(modifier = Modifier.fillMaxWidth()) {
                Column(verticalArrangement = Arrangement.spacedBy(OneUiSpacing.Medium)) {
                    GlassTextField(
                        value = adminToken,
                        onValueChange = { adminToken = it },
                        label = "Administrator Token",
                        leadingIcon = {
                            Icon(
                                imageVector = Icons.Filled.Key,
                                contentDescription = null,
                                tint = glass.textSecondary,
                            )
                        },
                        visualTransformation = PasswordVisualTransformation(),
                        singleLine = true,
                    )
                    when (val state = sessionState) {
                        AdminSessionState.Locked, AdminSessionState.Unlocked -> Unit
                        AdminSessionState.Unlocking ->
                            CircularProgressIndicator(
                                modifier = Modifier.align(Alignment.CenterHorizontally),
                                color = glass.primaryAccent,
                            )
                        is AdminSessionState.Error ->
                            GlassStatusBadge(text = state.message, tint = glass.errorTint)
                    }
                    GlassPrimaryButton(
                        text = "Unlock Console",
                        onClick = { onUnlock(adminToken) },
                        enabled = adminToken.isNotBlank() && sessionState !is AdminSessionState.Unlocking,
                        modifier = Modifier.fillMaxWidth(),
                    )
                }
            }
            Spacer(modifier = Modifier.height(16.dp))
        }
    }
}

@Preview(name = "Locked - Light", showBackground = true)
@Composable
private fun AdminAuthScreenLockedLightPreview() {
    OneUiGlassTheme(darkTheme = false) {
        AdminAuthScreenContent(
            sessionState = AdminSessionState.Locked,
            initialToken = "adm_secret_token",
        )
    }
}

@Preview(name = "Unlocking", showBackground = true)
@Composable
private fun AdminAuthScreenUnlockingPreview() {
    OneUiGlassTheme(darkTheme = false) {
        AdminAuthScreenContent(
            sessionState = AdminSessionState.Unlocking,
            initialToken = "adm_secret_token",
        )
    }
}

@Preview(name = "Error - Dark", uiMode = Configuration.UI_MODE_NIGHT_YES, showBackground = true)
@Composable
private fun AdminAuthScreenErrorDarkPreview() {
    OneUiGlassTheme(darkTheme = true) {
        AdminAuthScreenContent(
            sessionState = AdminSessionState.Error("Invalid administrator token."),
            initialToken = "bad_token",
        )
    }
}
