package edu.strathmore.pricing.ui.pricing.components

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
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
import edu.strathmore.pricing.ui.theme.PricingSpacing

/** Supported industry partitions, kept in sync with `SUPPORTED_INDUSTRY_PARTITIONS` server-side. */
val SupportedIndustries = listOf(
    "data_ai", "web_backend", "mobile", "devops_cloud",
    "design_creative", "product_management", "digital_marketing", "general_tech",
)

/**
 * `CapabilityInputForm` from the canonical Sprint 4 acceptance (issue #74): raw description,
 * industry selector and the bilateral country pair. Validation messages come from the ViewModel
 * (single source of truth); this composable only renders them.
 */
@Composable
fun CapabilityInputForm(
    rawDescription: String,
    onDescriptionChanged: (String) -> Unit,
    selectedIndustry: String,
    onIndustrySelected: (String) -> Unit,
    mentorCountry: String,
    onMentorCountryChanged: (String) -> Unit,
    clientCountry: String,
    onClientCountryChanged: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(modifier = modifier.fillMaxWidth()) {
        OutlinedTextField(
            value = rawDescription,
            onValueChange = onDescriptionChanged,
            label = { Text("Describe your service") },
            supportingText = { Text("Min 20 characters. Used only to compute a peer-matched rate.") },
            minLines = 3,
            modifier = Modifier
                .fillMaxWidth()
                .semantics { contentDescription = "Service description input" },
        )

        Spacer(modifier = Modifier.height(PricingSpacing.Medium))

        IndustryDropdown(selectedIndustry = selectedIndustry, onIndustrySelected = onIndustrySelected)

        Spacer(modifier = Modifier.height(PricingSpacing.Medium))

        OutlinedTextField(
            value = mentorCountry,
            onValueChange = { onMentorCountryChanged(it.take(2)) },
            label = { Text("Your country (ISO-2)") },
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Text),
            modifier = Modifier
                .fillMaxWidth()
                .semantics { contentDescription = "Your country ISO 2-letter code" },
        )

        Spacer(modifier = Modifier.height(PricingSpacing.Small))

        OutlinedTextField(
            value = clientCountry,
            onValueChange = { onClientCountryChanged(it.take(2)) },
            label = { Text("Client country (ISO-2)") },
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Text),
            modifier = Modifier
                .fillMaxWidth()
                .semantics { contentDescription = "Client country ISO 2-letter code" },
        )
    }
}

@OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)
@Composable
private fun IndustryDropdown(selectedIndustry: String, onIndustrySelected: (String) -> Unit) {
    var expanded by remember { mutableStateOf(false) }
    ExposedDropdownMenuBox(expanded = expanded, onExpandedChange = { expanded = it }) {
        OutlinedTextField(
            value = selectedIndustry,
            onValueChange = {},
            readOnly = true,
            label = { Text("Industry") },
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded) },
            modifier = Modifier
                .fillMaxWidth()
                .menuAnchor()
                .semantics { contentDescription = "Industry selector, currently $selectedIndustry" },
        )
        ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            SupportedIndustries.forEach { industry ->
                DropdownMenuItem(
                    text = { Text(industry) },
                    onClick = {
                        onIndustrySelected(industry)
                        expanded = false
                    },
                )
            }
        }
    }
}


