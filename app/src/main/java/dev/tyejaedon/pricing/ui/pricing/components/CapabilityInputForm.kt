package dev.tyejaedon.pricing.ui.pricing.components

import android.content.res.Configuration
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import dev.tyejaedon.pricing.designsystem.GlassDropdownField
import dev.tyejaedon.pricing.designsystem.GlassDropdownItem
import dev.tyejaedon.pricing.designsystem.GlassStatusBadge
import dev.tyejaedon.pricing.designsystem.GlassTextField
import dev.tyejaedon.pricing.designsystem.LocalOneUiGlassColors
import dev.tyejaedon.pricing.designsystem.OneUiAmbientCanvas
import dev.tyejaedon.pricing.ui.theme.PricingSpacing
import dev.tyejaedon.pricing.ui.theme.PricingTheme
import java.util.Locale
import kotlin.math.abs

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

private val IndustryStarterTemplates: Map<String, List<Pair<String, String>>> =
    mapOf(
        "mobile" to
            listOf(
                "Android & Compose" to
                    "Senior Android engineer mentoring Kotlin, Jetpack Compose architecture, and UI performance.",
                "Flutter Cross-Platform" to
                    "Mobile architect coaching Flutter state management, native plugins, and release pipelines.",
            ),
        "data_ai" to
            listOf(
                "ML & MLOps" to
                    "Machine learning mentor guiding Python model evaluation, feature engineering, and MLOps deployment.",
                "LLM & RAG Systems" to
                    "Applied AI mentor for retrieval-augmented generation, vector search, and prompt evaluation.",
            ),
        "web_backend" to
            listOf(
                "APIs & Microservices" to
                    "Backend systems mentor teaching FastAPI, distributed microservices, and PostgreSQL query tuning.",
                "Full-Stack TypeScript" to
                    "Full-stack web mentor coaching React, Next.js architecture, and scalable REST APIs.",
            ),
        "devops_cloud" to
            listOf(
                "Kubernetes & CI/CD" to
                    "Cloud infrastructure mentor covering Kubernetes clusters, Terraform IaC, and GitHub Actions CI/CD.",
                "Cloud Security & SRE" to
                    "Site reliability mentor guiding observability, Prometheus alerts, and zero-trust cloud security.",
            ),
        "design_creative" to
            listOf(
                "Design Systems & UX" to
                    "Principal product designer mentoring Figma design systems, usability audits, and mobile UX flows.",
            ),
        "product_management" to
            listOf(
                "Product Strategy" to
                    "Product leadership mentor guiding roadmap prioritization, B2B discovery interviews, and KPI metrics.",
            ),
        "digital_marketing" to
            listOf(
                "Growth & SEO" to
                    "Digital growth mentor coaching technical SEO, conversion funnel analytics, and paid acquisition.",
            ),
        "general_tech" to
            listOf(
                "System Design & Career" to
                    "Staff software engineer mentoring system design interviews, code reviews, and technical leadership.",
            ),
    )

private data class CorridorShortcut(
    val label: String,
    val mentorCode: String,
    val clientCode: String,
)

private val PopularCorridors =
    listOf(
        CorridorShortcut("KE -> US", "KE", "US"),
        CorridorShortcut("KE -> GB", "KE", "GB"),
        CorridorShortcut("KE -> DE", "KE", "DE"),
        CorridorShortcut("KE -> KE (Local)", "KE", "KE"),
    )

private data class PositioningPreset(
    val label: String,
    val score: Float,
)

private val PositioningPresets =
    listOf(
        PositioningPreset("Niche (25%)", 0.25f),
        PositioningPreset("Balanced (50%)", 0.50f),
        PositioningPreset("Crowded (75%)", 0.75f),
    )

