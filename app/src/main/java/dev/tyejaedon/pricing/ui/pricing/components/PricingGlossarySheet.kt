package dev.tyejaedon.pricing.ui.pricing.components

import androidx.compose.animation.AnimatedVisibility
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
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.KeyboardArrowUp
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
import androidx.compose.ui.draw.clip
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import dev.tyejaedon.pricing.designsystem.GlassModalBottomSheet
import dev.tyejaedon.pricing.designsystem.GlassPrimaryButton
import dev.tyejaedon.pricing.designsystem.GlassStatusBadge
import dev.tyejaedon.pricing.designsystem.GlassTextField
import dev.tyejaedon.pricing.designsystem.LocalOneUiGlassColors
import dev.tyejaedon.pricing.designsystem.OneUiShapes
import dev.tyejaedon.pricing.designsystem.recessedGlassWell
import dev.tyejaedon.pricing.ui.components.SectionCard
import dev.tyejaedon.pricing.ui.theme.PricingSpacing

enum class GlossaryCategory(val label: String) {
    ALL("All"),
    RATES("Rates & Fees"),
    CORRIDOR("Corridor & Market"),
    MATCHING("Peer Matching"),
    MODEL("Model & Guards"),
}

data class GlossaryTerm(
    val id: String,
    val title: String,
    val badge: String,
    val category: GlossaryCategory,
    val plainMeaning: String,
    val example: String,
)

