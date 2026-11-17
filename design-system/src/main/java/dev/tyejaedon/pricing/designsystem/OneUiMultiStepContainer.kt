package dev.tyejaedon.pricing.designsystem

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.AnimatedContentTransitionScope
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.unit.dp

data class OneUiStepMeta(
    val title: String,
    val subtitle: String,
)

/**
 * Reusable One UI Glassmorphic multi-step progressive disclosure container.
 * Features pill-segmented progress indicators, directional slide+fade transitions,
 * haptic feedback, and keyboard-aware bottom navigation controls.
 */
@Composable
fun OneUiMultiStepContainer(
    currentStep: Int,
    steps: List<OneUiStepMeta>,
    onBack: () -> Unit,
    onNext: () -> Unit,
    canProceed: Boolean,
    finalActionLabel: String,
    modifier: Modifier = Modifier,
    finalActionContentDescription: String? = null,
    secondaryResetLabel: String? = null,
    onSecondaryReset: (() -> Unit)? = null,
    isBusy: Boolean = false,
    stepContent: @Composable ColumnScope.(stepIndex: Int) -> Unit,
) {
    val glass = LocalOneUiGlassColors.current
    val haptics = LocalHapticFeedback.current
    val safeStep = currentStep.coerceIn(0, (steps.size - 1).coerceAtLeast(0))
    val activeMeta = steps.getOrNull(safeStep) ?: OneUiStepMeta("", "")
    val isFirstStep = safeStep == 0
    val isLastStep = safeStep == steps.lastIndex

    Column(
        modifier = modifier.fillMaxWidth().imePadding(),
        verticalArrangement = Arrangement.spacedBy(OneUiSpacing.Medium),
    ) {
        GlassCard(modifier = Modifier.fillMaxWidth()) {
            Column(verticalArrangement = Arrangement.spacedBy(OneUiSpacing.Small)) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    GlassStatusBadge(
                        text = "Step ${safeStep + 1} of ${steps.size}",
                        tint = glass.primaryAccent,
                    )
                    if (secondaryResetLabel != null && onSecondaryReset != null) {
                        androidx.compose.material3.TextButton(
                            onClick = onSecondaryReset,
                            enabled = !isBusy,
                        ) {
                            Text(text = secondaryResetLabel, color = glass.textMuted)
                        }
                    }
                }

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    steps.indices.forEach { index ->
                        val active = index <= safeStep
                        val fillFraction by animateFloatAsState(
                            targetValue = if (active) 1f else 0f,
                            animationSpec = OneUiMotion.TransitionTween,
                            label = "stepPillProgress",
                        )
                        Box(
                            modifier =
                                Modifier
                                    .weight(1f)
                                    .height(6.dp)
                                    .clip(CircleShape)
                                    .background(glass.recessedWellFill),
                        ) {
                            if (fillFraction > 0f) {
                                Box(
                                    modifier =
                                        Modifier
                                            .fillMaxWidth(fillFraction)
                                            .height(6.dp)
                                            .clip(CircleShape)
                                            .background(glass.primaryAccent),
                                )
                            }
                        }
                    }
                }

                Text(
                    text = activeMeta.title,
                    style = MaterialTheme.typography.titleLarge,
                    color = glass.textPrimary,
                )
                Text(
                    text = activeMeta.subtitle,
                    style = MaterialTheme.typography.bodyMedium,
                    color = glass.textSecondary,
                )
            }
        }

        GlassCard(modifier = Modifier.fillMaxWidth()) {
            AnimatedContent(
                targetState = safeStep,
                transitionSpec = {
                    val direction =
                        if (targetState >= initialState) {
                            AnimatedContentTransitionScope.SlideDirection.Start
                        } else {
                            AnimatedContentTransitionScope.SlideDirection.End
                        }
                    (slideIntoContainer(direction) + fadeIn())
                        .togetherWith(slideOutOfContainer(direction) + fadeOut())
                },
                label = "multiStepTransition",
            ) { targetStep ->
                Column(
                    modifier = Modifier.fillMaxWidth(),
                    verticalArrangement = Arrangement.spacedBy(OneUiSpacing.Medium),
                ) {
                    stepContent(targetStep)
                }
            }
        }

        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(OneUiSpacing.Small),
        ) {
            if (!isFirstStep) {
                GlassSecondaryButton(
                    text = "Back",
                    onClick = {
                        haptics.performHapticFeedback(HapticFeedbackType.TextHandleMove)
                        onBack()
                    },
                    enabled = !isBusy,
                    contentDescription = "Back to previous step",
                )
            }
            GlassPrimaryButton(
                text = if (isLastStep) finalActionLabel else "Continue",
                onClick = {
                    haptics.performHapticFeedback(HapticFeedbackType.TextHandleMove)
                    onNext()
                },
                enabled = canProceed && !isBusy,
                contentDescription =
                    if (isLastStep) {
                        finalActionContentDescription
                    } else {
                        "Continue to next step"
                    },
                modifier = Modifier.weight(1f),
            )
        }
    }
}
