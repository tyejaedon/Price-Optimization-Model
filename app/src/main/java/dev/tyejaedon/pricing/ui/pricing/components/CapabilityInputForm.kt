package dev.tyejaedon.pricing.ui.pricing.components

import android.content.res.Configuration
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.MaterialTheme
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
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import dev.tyejaedon.pricing.designsystem.GlassDropdownField
import dev.tyejaedon.pricing.designsystem.GlassDropdownItem
import dev.tyejaedon.pricing.designsystem.GlassTextField
import dev.tyejaedon.pricing.designsystem.LocalOneUiGlassColors
import dev.tyejaedon.pricing.designsystem.OneUiAmbientCanvas
import dev.tyejaedon.pricing.ui.theme.PricingSpacing
import dev.tyejaedon.pricing.ui.theme.PricingTheme
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
fun CapabilityServiceStep(
    rawDescription: String,
    onDescriptionChanged: (String) -> Unit,
    selectedIndustry: String,
    onIndustrySelected: (String) -> Unit,
    industries: List<String> = SupportedIndustries,
    modifier: Modifier = Modifier,
) {
    val trimmedLength = rawDescription.trim().length
    val descriptionHelper =
        if (trimmedLength < 20) {
            "Add at least ${20 - trimmedLength} more characters ($trimmedLength/20) for accurate peer matching."
        } else {
            "Ready for peer matching ($trimmedLength characters)."
        }

    Column(
        modifier = modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(PricingSpacing.Medium),
    ) {
        GlassTextField(
            value = rawDescription,
            onValueChange = onDescriptionChanged,
            label = "Describe your service",
            supportingText = descriptionHelper,
            singleLine = false,
            minLines = 3,
            textFieldModifier = Modifier.semantics { contentDescription = "Service description input" },
        )

        IndustryDropdown(
            selectedIndustry = selectedIndustry,
            onIndustrySelected = onIndustrySelected,
            industries = industries,
        )
    }
}

@Composable
fun CapabilityCorridorStep(
    mentorCountry: String,
    onMentorCountryChanged: (String) -> Unit,
    clientCountry: String,
    onClientCountryChanged: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    val glass = LocalOneUiGlassColors.current
    Column(
        modifier = modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(PricingSpacing.Medium),
    ) {
        CountryDropdown(
            label = "Your country",
            selectedCode = mentorCountry,
            onCountrySelected = onMentorCountryChanged,
            contentDescriptionText = "Your country ISO 2-letter code",
        )

        CountryDropdown(
            label = "Client country",
            selectedCode = clientCountry,
            onCountrySelected = onClientCountryChanged,
            contentDescriptionText = "Client country ISO 2-letter code",
        )

        Text(
            text = "Cross-border quotes automatically factor in local purchasing power and M-Pesa transfer fees.",
            style = MaterialTheme.typography.bodySmall,
            color = glass.textMuted,
        )
    }
}

@Composable
fun CapabilityPositioningStep(
    baseRateFloor: String,
    onBaseRateFloorChanged: (String) -> Unit,
    competitivenessScore: Float,
    onCompetitivenessScoreChanged: (Float) -> Unit,
    modifier: Modifier = Modifier,
) {
    val glass = LocalOneUiGlassColors.current
    Column(
        modifier = modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(PricingSpacing.Medium),
    ) {
        GlassTextField(
            value = baseRateFloor,
            onValueChange = onBaseRateFloorChanged,
            label = "Minimum base rate (KES/hour, optional)",
            supportingText = "Your personal floor before M-Pesa fees are added.",
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
            singleLine = true,
        )

        SaturationSlider(
            score = competitivenessScore,
            onScoreChanged = onCompetitivenessScoreChanged,
        )

        Text(
            text = "Higher competitiveness reflects a more crowded niche; lower scores indicate specialized demand.",
            style = MaterialTheme.typography.bodySmall,
            color = glass.textMuted,
        )
    }
}

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
    Column(
        modifier = modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(PricingSpacing.Medium),
    ) {
        CapabilityServiceStep(
            rawDescription = rawDescription,
            onDescriptionChanged = onDescriptionChanged,
            selectedIndustry = selectedIndustry,
            onIndustrySelected = onIndustrySelected,
            industries = industries,
        )

        CapabilityCorridorStep(
            mentorCountry = mentorCountry,
            onMentorCountryChanged = onMentorCountryChanged,
            clientCountry = clientCountry,
            onClientCountryChanged = onClientCountryChanged,
        )

        GlassTextField(
            value = baseRateFloor,
            onValueChange = onBaseRateFloorChanged,
            label = "Minimum base rate (KES/hour, optional)",
            supportingText = "Your personal floor before M-Pesa fees are added.",
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
            singleLine = true,
        )
    }
}

@Composable
fun IndustryDropdown(
    selectedIndustry: String,
    onIndustrySelected: (String) -> Unit,
    industries: List<String>,
    modifier: Modifier = Modifier,
) {
    var expanded by remember { mutableStateOf(false) }
    GlassDropdownField(
        label = "Industry",
        displayValue = if (selectedIndustry.isBlank()) "" else formatIndustryLabel(selectedIndustry),
        expanded = expanded,
        onExpandedChange = { expanded = it },
        modifier = modifier,
        anchorSemanticsDescription = "Industry selector, currently $selectedIndustry",
    ) {
        industries.forEach { industry ->
            GlassDropdownItem(
                text = formatIndustryLabel(industry),
                onClick = {
                    onIndustrySelected(industry)
                    expanded = false
                },
            )
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

    GlassDropdownField(
        label = label,
        displayValue = displayValue,
        expanded = expanded,
        onExpandedChange = { expanded = it },
        modifier = modifier,
        anchorSemanticsDescription = contentDescriptionText,
    ) {
        countries.forEach { (code, name) ->
            GlassDropdownItem(
                text = "$name ($code)",
                onClick = {
                    onCountrySelected(code)
                    expanded = false
                },
            )
        }
    }
}

@Preview(name = "CapabilityInputForm - Light", showBackground = true)
@Composable
private fun CapabilityInputFormLightPreview() {
    PricingTheme(darkTheme = false) {
        OneUiAmbientCanvas {
            CapabilityInputForm(
                rawDescription = "Senior Android & Kotlin Multiplatform mentorship and architecture reviews",
                onDescriptionChanged = {},
                mentorId = "mentor_001",
                onMentorIdChanged = {},
                selectedIndustry = "mobile",
                onIndustrySelected = {},
                mentorCountry = "KE",
                onMentorCountryChanged = {},
                clientCountry = "US",
                onClientCountryChanged = {},
                baseRateFloor = "2000",
                onBaseRateFloorChanged = {},
                modifier = Modifier.padding(16.dp),
            )
        }
    }
}

@Preview(name = "CapabilityInputForm - Dark", uiMode = Configuration.UI_MODE_NIGHT_YES, showBackground = true)
@Composable
private fun CapabilityInputFormDarkPreview() {
    PricingTheme(darkTheme = true) {
        OneUiAmbientCanvas {
            CapabilityInputForm(
                rawDescription = "",
                onDescriptionChanged = {},
                mentorId = "",
                onMentorIdChanged = {},
                selectedIndustry = "data_ai",
                onIndustrySelected = {},
                mentorCountry = "KE",
                onMentorCountryChanged = {},
                clientCountry = "GB",
                onClientCountryChanged = {},
                baseRateFloor = "",
                onBaseRateFloorChanged = {},
                modifier = Modifier.padding(16.dp),
            )
        }
    }
}
