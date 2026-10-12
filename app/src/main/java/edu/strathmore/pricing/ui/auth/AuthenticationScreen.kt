package edu.strathmore.pricing.ui.auth

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
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
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import edu.strathmore.pricing.ui.components.InlineErrorText
import edu.strathmore.pricing.ui.components.PrimaryActionButton
import edu.strathmore.pricing.ui.theme.PricingSpacing
import edu.strathmore.pricing.viewmodel.AuthUiState
import edu.strathmore.pricing.viewmodel.AuthViewModel

@Composable
fun AuthenticationScreen(viewModel: AuthViewModel) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    var email by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }

    Column(
        modifier = Modifier.padding(PricingSpacing.Medium),
        verticalArrangement = Arrangement.spacedBy(PricingSpacing.Medium),
    ) {
        Text("Sign in to price your service", style = MaterialTheme.typography.headlineSmall)
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
            visualTransformation = PasswordVisualTransformation(),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
            singleLine = true,
            modifier = Modifier.fillMaxWidth().semantics { contentDescription = "Password" },
        )
        when (val state = uiState) {
            AuthUiState.SignedOut -> Unit
            AuthUiState.SigningIn -> CircularProgressIndicator()
            is AuthUiState.SignedIn -> Unit
            is AuthUiState.Error -> InlineErrorText(state.message)
        }
        PrimaryActionButton(
            text = "Sign in",
            onClick = { viewModel.signIn(email, password) },
            enabled = email.isNotBlank() && password.isNotBlank() && uiState !is AuthUiState.SigningIn,
            modifier = Modifier.fillMaxWidth(),
        )
    }
}
