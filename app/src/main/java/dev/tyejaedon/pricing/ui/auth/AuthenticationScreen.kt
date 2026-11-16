package dev.tyejaedon.pricing.ui.auth

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Visibility
import androidx.compose.material.icons.filled.VisibilityOff
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import dev.tyejaedon.pricing.ui.components.InlineErrorText
import dev.tyejaedon.pricing.ui.components.PrimaryActionButton
import dev.tyejaedon.pricing.ui.theme.PricingSpacing
import dev.tyejaedon.pricing.viewmodel.AuthUiState
import dev.tyejaedon.pricing.viewmodel.AuthViewModel

@Composable
fun AuthenticationScreen(viewModel: AuthViewModel) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    var email by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var passwordVisible by remember { mutableStateOf(false) }
    var isSignUpMode by remember { mutableStateOf(false) }

    Scaffold { padding ->
        Column(
            modifier =
                Modifier
                    .fillMaxSize()
                    .padding(padding)
                    .padding(PricingSpacing.Medium)
                    .verticalScroll(rememberScrollState())
                    .imePadding(),
            verticalArrangement = Arrangement.spacedBy(PricingSpacing.Medium),
        ) {
            Text(
                text = if (isSignUpMode) "Create your mentor account" else "Sign in to price your service",
                style = MaterialTheme.typography.headlineSmall,
            )
            OutlinedTextField(
                value = email,
                onValueChange = { email = it },
                label = { Text("Email") },
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email),
                singleLine = true,
                modifier = Modifier.fillMaxWidth().semantics { contentDescription = "Email address" },
            )
            OutlinedTextField(
                value = password,
                onValueChange = { password = it },
                label = { Text("Password") },
                supportingText = if (isSignUpMode) ({ Text("At least 6 characters.") }) else null,
                visualTransformation = if (passwordVisible) VisualTransformation.None else PasswordVisualTransformation(),
                trailingIcon = {
                    IconButton(onClick = { passwordVisible = !passwordVisible }) {
                        Icon(
                            imageVector = if (passwordVisible) Icons.Filled.VisibilityOff else Icons.Filled.Visibility,
                            contentDescription = if (passwordVisible) "Hide password" else "Show password",
                        )
                    }
                },
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                singleLine = true,
                modifier = Modifier.fillMaxWidth().semantics { contentDescription = "Password" },
            )
            when (val state = uiState) {
                AuthUiState.SignedOut -> Unit
                AuthUiState.SigningIn -> CircularProgressIndicator()
                is AuthUiState.SignedIn -> Unit
                is AuthUiState.Error -> InlineErrorText(state.message)
                is AuthUiState.PasswordResetSent ->
                    Text(
                        text = "Password reset email sent to ${state.email}.",
                        color = MaterialTheme.colorScheme.primary,
                        style = MaterialTheme.typography.bodyMedium,
                    )
            }
            PrimaryActionButton(
                text = if (isSignUpMode) "Create account" else "Sign in",
                onClick = {
                    if (isSignUpMode) {
                        viewModel.signUp(email, password)
                    } else {
                        viewModel.signIn(email, password)
                    }
                },
                enabled = email.isNotBlank() && password.isNotBlank() && uiState !is AuthUiState.SigningIn,
                modifier = Modifier.fillMaxWidth(),
            )
            if (!isSignUpMode) {
                TextButton(
                    onClick = { viewModel.sendPasswordReset(email) },
                    enabled = uiState !is AuthUiState.SigningIn,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text("Forgot password?")
                }
            }
            TextButton(
                onClick = { isSignUpMode = !isSignUpMode },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(
                    text =
                        if (isSignUpMode) {
                            "Already have an account? Sign in"
                        } else {
                            "Don't have an account? Create account"
                        },
                )
            }
        }
    }
}