val PricingGlossaryTerms: List<GlossaryTerm> =
    listOf(
        GlossaryTerm(
            id = "recommended_rate",
            title = "Recommended Rate (Final Quoted Rate)",
            badge = "Client invoice total",
            category = GlossaryCategory.RATES,
            plainMeaning =
                "The total hourly rate in Kenyan Shillings (KES/hour) you quote to your client. " +
                    "It combines your peer-matched base rate with the M-Pesa transfer surcharge so " +
                    "payment fees never eat into your take-home pay.",
            example =
                "If your base rate is 2,500 KES/hour and the M-Pesa fee is 57 KES, your recommended " +
                    "rate is 2,557 KES/hour.",
        ),
        GlossaryTerm(
            id = "base_predicted_rate",
            title = "Base Predicted Rate (Your Take-Home)",
            badge = "Net mentor earnings",
            category = GlossaryCategory.RATES,
            plainMeaning =
                "The hourly amount you keep before adding mobile-money transfer fees. It is calculated " +
                    "from verified peer listings with similar skills, or raised to your Base-Rate Floor " +
                    "if your minimum floor is higher.",
            example =
                "When peers with similar Android skills charge around 2,500 KES/hour, your base " +
                    "predicted rate is 2,500 KES/hour.",
        ),
        GlossaryTerm(
            id = "mpesa_surcharge",
            title = "M-Pesa Tariff Surcharge",
            badge = "Fee pass-through",
            category = GlossaryCategory.RATES,
            plainMeaning =
                "The official M-Pesa transfer fee for your payout band, added on top of your base " +
                    "rate so you net 100% of your intended hourly earnings after cash-out or transfer.",
            example =
                "A 2,500 KES payout sits in the 1,501–2,500 KES tariff band, adding a 57 KES surcharge.",
        ),
        GlossaryTerm(
            id = "base_rate_floor",
            title = "Base-Rate Floor",
            badge = "Walk-away minimum",
            category = GlossaryCategory.RATES,
            plainMeaning =
                "An optional minimum hourly rate (KES/hour) you refuse to go below. If the market " +
                    "estimate or lower corridor bound falls below your floor, the engine clamps your " +
                    "quote upward to protect your minimum.",
            example =
                "If peers average 2,200 KES/hour but you set a 2,500 KES/hour floor, your base rate " +
                    "and corridor minimum are raised to 2,500 KES/hour.",
        ),
        GlossaryTerm(
            id = "negotiation_corridor",
            title = "Negotiation Corridor (Min – Max Range)",
            badge = "Safe bargaining window",
            category = GlossaryCategory.CORRIDOR,
            plainMeaning =
                "Your recommended bargaining range (excluding the M-Pesa fee). Start negotiations near " +
                    "the ceiling for international clients or urgent scopes, and treat the floor as your " +
                    "lowest acceptable rate for long-term retainers.",
            example =
                "A corridor of 2,125–3,375 KES/hour lets you anchor high at 3,375 KES/hour while " +
                    "knowing 2,125 KES/hour is your bottom line.",
        ),
        GlossaryTerm(
            id = "bilateral_factor",
            title = "Bilateral Arbitrage Factor",
            badge = "Cross-border purchasing power",
            category = GlossaryCategory.CORRIDOR,
            plainMeaning =
                "A macro-economic index comparing purchasing power and wage levels between your country " +
                    "and your client's country. When a client is in a higher-income market, this factor " +
                    "widens your upper negotiation ceiling.",
            example =
                "A factor of 0.51 for a KE → US corridor expands your upper negotiation ceiling by " +
                    "roughly +49% compared to a domestic KE → KE quote.",
        ),
        GlossaryTerm(
            id = "competitiveness_score",
            title = "Competitiveness Score",
            badge = "Market crowding slider",
            category = GlossaryCategory.CORRIDOR,
            plainMeaning =
                "A 0.00 to 1.00 input reflecting how crowded your niche is. Lower values indicate a " +
                    "rare specialization (supporting a wider premium), while higher values indicate stiff " +
                    "competition (tightening the corridor closer to the peer median).",
            example =
                "Set 0.25 for niche embedded-AI mentoring, or 0.75 for general entry-level web tutoring.",
        ),
        GlossaryTerm(
            id = "idw_weight",
            title = "IDW Quote Weight (Inverse Distance Weighting)",
            badge = "Peer influence share",
            category = GlossaryCategory.MATCHING,
            plainMeaning =
                "The exact percentage share a comparable peer listing contributed to your base rate. " +
                    "Peers whose skills and experience sit closer to yours in feature space receive " +
                    "exponentially higher weight than distant peers.",
            example =
                "A peer with 62% quote weight had nearly twice as much influence on your rate as a " +
                    "peer with 38% weight.",
        ),
        GlossaryTerm(
            id = "similarity_score",
            title = "Similarity Score & Feature Distance",
            badge = "0% – 100% profile match",
            category = GlossaryCategory.MATCHING,
            plainMeaning =
                "How closely a peer listing matches your service description and experience profile. " +
                    "It is derived from the Euclidean distance between your profile and the peer inside " +
                    "the engine's spatial KD-Tree index (1 / (1 + distance)).",
            example =
                "A Euclidean distance of 0.09 converts to a 92% similarity score—an almost identical " +
                    "service profile.",
        ),
        GlossaryTerm(
            id = "matched_terms",
            title = "Matched Terms (TF-IDF Keywords)",
            badge = "NLP skill signals",
            category = GlossaryCategory.MATCHING,
            plainMeaning =
                "The highest-weighted technical words or phrases extracted from your service description " +
                    "using TF-IDF (Term Frequency–Inverse Document Frequency). Distinctive skills carry " +
                    "more weight than generic words.",
            example =
                "Terms like 'kotlin', 'jetpack compose', and 'architecture' steer the search toward " +
                    "specialized mobile mentors.",
        ),
        GlossaryTerm(
            id = "partition_routing",
            title = "Industry Partition & Fallback Routing",
            badge = "Domain search bucket",
            category = GlossaryCategory.MODEL,
            plainMeaning =
                "To keep comparisons fair, peer listings are grouped into industry partitions (such as " +
                    "Mobile or Data & AI). If your chosen partition has too few verified peers, the " +
                    "engine automatically broadens the search to General Technology so you still get a " +
                    "reliable quote.",
            example =
                "If a niche partition has fewer than the minimum required peers, routing falls back to " +
                    "'general_tech' and flags the broadened search.",
        ),
        GlossaryTerm(
            id = "peer_dispersion",
            title = "Peer Rate Dispersion (± KES/hour)",
            badge = "Market spread",
            category = GlossaryCategory.MODEL,
            plainMeaning =
                "The standard deviation (± KES/hour) across your matched peers' hourly rates. Low " +
                    "dispersion means peers charge very similar rates; high dispersion means rates vary " +
                    "widely by seniority or specialization.",
            example =
                "A dispersion of ±240 KES/hour around a 2,500 KES base rate shows tight market consensus.",
        ),
        GlossaryTerm(
            id = "uncalibrated_confidence",
            title = "Confidence (Uncalibrated)",
            badge = "Internal diagnostic",
            category = GlossaryCategory.MODEL,
            plainMeaning =
                "A raw internal distance diagnostic rather than a calibrated statistical probability. " +
                    "A 0% reading does not mean your quote is inaccurate—always check the number of " +
                    "matched peers and their similarity scores instead.",
            example =
                "A quote backed by 5 peers at 92% similarity is well-grounded even when uncalibrated " +
                    "confidence reads 0%.",
        ),
    )

/**
 * Searchable, category-filtered One UI Glass bottom sheet that explains every technical term used
 * in the pricing form and quote breakdown in plain language with concrete KES examples.
 */
