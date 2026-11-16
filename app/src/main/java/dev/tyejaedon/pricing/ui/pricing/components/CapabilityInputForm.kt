package dev.tyejaedon.pricing.ui.pricing.components

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
import dev.tyejaedon.pricing.ui.theme.PricingSpacing
import java.util.Locale

/** Supported industry partitions, kept in sync with `SUPPORTED_INDUSTRY_PARTITIONS` server-side. */
val SupportedIndustries =
    listOf(
        "data_ai",
        "web_backend",
        "mobile",
        "devops_cloud",
        "design_creative",
        "product_management",
        "digital_marketing",
        "general_tech",
    )

fun formatIndustryLabel(key: String): String =
    when (key) {
        "data_ai" -> "Data & AI"
        "web_backend" -> "Web & Backend"
        "mobile" -> "Mobile Development"
        "devops_cloud" -> "DevOps & Cloud"
        "design_creative" -> "Design & Creative"
        "product_management" -> "Product Management"
        "digital_marketing" -> "Digital Marketing"
        "general_tech" -> "General Tech"
        else ->
            key
                .split("_")
                .filter { it.isNotBlank() }
                .joinToString(" ") { part ->
                    part.replaceFirstChar { ch -> ch.uppercase(Locale.getDefault()) }
                }
    }

/**
 * `CapabilityInputForm` from the canonical Sprint 4 acceptance (issue #74): raw description,
 * industry selector and the bilateral country pair. Validation messages come from the ViewModel
 * (single source of truth); this composable only renders them.
 */
@Composable
fun CapabilityInputForm(
    rawDescription: String,
    onDescriptionChanged: (String) -> Unit,
    mentorId: String,
    onMentorIdChanged: (String) -> Unit,
    selectedIndustry: String,
    onIndustrySelected: (String) -> Unit,
    industries: List<String> = SupportedIndustries,
    mentorCountry: String,
    onMentorCountryChanged: (String) -> Unit,
    clientCountry: String,
    onClientCountryChanged: (String) -> Unit,
    baseRateFloor: String,
    onBaseRateFloorChanged: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(modifier = modifier.fillMaxWidth()) {
        OutlinedTextField(
            value = rawDescription,
            onValueChange = onDescriptionChanged,
            label = { Text("Describe your service") },
            supportingText = { Text("Min 20 characters. Used only to compute a peer-matched rate.") },
            minLines = 3,
            modifier =
                Modifier
                    .fillMaxWidth()
                    .semantics { contentDescription = "Service description input" },
        )

        Spacer(modifier = Modifier.height(PricingSpacing.Medium))

        IndustryDropdown(
            selectedIndustry = selectedIndustry,
            onIndustrySelected = onIndustrySelected,
            industries = industries,
        )

        Spacer(modifier = Modifier.height(PricingSpacing.Medium))

        CountryDropdown(
            label = "Your country",
            selectedCode = mentorCountry,
            onCountrySelected = onMentorCountryChanged,
            contentDescriptionText = "Your country ISO 2-letter code",
        )

        Spacer(modifier = Modifier.height(PricingSpacing.Small))

        CountryDropdown(
            label = "Client country",
            selectedCode = clientCountry,
            onCountrySelected = onClientCountryChanged,
            contentDescriptionText = "Client country ISO 2-letter code",
        )

        Spacer(modifier = Modifier.height(PricingSpacing.Small))

        OutlinedTextField(
            value = baseRateFloor,
            onValueChange = onBaseRateFloorChanged,
            label = { Text("Minimum base rate (KES/hour, optional)") },
            supportingText = { Text("Does not include the M-Pesa fee.") },
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
    }
}

@OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)
@Composable
fun IndustryDropdown(
    selectedIndustry: String,
    onIndustrySelected: (String) -> Unit,
    industries: List<String>,
    modifier: Modifier = Modifier,
) {
    var expanded by remember { mutableStateOf(false) }
    ExposedDropdownMenuBox(expanded = expanded, onExpandedChange = { expanded = it }, modifier = modifier) {
        OutlinedTextField(
            value = if (selectedIndustry.isBlank()) "" else formatIndustryLabel(selectedIndustry),
            onValueChange = {},
            readOnly = true,
            label = { Text("Industry") },
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded) },
            modifier =
                Modifier
                    .fillMaxWidth()
                    .menuAnchor()
                    .semantics { contentDescription = "Industry selector, currently $selectedIndustry" },
        )
        ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            industries.forEach { industry ->
                DropdownMenuItem(
                    text = { Text(formatIndustryLabel(industry)) },
                    onClick = {
                        onIndustrySelected(industry)
                        expanded = false
                    },
                )
            }
        }
    }
}

private val PinnedCountryCodes = listOf("KE", "UG", "TZ", "NG", "ZA", "US", "GB", "CA", "DE")

private fun buildCountryOptions(): List<Pair<String, String>> {
    val locale = Locale.getDefault()
    val all =
        Locale
            .getISOCountries()
            .map { code -> code to Locale("", code).getDisplayCountry(locale).ifBlank { code } }
            .sortedBy { it.second }
    val pinned = PinnedCountryCodes.mapNotNull { code -> all.firstOrNull { it.first == code } }
    val rest = all.filterNot { it.first in PinnedCountryCodes }
    return pinned + rest
}

@OptIn(androidx.compose.material3.ExperimentalMaterial3Api::class)
@Composable
fun CountryDropdown(
    label: String,
    selectedCode: String,
    onCountrySelected: (String) -> Unit,
    contentDescriptionText: String,
    modifier: Modifier = Modifier,
) {
    var expanded by remember { mutableStateOf(false) }
    val countries = remember { buildCountryOptions() }
    val displayValue =
        if (selectedCode.isBlank()) {
            ""
        } else {
            countries
                .firstOrNull { it.first.equals(selectedCode, ignoreCase = true) }
                ?.let { "${it.second} (${it.first})" }
                ?: selectedCode.uppercase()
        }

    ExposedDropdownMenuBox(expanded = expanded, onExpandedChange = { expanded = it }, modifier = modifier) {
        OutlinedTextField(
            value = displayValue,
            onValueChange = {},
            readOnly = true,
            label = { Text(label) },
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded) },
            modifier =
                Modifier
                    .fillMaxWidth()
                    .menuAnchor()
                    .semantics { contentDescription = contentDescriptionText },
        )
        ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            countries.forEach { (code, name) ->
                DropdownMenuItem(
                    text = { Text("$name ($code)") },
                    onClick = {
                        onCountrySelected(code)
                        expanded = false
                    },
                )
            }
        }
    }
}
