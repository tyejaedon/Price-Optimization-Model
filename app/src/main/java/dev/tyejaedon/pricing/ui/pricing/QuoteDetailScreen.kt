package dev.tyejaedon.pricing.ui.pricing

import android.content.Intent
import android.content.res.Configuration
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import dev.tyejaedon.pricing.data.network.dto.PeerMatchDTO
import dev.tyejaedon.pricing.data.network.dto.PredictionResultDTO
import dev.tyejaedon.pricing.data.network.dto.QuoteExplanationDTO
import dev.tyejaedon.pricing.designsystem.GlassInsetDivider
import dev.tyejaedon.pricing.designsystem.GlassSecondaryButton
import dev.tyejaedon.pricing.designsystem.GlassStatusBadge
import dev.tyejaedon.pricing.designsystem.LocalOneUiGlassColors
import dev.tyejaedon.pricing.designsystem.OneUiGlassScaffold
import dev.tyejaedon.pricing.designsystem.OneUiShapes
import dev.tyejaedon.pricing.designsystem.recessedGlassWell
import dev.tyejaedon.pricing.ui.components.PrimaryActionButton
import dev.tyejaedon.pricing.ui.components.SectionCard
import dev.tyejaedon.pricing.ui.pricing.components.BilateralCorridorSelector
import dev.tyejaedon.pricing.ui.pricing.components.GlossaryPromptCard
import dev.tyejaedon.pricing.ui.pricing.components.PricingGlossarySheet
import dev.tyejaedon.pricing.ui.pricing.components.formatIndustryLabel
import dev.tyejaedon.pricing.ui.pricing.formatting.formatKesRate
import dev.tyejaedon.pricing.ui.theme.PricingSpacing
import dev.tyejaedon.pricing.ui.theme.PricingTheme
import dev.tyejaedon.pricing.viewmodel.PricingFormState
import java.text.NumberFormat
import java.util.Locale
import kotlin.math.abs
import kotlin.math.roundToInt

/**
 * Full-screen One UI Glass detail view opened on click from [PricingResultCard]. Explains rate
 * anatomy, negotiation range with peer dots, cross-border bilateral factor, matched skill terms,
 * peer IDW weights, session totals, and the uncalibrated-confidence disclosure without cluttering
 * the primary Quote screen.
 */