@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
fun PricingGlossarySheet(
    onDismiss: () -> Unit,
    modifier: Modifier = Modifier,
    initialExpandedTermId: String? = null,
) {
    val glass = LocalOneUiGlassColors.current
    var searchQuery by remember { mutableStateOf("") }
    var selectedCategory by remember { mutableStateOf(GlossaryCategory.ALL) }
    var expandedTermId by remember {
        mutableStateOf(initialExpandedTermId ?: PricingGlossaryTerms.first().id)
    }

    val filteredTerms =
        remember(searchQuery, selectedCategory) {
            val query = searchQuery.trim().lowercase()
            PricingGlossaryTerms.filter { term ->
                val matchesCategory =
                    selectedCategory == GlossaryCategory.ALL || term.category == selectedCategory
                val matchesQuery =
                    query.isEmpty() ||
                        term.title.lowercase().contains(query) ||
                        term.badge.lowercase().contains(query) ||
                        term.plainMeaning.lowercase().contains(query)
                matchesCategory && matchesQuery
            }
        }

    GlassModalBottomSheet(
        onDismissRequest = onDismiss,
        title = "Pricing Glossary",
        modifier = modifier,
        actions = {
            GlassPrimaryButton(
                text = "Done",
                onClick = onDismiss,
                modifier = Modifier.fillMaxWidth(),
                contentDescription = "Close pricing glossary",
            )
        },
    ) {
        Text(
            text = "Plain-language guide to every rate, corridor, and peer-matching term.",
            style = MaterialTheme.typography.bodySmall,
            color = glass.textSecondary,
        )

        GlassTextField(
            value = searchQuery,
            onValueChange = { searchQuery = it },
            label = "Search terms (e.g., IDW, corridor, M-Pesa, floor)",
            singleLine = true,
        )

        FlowRow(
            horizontalArrangement = Arrangement.spacedBy(PricingSpacing.Small),
            verticalArrangement = Arrangement.spacedBy(PricingSpacing.Small),
        ) {
            GlossaryCategory.entries.forEach { category ->
                val selected = category == selectedCategory
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
                                color =
                                    if (selected) {
                                        glass.primaryAccent
                                    } else {
                                        glass.recessedWellBorder
                                    },
                                shape = CircleShape,
                            ).clickable(
                                role = Role.Tab,
                                onClick = { selectedCategory = category },
                            ).padding(horizontal = 12.dp, vertical = 6.dp),
                ) {
                    Text(
                        text = category.label,
                        style = MaterialTheme.typography.labelLarge,
                        color = if (selected) glass.primaryAccent else glass.textSecondary,
                    )
                }
            }
        }

        Column(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .heightIn(max = 380.dp)
                    .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(PricingSpacing.Small),
        ) {
            if (filteredTerms.isEmpty()) {
                Text(
                    text = "No glossary terms match \"$searchQuery\".",
                    style = MaterialTheme.typography.bodyMedium,
                    color = glass.textMuted,
                    modifier = Modifier.padding(vertical = PricingSpacing.Medium),
                )
            } else {
                filteredTerms.forEach { term ->
                    GlossaryTermItem(
                        term = term,
                        expanded = expandedTermId == term.id,
                        onToggle = {
                            expandedTermId = if (expandedTermId == term.id) "" else term.id
                        },
                    )
                }
            }
        }
    }
}

@Composable
private fun GlossaryTermItem(
    term: GlossaryTerm,
    expanded: Boolean,
    onToggle: () -> Unit,
) {
    val glass = LocalOneUiGlassColors.current
    Column(
        modifier =
            Modifier
                .fillMaxWidth()
                .recessedGlassWell(shape = OneUiShapes.InputWell, focused = expanded)
                .clickable(
                    role = Role.Button,
                    onClick = onToggle,
                ).semantics {
                    contentDescription = "${term.title}: ${term.badge}"
                }.padding(PricingSpacing.Medium),
        verticalArrangement = Arrangement.spacedBy(PricingSpacing.Small),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(2.dp),
            ) {
                Text(
                    text = term.title,
                    style = MaterialTheme.typography.bodyMedium.copy(fontWeight = FontWeight.SemiBold),
                    color = glass.textPrimary,
                )
                Text(
                    text = term.badge,
                    style = MaterialTheme.typography.bodySmall,
                    color = glass.primaryAccent,
                )
            }
            Icon(
                imageVector =
                    if (expanded) {
                        Icons.Default.KeyboardArrowUp
                    } else {
                        Icons.Default.KeyboardArrowDown
                    },
                contentDescription = null,
                tint = glass.textSecondary,
            )
        }

        AnimatedVisibility(visible = expanded) {
            Column(verticalArrangement = Arrangement.spacedBy(PricingSpacing.Small)) {
                Text(
                    text = term.plainMeaning,
                    style = MaterialTheme.typography.bodySmall,
                    color = glass.textSecondary,
                )
                GlassStatusBadge(
                    text = "Example: ${term.example}",
                    tint = glass.infoTint,
                )
            }
        }
    }
}

/**
 * Compact clickable banner card encouraging users to open the [PricingGlossarySheet] whenever they
 * want plain-language definitions of technical terms.
 */
@Composable
fun GlossaryPromptCard(
    onOpenGlossary: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val glass = LocalOneUiGlassColors.current
    SectionCard(
        modifier =
            modifier
                .fillMaxWidth()
                .semantics {
                    contentDescription = "Open pricing glossary"
                },
        onClick = onOpenGlossary,
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                Text(
                    text = "New to these pricing terms?",
                    style = MaterialTheme.typography.titleMedium,
                    color = glass.textPrimary,
                )
                Text(
                    text =
                        "Browse the Pricing Glossary for plain-language explanations of IDW weight, " +
                            "bilateral factor, corridor bounds, and M-Pesa pass-through.",
                    style = MaterialTheme.typography.bodySmall,
                    color = glass.textSecondary,
                )
            }
            GlassStatusBadge(
                text = "Glossary",
                tint = glass.primaryAccent,
                modifier = Modifier.padding(start = PricingSpacing.Small),
            )
        }
    }
}
