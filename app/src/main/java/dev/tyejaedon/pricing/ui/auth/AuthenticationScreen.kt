package dev.tyejaedon.pricing.ui.auth

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
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Email
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.Visibility
import androidx.compose.material.icons.filled.VisibilityOff
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import dev.tyejaedon.pricing.designsystem.GlassCard
import dev.tyejaedon.pricing.designsystem.GlassStatusBadge
import dev.tyejaedon.pricing.designsystem.GlassTextField
import dev.tyejaedon.pricing.designsystem.LocalOneUiGlassColors
import dev.tyejaedon.pricing.designsystem.OneUiGlassScaffold
import dev.tyejaedon.pricing.ui.components.InlineErrorText
import dev.tyejaedon.pricing.ui.components.PrimaryActionButton
import dev.tyejaedon.pricing.ui.theme.PricingSpacing
import dev.tyejaedon.pricing.ui.theme.PricingTheme
import dev.tyejaedon.pricing.viewmodel.AuthUiState
import dev.tyejaedon.pricing.viewmodel.AuthViewModel

@Composable
fun AuthenticationScreen(viewModel: AuthViewModel) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    AuthenticationScreenContent(
        uiState = uiState,
        onSignIn = viewModel::signIn,
        onSignUp = viewModel::signUp,
        onSendPasswordReset = viewModel::sendPasswordReset,
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AuthenticationScreenContent(
    uiState: AuthUiState,
    onSignIn: (email: String, password: String) -> Unit = { _, _ -> },
    onSignUp: (email: String, password: String) -> Unit = { _, _ -> },
    onSendPasswordReset: (email: String) -> Unit = {},
    initialEmail: String = "",
    initialSignUpMode: Boolean = false,
) {
    var email by remember { mutableStateOf(initialEmail) }
    var password by remember { mutableStateOf("") }
    var passwordVisible by remember { mutableStateOf(false) }
    var isSignUpMode by remember { mutableStateOf(initialSignUpMode) }
    val glass = LocalOneUiGlassColors.current

    OneUiGlassScaffold(
        title = if (isSignUpMode) "Create mentor account" else "Sign in to price your service",
    ) { padding ->
        Column(
            modifier =
                Modifier
                    .fillMaxSize()
                    .padding(padding)
                    .padding(horizontal = PricingSpacing.Medium)
                    .verticalScroll(rememberScrollState())
                    .imePadding(),
            verticalArrangement = Arrangement.spacedBy(PricingSpacing.Medium),
        ) {
            Text(
                text = "Peer-backed hourly rate optimization with transparent M-Pesa corridor pricing.",
                style = MaterialTheme.typography.bodyLarge,
                color = glass.textSecondary,
            )

            Spacer(modifier = Modifier.height(PricingSpacing.Small))

            GlassCard(modifier = Modifier.fillMaxWidth()) {
                Column(verticalArrangement = Arrangement.spacedBy(PricingSpacing.Medium)) {
                    GlassTextField(
                        value = email,
                        onValueChange = { email = it },
                        label = "Email",
                        leadingIcon = {
                            Icon(
                                imageVector = Icons.Filled.Email,
                                contentDescription = null,
                                tint = glass.textSecondary,
                            )
                        },
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email),
                        singleLine = true,
                        textFieldModifier = Modifier.semantics { contentDescription = "Email address" },
                    )
                    GlassTextField(
                        value = password,
                        onValueChange = { password = it },
                        label = "Password",
                        supportingText = if (isSignUpMode) "At least 6 characters." else null,
                        leadingIcon = {
                            Icon(
                                imageVector = Icons.Filled.Lock,
                                contentDescription = null,
                                tint = glass.textSecondary,
                            )
                        },
                        visualTransformation =
                            if (passwordVisible) VisualTransformation.None else PasswordVisualTransformation(),
                        trailingIcon = {
                            IconButton(onClick = { passwordVisible = !passwordVisible }) {
                                Icon(
                                    imageVector =
                                        if (passwordVisible) Icons.Filled.VisibilityOff else Icons.Filled.Visibility,
                                    contentDescription = if (passwordVisible) "Hide password" else "Show password",
                                    tint = glass.textSecondary,
                                )
                            }
                        },
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                        singleLine = true,
                        textFieldModifier = Modifier.semantics { contentDescription = "Password" },
                    )
                    when (val state = uiState) {
                        AuthUiState.SignedOut -> Unit
                        AuthUiState.SigningIn ->
                            CircularProgressIndicator(
                                modifier = Modifier.align(Alignment.CenterHorizontally),
                                color = glass.primaryAccent,
                            )
                        is AuthUiState.SignedIn -> Unit
                        is AuthUiState.Error -> InlineErrorText(state.message, modifier = Modifier.fillMaxWidth())
                        is AuthUiState.PasswordResetSent ->
                            GlassStatusBadge(
                                text = "Password reset email sent to ${state.email}.",
                                tint = glass.successTint,
                            )
                    }
                    PrimaryActionButton(
                        text = if (isSignUpMode) "Create account" else "Sign in",
                        onClick = {
                            if (isSignUpMode) {
                                onSignUp(email, password)
                            } else {
                                onSignIn(email, password)
                            }
                        },
                        enabled = email.isNotBlank() && password.isNotBlank() && uiState !is AuthUiState.SigningIn,
                        modifier = Modifier.fillMaxWidth(),
                    )
                }
            }

            if (!isSignUpMode) {
                TextButton(
                    onClick = { onSendPasswordReset(email) },
                    enabled = uiState !is AuthUiState.SigningIn,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text("Forgot password?", color = glass.primaryAccent)
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
                    color = glass.textSecondary,
                )
            }
            Spacer(modifier = Modifier.height(16.dp))
        }
    }
}

@Preview(name = "Sign In - Light", showBackground = true)
@Composable
private fun AuthenticationScreenSignInLightPreview() {
    PricingTheme(darkTheme = false) {
        AuthenticationScreenContent(
            uiState = AuthUiState.SignedOut,
            initialEmail = "mentor@strathmore.edu",
        )
    }
}

@Preview(name = "Sign Up - Light", showBackground = true)
@Composable
private fun AuthenticationScreenSignUpPreview() {
    PricingTheme(darkTheme = false) {
        AuthenticationScreenContent(
            uiState = AuthUiState.SignedOut,
            initialSignUpMode = true,
        )
    }
}

@Preview(name = "Signing In", showBackground = true)
@Composable
private fun AuthenticationScreenSigningInPreview() {
    PricingTheme(darkTheme = false) {
        AuthenticationScreenContent(
            uiState = AuthUiState.SigningIn,
            initialEmail = "mentor@strathmore.edu",
        )
    }
}

@Preview(name = "Error - Dark", uiMode = Configuration.UI_MODE_NIGHT_YES, showBackground = true)
@Composable
private fun AuthenticationScreenErrorDarkPreview() {
    PricingTheme(darkTheme = true) {
        AuthenticationScreenContent(
            uiState = AuthUiState.Error("Invalid email or password."),
            initialEmail = "mentor@strathmore.edu",
        )
    }
}