@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
fun QuoteDetailScreen(
    result: PredictionResultDTO,
    form: PricingFormState,
    onBack: () -> Unit,
    modifier: Modifier = Modifier,
) {
    BackHandler(onBack = onBack)

    val glass = LocalOneUiGlassColors.current
    val clipboard = LocalClipboardManager.current
    val context = LocalContext.current
    var copied by remember { mutableStateOf(false) }
    var showGlossary by remember { mutableStateOf(false) }
    var activeGlossaryTermId by remember { mutableStateOf<String?>(null) }
    var selectedHours by remember { mutableIntStateOf(1) }
    var selectedDiscountPct by remember { mutableIntStateOf(0) }
    val explanation = result.explanation

    val openGlossaryAt: (String?) -> Unit = { termId ->
        activeGlossaryTermId = termId
        showGlossary = true
    }

    val summaryText =
        remember(result, selectedHours, selectedDiscountPct) {
            buildClientSummaryText(result, selectedHours, selectedDiscountPct)
        }

    val copySummary = {
        clipboard.setText(AnnotatedString(summaryText))
        copied = true
    }

    val shareSummary = {
        val sendIntent =
            Intent(Intent.ACTION_SEND).apply {
                type = "text/plain"
                putExtra(Intent.EXTRA_SUBJECT, "Mentorship Rate Quote")
                putExtra(Intent.EXTRA_TEXT, summaryText)
            }
        runCatching {
            context.startActivity(Intent.createChooser(sendIntent, "Share Mentorship Quote"))
        }
        Unit
    }

    if (showGlossary) {
        PricingGlossarySheet(
            onDismiss = { showGlossary = false },
            initialExpandedTermId = activeGlossaryTermId,
        )
    }

    OneUiGlassScaffold(
        title = "Quote Breakdown",
        modifier = modifier,
        navigationIcon = {
            IconButton(onClick = onBack) {
                Icon(
                    imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                    contentDescription = "Back to quote",
                )
            }
        },
        actions = {
            GlassSecondaryButton(
                text = "Glossary",
                onClick = { openGlossaryAt(null) },
                contentDescription = "Open pricing glossary",
            )
            GlassSecondaryButton(
                text = if (copied) "Copied" else "Copy",
                onClick = copySummary,
                contentDescription = "Copy quote summary",
            )
        },
    ) { padding ->
        Column(
            modifier =
                Modifier
                    .fillMaxSize()
                    .padding(padding)
                    .padding(top = 24.dp)
                    .padding(horizontal = PricingSpacing.Medium)
                    .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(PricingSpacing.Medium),
        ) {
            RateAnatomyCard(result = result, explanation = explanation)

            CorridorStrategyCard(
                result = result,
                form = form,
                explanation = explanation,
                onExplainTerm = openGlossaryAt,
            )

            MatchingAttributionCard(
                result = result,
                form = form,
                explanation = explanation,
            )

            ComparablePeersCard(
                result = result,
                onExplainTerm = openGlossaryAt,
            )

            SessionAndTransparencyCard(
                result = result,
                selectedHours = selectedHours,
                onSelectHours = {
                    selectedHours = it
                    if (it == 1) {
                        selectedDiscountPct = 0
                    }
                    copied = false
                },
                selectedDiscountPct = selectedDiscountPct,
                onSelectDiscountPct = {
                    selectedDiscountPct = it
                    copied = false
                },
                copied = copied,
                onCopySummary = copySummary,
                onShareSummary = shareSummary,
                onExplainTerm = openGlossaryAt,
            )

            GlossaryPromptCard(
                onOpenGlossary = { openGlossaryAt(null) },
            )

            Spacer(modifier = Modifier.height(PricingSpacing.Medium))
        }
    }
}

@Composable
private fun RateAnatomyCard(
    result: PredictionResultDTO,
    explanation: QuoteExplanationDTO?,
) {
    val glass = LocalOneUiGlassColors.current
    SectionCard(modifier = Modifier.fillMaxWidth()) {
        Column(verticalArrangement = Arrangement.spacedBy(PricingSpacing.Small)) {
            Text(
                text = "Client pays vs. you keep",
                style = MaterialTheme.typography.titleMedium,
                color = glass.textPrimary,
            )
            Text(
                text = "${formatKesRate(result.finalQuotedRate)} KES/hour",
                style = MaterialTheme.typography.displayLarge,
                color = glass.textPrimary,
            )
            DetailLineItem(
                label = "Peer-matched base rate (you net)",
                value = "${formatKesRate(result.basePredictedRate)} KES/hour",
            )
            DetailLineItem(
                label = "M-Pesa transfer pass-through",
                value =
                    if (result.mpesaTariffSurcharge > 0f) {
                        "+${formatKesRate(result.mpesaTariffSurcharge)} KES/hour"
                    } else {
                        "0 KES/hour"
                    },
            )
            GlassInsetDivider(startIndent = 0.dp)
            DetailLineItem(
                label = "Total to quote client",
                value = "${formatKesRate(result.finalQuotedRate)} KES/hour",
                valueColor = glass.primaryAccent,
            )

            if (explanation?.floorExceedsBase == true) {
                GlassStatusBadge(
                    text =
                        "Your requested floor (${formatKesRate(explanation.baseRateFloorRequested ?: result.minQuotedRate)} KES) " +
                            "exceeds the peer median; walk-away floor is raised.",
                    tint = glass.warningTint,
                )
            }
            if (explanation?.feePushesAboveCeiling == true || result.finalQuotedRate > result.maxQuotedRate) {
                GlassStatusBadge(
                    text = "Negotiation range excludes the M-Pesa fee, so the fee-inclusive total sits above the corridor ceiling.",
                    tint = glass.infoTint,
                )
            }
        }
    }
}