/**
 * `CapabilityInputForm` from the canonical Sprint 4 acceptance (issue #74): raw description,
 * industry selector and the bilateral country pair. Validation messages come from the ViewModel
 * (single source of truth); this composable only renders them.
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun CapabilityServiceStep(
    rawDescription: String,
    onDescriptionChanged: (String) -> Unit,
    selectedIndustry: String,
    onIndustrySelected: (String) -> Unit,
    industries: List<String> = SupportedIndustries,
    modifier: Modifier = Modifier,
) {
    val glass = LocalOneUiGlassColors.current
    val trimmedLength = rawDescription.trim().length
    val descriptionHelper =
        if (trimmedLength < 20) {
            "Add at least ${20 - trimmedLength} more characters ($trimmedLength/20) for accurate peer matching."
        } else {
            "Ready for peer matching ($trimmedLength characters)."
        }
    val starterTemplates =
        remember(selectedIndustry) {
            IndustryStarterTemplates[selectedIndustry]
                ?: IndustryStarterTemplates.getValue("general_tech")
        }

    Column(
        modifier = modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(PricingSpacing.Medium),
    ) {
        IndustryDropdown(
            selectedIndustry = selectedIndustry,
            onIndustrySelected = onIndustrySelected,
            industries = industries,
        )

        GlassTextField(
            value = rawDescription,
            onValueChange = onDescriptionChanged,
            label = "Describe your service",
            supportingText = descriptionHelper,
            singleLine = false,
            minLines = 3,
            textFieldModifier = Modifier.semantics { contentDescription = "Service description input" },
        )

        Column(verticalArrangement = Arrangement.spacedBy(PricingSpacing.Small)) {
            Text(
                text = "Quick-fill starter templates",
                style = MaterialTheme.typography.bodySmall,
                color = glass.textSecondary,
            )
            FlowRow(
                horizontalArrangement = Arrangement.spacedBy(PricingSpacing.Small),
                verticalArrangement = Arrangement.spacedBy(PricingSpacing.Small),
            ) {
                starterTemplates.forEach { (chipLabel, templateText) ->
                    val isSelected = rawDescription.trim() == templateText
                    PresetChip(
                        label = chipLabel,
                        selected = isSelected,
                        onClick = {
                            if (selectedIndustry.isBlank()) {
                                onIndustrySelected("general_tech")
                            }
                            onDescriptionChanged(templateText)
                        },
                    )
                }
            }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
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
        Column(verticalArrangement = Arrangement.spacedBy(PricingSpacing.Small)) {
            Text(
                text = "Popular corridors",
                style = MaterialTheme.typography.bodySmall,
                color = glass.textSecondary,
            )
            FlowRow(
                horizontalArrangement = Arrangement.spacedBy(PricingSpacing.Small),
                verticalArrangement = Arrangement.spacedBy(PricingSpacing.Small),
            ) {
                PopularCorridors.forEach { shortcut ->
                    val isSelected =
                        mentorCountry.equals(shortcut.mentorCode, ignoreCase = true) &&
                            clientCountry.equals(shortcut.clientCode, ignoreCase = true)
                    PresetChip(
                        label = shortcut.label,
                        selected = isSelected,
                        onClick = {
                            onMentorCountryChanged(shortcut.mentorCode)
                            onClientCountryChanged(shortcut.clientCode)
                        },
                    )
                }
            }
        }

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

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun CapabilityPositioningStep(
    baseRateFloor: String,
    onBaseRateFloorChanged: (String) -> Unit,
    competitivenessScore: Float,
    onCompetitivenessScoreChanged: (Float) -> Unit,
    modifier: Modifier = Modifier,
    onOpenGlossaryTerm: ((String) -> Unit)? = null,
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

        FlowRow(
            horizontalArrangement = Arrangement.spacedBy(PricingSpacing.Small),
            verticalArrangement = Arrangement.spacedBy(PricingSpacing.Small),
        ) {
            PositioningPresets.forEach { preset ->
                val isSelected = abs(competitivenessScore - preset.score) < 0.03f
                PresetChip(
                    label = preset.label,
                    selected = isSelected,
                    onClick = { onCompetitivenessScoreChanged(preset.score) },
                )
            }
        }

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                text = "Higher competitiveness reflects a more crowded niche; lower scores indicate specialized demand.",
                style = MaterialTheme.typography.bodySmall,
                color = glass.textMuted,
                modifier = Modifier.weight(1f),
            )
            if (onOpenGlossaryTerm != null) {
                GlassStatusBadge(
                    text = "Explain terms",
                    tint = glass.primaryAccent,
                    modifier =
                        Modifier
                            .padding(start = PricingSpacing.Small)
                            .clickable(
                                role = Role.Button,
                                onClick = { onOpenGlossaryTerm("competitiveness_score") },
                            ),
                )
            }
        }
    }
}

@Composable
private fun PresetChip(
    label: String,
    selected: Boolean,
    onClick: () -> Unit,
) {
    val glass = LocalOneUiGlassColors.current
    Box(
        modifier =
            Modifier
                .clip(CircleShape)
                .background(
                    color =
                        if (selected) {
                            glass.primaryAccent.copy(alpha = 0.22f)
                        } else {
                            glass.recessedWellFill
                        },
                    shape = CircleShape,
                ).border(
                    width = 1.dp,
                    color = if (selected) glass.primaryAccent else glass.recessedWellBorder,
                    shape = CircleShape,
                ).clickable(
                    role = Role.Button,
                    onClick = onClick,
                ).padding(horizontal = 12.dp, vertical = 6.dp),
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.labelLarge,
            color = if (selected) glass.primaryAccent else glass.textSecondary,
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