@Composable
private fun CorridorStrategyCard(
    result: PredictionResultDTO,
    form: PricingFormState,
    explanation: QuoteExplanationDTO?,
    onExplainTerm: (String) -> Unit,
) {
    val glass = LocalOneUiGlassColors.current
    val mentorCountry = form.mentorCountry.ifBlank { "Local" }
    val clientCountry = form.clientCountry.ifBlank { "Client" }
    val uplift =
        explanation?.corridorUpliftMultiplier
            ?: if (result.bilateralArbitrageFactor < 1f) (2f - result.bilateralArbitrageFactor) else 1f

    SectionCard(modifier = Modifier.fillMaxWidth()) {
        Column(verticalArrangement = Arrangement.spacedBy(PricingSpacing.Small)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = "Negotiation strategy map",
                    style = MaterialTheme.typography.titleMedium,
                    color = glass.textPrimary,
                )
                GlassStatusBadge(
                    text = "Explain factor",
                    tint = glass.primaryAccent,
                    modifier =
                        Modifier.clickable(
                            role = Role.Button,
                            onClick = { onExplainTerm("bilateral_factor") },
                        ),
                )
            }
            BilateralCorridorSelector(
                minRate = result.minQuotedRate,
                maxRate = result.maxQuotedRate,
                finalRate = result.basePredictedRate,
                peerRates = result.comparables.map { it.verifiedRate },
                floorRate = explanation?.baseRateFloorRequested,
                showAnchorLabels = true,
            )
            GlassInsetDivider(startIndent = 0.dp)
            Text(
                text = "Cross-border effect ($mentorCountry -> $clientCountry)",
                style = MaterialTheme.typography.labelLarge,
                color = glass.textPrimary,
            )
            val corridorText =
                if (uplift > 1.01f) {
                    val upliftPct = ((uplift - 1f) * 100f).roundToInt()
                    "Purchasing-power calibration (factor ${formatFactor(result.bilateralArbitrageFactor)}) " +
                        "expanded your upper negotiation ceiling by +$upliftPct%."
                } else {
                    "Local or parity purchasing-power corridor (factor ${formatFactor(result.bilateralArbitrageFactor)}); " +
                        "no cross-border ceiling uplift applied."
                }
            Text(
                text = corridorText,
                style = MaterialTheme.typography.bodySmall,
                color = glass.textSecondary,
            )
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun MatchingAttributionCard(
    result: PredictionResultDTO,
    form: PricingFormState,
    explanation: QuoteExplanationDTO?,
) {
    val glass = LocalOneUiGlassColors.current
    val partitionKey = explanation?.routedPartition ?: form.selectedIndustry.ifBlank { "general_tech" }
    val spreadRatio = (result.maxQuotedRate - result.minQuotedRate) / result.basePredictedRate.coerceAtLeast(1f)
    val spreadLabel =
        when {
            spreadRatio < 0.35f -> "Tight consensus"
            spreadRatio < 0.70f -> "Moderate spread"
            else -> "Wide market spread"
        }

    SectionCard(modifier = Modifier.fillMaxWidth()) {
        Column(verticalArrangement = Arrangement.spacedBy(PricingSpacing.Small)) {
            Text(
                text = "How your service matched",
                style = MaterialTheme.typography.titleMedium,
                color = glass.textPrimary,
            )
            DetailLineItem(
                label = "Market partition searched",
                value = formatIndustryLabel(partitionKey),
            )
            if (explanation?.usedFallbackPartition == true) {
                val requestedLabel = formatIndustryLabel(explanation.requestedPartition ?: form.selectedIndustry)
                GlassStatusBadge(
                    text = "Few exact matches in $requestedLabel; broadened search to ${formatIndustryLabel(partitionKey)}.",
                    tint = glass.infoTint,
                )
            }
            DetailLineItem(
                label = "Market consensus",
                value =
                    if (explanation?.peerRateStddev != null) {
                        "$spreadLabel (±${formatKesRate(explanation.peerRateStddev)} KES/hr)"
                    } else {
                        spreadLabel
                    },
            )
            val terms = explanation?.topMatchedTerms.orEmpty()
            if (terms.isNotEmpty()) {
                GlassInsetDivider(startIndent = 0.dp)
                Text(
                    text = "Keywords anchoring your match",
                    style = MaterialTheme.typography.labelLarge,
                    color = glass.textPrimary,
                )
                FlowRow(
                    horizontalArrangement = Arrangement.spacedBy(PricingSpacing.ExtraSmall),
                    verticalArrangement = Arrangement.spacedBy(PricingSpacing.ExtraSmall),
                ) {
                    terms.forEach { term ->
                        GlassStatusBadge(text = term, tint = glass.primaryAccent)
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun ComparablePeersCard(
    result: PredictionResultDTO,
    onExplainTerm: (String) -> Unit,
) {
    val glass = LocalOneUiGlassColors.current
    SectionCard(modifier = Modifier.fillMaxWidth()) {
        Column(verticalArrangement = Arrangement.spacedBy(PricingSpacing.Small)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = "Comparable mentor peers",
                    style = MaterialTheme.typography.titleMedium,
                    color = glass.textPrimary,
                )
                GlassStatusBadge(
                    text = "Explain IDW",
                    tint = glass.primaryAccent,
                    modifier =
                        Modifier.clickable(
                            role = Role.Button,
                            onClick = { onExplainTerm("idw_weight") },
                        ),
                )
            }
            if (result.comparables.isEmpty()) {
                Text(
                    text = "No listing-backed comparables are available for this quote yet.",
                    style = MaterialTheme.typography.bodySmall,
                    color = glass.textMuted,
                )
                return@Column
            }
            if (result.comparables.size < result.kNeighborsUsed) {
                Text(
                    text =
                        "Showing ${result.comparables.size} of ${result.kNeighborsUsed} indexed peers; " +
                            "some listings lack public provenance.",
                    style = MaterialTheme.typography.bodySmall,
                    color = glass.textMuted,
                )
            }
            Column(
                modifier =
                    Modifier
                        .fillMaxWidth()
                        .recessedGlassWell(shape = OneUiShapes.InnerCard)
                        .padding(14.dp),
                verticalArrangement = Arrangement.spacedBy(PricingSpacing.Small),
            ) {
                result.comparables.forEachIndexed { index, peer ->
                    PeerDetailRow(peer = peer, basePredictedRate = result.basePredictedRate)
                    if (index < result.comparables.lastIndex) {
                        GlassInsetDivider(startIndent = 0.dp)
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun PeerDetailRow(
    peer: PeerMatchDTO,
    basePredictedRate: Float,
) {
    val glass = LocalOneUiGlassColors.current
    val deltaPct =
        if (basePredictedRate > 0f) {
            (((peer.verifiedRate - basePredictedRate) / basePredictedRate) * 100f).roundToInt()
        } else {
            0
        }
    val deltaLabel =
        when {
            deltaPct > 0 -> "+$deltaPct% vs base"
            deltaPct < 0 -> "$deltaPct% vs base"
            else -> "Matches base"
        }

    Column(
        modifier = Modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Text(
                text = peer.jobTitle?.takeIf(String::isNotBlank) ?: "Untitled listing",
                style = MaterialTheme.typography.bodyMedium,
                color = glass.textPrimary,
                modifier = Modifier.weight(1f),
            )
            Text(
                text = "${formatKesRate(peer.verifiedRate)} KES/hour",
                style = MaterialTheme.typography.bodyMedium,
                color = glass.secondaryAccent,
            )
        }
        FlowRow(
            horizontalArrangement = Arrangement.spacedBy(PricingSpacing.ExtraSmall),
            verticalArrangement = Arrangement.spacedBy(PricingSpacing.ExtraSmall),
        ) {
            GlassStatusBadge(
                text = deltaLabel,
                tint = if (abs(deltaPct) <= 5) glass.textSecondary else glass.infoTint,
            )
            peer.idwWeight?.let { weight ->
                GlassStatusBadge(
                    text = "${(weight.coerceIn(0f, 1f) * 100f).roundToInt()}% quote weight",
                    tint = glass.primaryAccent,
                )
            }
        }
        Row(modifier = Modifier.fillMaxWidth()) {
            val metaItems =
                listOfNotNull(
                    "Listing ID: ${peer.listingId}",
                    peer.experienceLevel?.takeIf(String::isNotBlank),
                    peer.countryCode?.takeIf(String::isNotBlank),
                    peer.industryLabel?.takeIf(String::isNotBlank),
                    peer.publishedDate?.takeIf(String::isNotBlank)?.let { "Published $it" },
                )
            Text(
                text = metaItems.joinToString(" • "),
                style = MaterialTheme.typography.bodySmall,
                color = glass.textMuted,
                modifier = Modifier.weight(1f),
            )
            Text(
                text = "Similarity: ${formatSimilarity(peer.similarityScore)}",
                style = MaterialTheme.typography.bodySmall,
                color = glass.textSecondary,
            )
        }
        LinearProgressIndicator(
            progress = { peer.similarityScore.coerceIn(0f, 1f) },
            modifier =
                Modifier
                    .fillMaxWidth()
                    .height(4.dp)
                    .clip(CircleShape),
            color = glass.primaryAccent,
            trackColor = glass.recessedWellFill,
        )
    }
}

@Composable
private fun SessionAndTransparencyCard(
    result: PredictionResultDTO,
    selectedHours: Int,
    onSelectHours: (Int) -> Unit,
    selectedDiscountPct: Int,
    onSelectDiscountPct: (Int) -> Unit,
    copied: Boolean,
    onCopySummary: () -> Unit,
    onShareSummary: () -> Unit,
    onExplainTerm: (String) -> Unit,
) {
    val glass = LocalOneUiGlassColors.current
    val packageDurations = listOf(1, 4, 10)
    val discountOptions = listOf(0, 5, 10)
    val rawDiscountedBase = result.basePredictedRate * (1f - selectedDiscountPct / 100f)
    val effectiveBaseHourly =
        if (selectedDiscountPct > 0) {
            maxOf(rawDiscountedBase, result.minQuotedRate)
        } else {
            result.basePredictedRate
        }
    val floorClamped = selectedDiscountPct > 0 && effectiveBaseHourly > rawDiscountedBase + 0.5f
    val effectiveQuotedHourly = effectiveBaseHourly + result.mpesaTariffSurcharge
    val totalQuote = effectiveQuotedHourly * selectedHours
    val netTakeHome = effectiveBaseHourly * selectedHours

    SectionCard(modifier = Modifier.fillMaxWidth()) {
        Column(verticalArrangement = Arrangement.spacedBy(PricingSpacing.Small)) {
            Text(
                text = "Session & package estimator",
                style = MaterialTheme.typography.titleMedium,
                color = glass.textPrimary,
            )
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(PricingSpacing.Small),
            ) {
                packageDurations.forEach { hours ->
                    val label = if (hours == 1) "1 hr" else "$hours hrs"
                    val modifier =
                        Modifier
                            .weight(1f)
                            .semantics { contentDescription = "Estimate for $label" }
                    if (selectedHours == hours) {
                        PrimaryActionButton(
                            text = label,
                            onClick = { onSelectHours(hours) },
                            modifier = modifier,
                        )
                    } else {
                        GlassSecondaryButton(
                            text = label,
                            onClick = { onSelectHours(hours) },
                            modifier = modifier,
                        )
                    }
                }
            }

            if (selectedHours > 1) {
                Text(
                    text = "Multi-session retainer discount (protected by your corridor floor)",
                    style = MaterialTheme.typography.bodySmall,
                    color = glass.textSecondary,
                )
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(PricingSpacing.Small),
                ) {
                    discountOptions.forEach { pct ->
                        val label = if (pct == 0) "Standard" else "-$pct% Retainer"
                        val modifier = Modifier.weight(1f)
                        if (selectedDiscountPct == pct) {
                            PrimaryActionButton(
                                text = label,
                                onClick = { onSelectDiscountPct(pct) },
                                modifier = modifier,
                            )
                        } else {
                            GlassSecondaryButton(
                                text = label,
                                onClick = { onSelectDiscountPct(pct) },
                                modifier = modifier,
                            )
                        }
                    }
                }
            }

            if (floorClamped) {
                GlassStatusBadge(
                    text = "Discount clamped at your corridor floor (${formatKesRate(result.minQuotedRate)} KES/hr).",
                    tint = glass.warningTint,
                )
            }

            DetailLineItem(
                label = "Effective hourly rate (incl. M-Pesa)",
                value = "${formatKesRate(effectiveQuotedHourly)} KES/hour",
            )
            DetailLineItem(
                label = "Client quote ($selectedHours ${if (selectedHours == 1) "hour" else "hours"})",
                value = "${formatKesRate(totalQuote)} KES",
                valueColor = glass.primaryAccent,
            )
            DetailLineItem(
                label = "Your net take-home",
                value = "${formatKesRate(netTakeHome)} KES",
            )

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(PricingSpacing.Small),
            ) {
                PrimaryActionButton(
                    text = if (copied) "Summary Copied" else "Copy Summary",
                    onClick = onCopySummary,
                    modifier = Modifier.weight(1f),
                )
                GlassSecondaryButton(
                    text = "Share Proposal",
                    onClick = onShareSummary,
                    modifier = Modifier.weight(1f),
                    contentDescription = "Share client quote proposal",
                )
            }

            GlassInsetDivider(startIndent = 0.dp)

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = "Model transparency",
                    style = MaterialTheme.typography.labelLarge,
                    color = glass.textPrimary,
                )
                GlassStatusBadge(
                    text = "What does 0% mean?",
                    tint = glass.infoTint,
                    modifier =
                        Modifier.clickable(
                            role = Role.Button,
                            onClick = { onExplainTerm("uncalibrated_confidence") },
                        ),
                )
            }
            DetailLineItem(
                label = "Confidence (uncalibrated)",
                value = "${(result.confidenceScore * 100).toInt()}%",
            )
            Text(
                text = "Not a probability that this quote is accurate.",
                style = MaterialTheme.typography.bodySmall,
                color = glass.warningTint,
            )
            Text(
                text = result.reason,
                style = MaterialTheme.typography.bodySmall,
                color = glass.textMuted,
            )
        }
    }
}

@Composable
private fun DetailLineItem(
    label: String,
    value: String,
    valueColor: Color = LocalOneUiGlassColors.current.textPrimary,
) {
    val glass = LocalOneUiGlassColors.current
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.bodyMedium,
            color = glass.textSecondary,
            modifier = Modifier.weight(1f),
        )
        Text(
            text = value,
            style = MaterialTheme.typography.bodyMedium,
            color = valueColor,
        )
    }
}

private fun buildClientSummaryText(
    result: PredictionResultDTO,
    hours: Int,
    discountPct: Int = 0,
): String {
    val unitLabel = if (hours == 1) "1 hour" else "$hours hours"
    val rawDiscountedBase = result.basePredictedRate * (1f - discountPct / 100f)
    val effectiveBase =
        if (discountPct > 0) {
            maxOf(rawDiscountedBase, result.minQuotedRate)
        } else {
            result.basePredictedRate
        }
    val effectiveHourly = effectiveBase + result.mpesaTariffSurcharge
    val total = formatKesRate(effectiveHourly * hours)
    val hourly = formatKesRate(effectiveHourly)
    val minRange = formatKesRate(result.minQuotedRate)
    val maxRange = formatKesRate(result.maxQuotedRate)
    val discountTag = if (discountPct > 0) ", $discountPct% retainer package" else ""
    return "Mentorship Quote ($unitLabel$discountTag): $total KES ($hourly KES/hour, including transfer fee). " +
        "Market reference range (excl. fee): $minRange–$maxRange KES/hour."
}

private fun formatFactor(factor: Float): String = String.format(Locale.US, "%.2f", factor)

private fun formatSimilarity(score: Float): String =
    NumberFormat
        .getPercentInstance(Locale.getDefault())
        .format(score.coerceIn(0f, 1f))

private val previewDetailResult =
    PredictionResultDTO(
        basePredictedRate = 2500f,
        mpesaTariffSurcharge = 57f,
        finalQuotedRate = 2557f,
        minQuotedRate = 2125f,
        maxQuotedRate = 3375f,
        kNeighborsUsed = 5,
        bilateralArbitrageFactor = 0.51f,
        confidenceScore = 0f,
        comparables =
            listOf(
                PeerMatchDTO(
                    listingId = "list_001",
                    jobTitle = "Senior Android Architect",
                    verifiedRate = 2600f,
                    similarityScore = 0.92f,
                    euclideanDistance = 0.41f,
                    idwWeight = 0.62f,
                    experienceLevel = "Senior",
                    countryCode = "KE",
                ),
                PeerMatchDTO(
                    listingId = "list_045",
                    jobTitle = "Kotlin Mentor",
                    verifiedRate = 2400f,
                    similarityScore = 0.88f,
                    euclideanDistance = 0.55f,
                    idwWeight = 0.38f,
                    experienceLevel = "Mid-Senior",
                    countryCode = "KE",
                ),
            ),
        reason = "Weighted from 5 indexed peers in KES/hour; corridor excludes the M-Pesa surcharge.",
        explanation =
            QuoteExplanationDTO(
                requestedPartition = "mobile",
                routedPartition = "mobile",
                usedFallbackPartition = false,
                peerRateStddev = 280f,
                corridorUpliftMultiplier = 1.49f,
                topMatchedTerms = listOf("android", "kotlin", "jetpack compose", "architecture"),
            ),
        timestamp = "2026-10-10T00:00:00Z",
    )

private val previewDetailForm =
    PricingFormState(
        rawDescription = "Senior Android engineer mentoring Kotlin and Jetpack Compose teams.",
        mentorId = "demo-mentor",
        selectedIndustry = "mobile",
        mentorCountry = "KE",
        clientCountry = "US",
    )

@Preview(name = "QuoteDetailScreen - Light", showBackground = true)
@Composable
private fun QuoteDetailScreenLightPreview() {
    PricingTheme(darkTheme = false) {
        QuoteDetailScreen(
            result = previewDetailResult,
            form = previewDetailForm,
            onBack = {},
        )
    }
}

@Preview(name = "QuoteDetailScreen - Dark", uiMode = Configuration.UI_MODE_NIGHT_YES, showBackground = true)
@Composable
private fun QuoteDetailScreenDarkPreview() {
    PricingTheme(darkTheme = true) {
        QuoteDetailScreen(
            result = previewDetailResult,
            form = previewDetailForm,
            onBack = {},
        )
    }
}

@Preview(name = "QuoteDetailScreen - Large font", fontScale = 2.0f, showBackground = true)
@Composable
private fun QuoteDetailScreenLargeFontPreview() {
    PricingTheme(darkTheme = false) {
        QuoteDetailScreen(
            result = previewDetailResult,
            form = previewDetailForm,
            onBack = {},
        )
    }
}
