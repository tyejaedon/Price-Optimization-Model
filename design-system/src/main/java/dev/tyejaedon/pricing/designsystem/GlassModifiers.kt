package dev.tyejaedon.pricing.designsystem

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.runtime.compositionLocalOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.composed
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import dev.chrisbanes.haze.HazeState
import dev.chrisbanes.haze.HazeStyle
import dev.chrisbanes.haze.hazeChild

val LocalHazeState = compositionLocalOf<HazeState?> { null }

/**
 * Primary glassmorphic card surface combining optional Haze real-time background blur (API 31+),
 * multi-stop translucent vertical gradient fill, and a 1dp specular top-to-bottom rim border.
 */
fun Modifier.glassCard(
    shape: Shape = OneUiShapes.OuterContainer,
    specularRim: Boolean = true,
    blurRadius: Dp = 22.dp,
): Modifier =
    composed {
        val glass = LocalOneUiGlassColors.current
        val hazeState = LocalHazeState.current

        val base = this.clip(shape)
        val withBlur =
            if (hazeState != null) {
                base.hazeChild(
                    state = hazeState,
                    shape = shape,
                    style =
                        HazeStyle(
                            tint = glass.glassSurfaceTop.copy(alpha = 0.25f),
                            blurRadius = blurRadius,
                        ),
                )
            } else {
                base
            }

        val withFill = withBlur.background(brush = glass.glassCardBrush, shape = shape)
        if (specularRim) {
            withFill.border(width = 1.dp, brush = glass.specularRimBrush, shape = shape)
        } else {
            withFill
        }
    }

/**
 * Elevated glassmorphic surface for floating navigation docks, modal bottom sheets, and menus.
 */
fun Modifier.glassElevated(
    shape: Shape = OneUiShapes.BottomSheet,
    blurRadius: Dp = 32.dp,
    shadowElevation: Dp = 16.dp,
): Modifier =
    composed {
        val glass = LocalOneUiGlassColors.current
        val hazeState = LocalHazeState.current

        val base =
            this
                .shadow(
                    elevation = shadowElevation,
                    shape = shape,
                    ambientColor = Color.Black.copy(alpha = 0.4f),
                    spotColor = Color.Black.copy(alpha = 0.35f),
                ).clip(shape)

        val withBlur =
            if (hazeState != null) {
                base.hazeChild(
                    state = hazeState,
                    shape = shape,
                    style =
                        HazeStyle(
                            tint = glass.glassElevatedTop.copy(alpha = 0.32f),
                            blurRadius = blurRadius,
                        ),
                )
            } else {
                base
            }

        withBlur
            .background(brush = glass.glassElevatedBrush, shape = shape)
            .border(width = 1.dp, brush = glass.elevatedRimBrush, shape = shape)
    }

/**
 * Recessed glass well for text inputs, dropdown selectors, and inactive pills.
 */
fun Modifier.recessedGlassWell(
    shape: Shape = OneUiShapes.InputWell,
    focused: Boolean = false,
): Modifier =
    composed {
        val glass = LocalOneUiGlassColors.current
        val borderColor =
            if (focused) {
                glass.primaryAccent.copy(alpha = 0.72f)
            } else {
                glass.recessedWellBorder
            }
        val borderWidth = if (focused) 1.5.dp else 0.75.dp
        this
            .clip(shape)
            .background(color = glass.recessedWellFill, shape = shape)
            .border(width = borderWidth, color = borderColor, shape = shape)
    }

/**
 * One UI tactile press physics: springs to 0.97x scale and subtly shifts luminance when pressed.
 */
fun Modifier.oneUiPressPhysics(
    interactionSource: MutableInteractionSource? = null,
    enabled: Boolean = true,
): Modifier =
    composed {
        val resolvedSource = interactionSource ?: remember { MutableInteractionSource() }
        val isPressed by resolvedSource.collectIsPressedAsState()
        val scale by animateFloatAsState(
            targetValue = if (enabled && isPressed) OneUiMotion.PRESS_SCALE else 1f,
            animationSpec = OneUiMotion.PressSpring,
            label = "oneUiPressScale",
        )
        val alpha by animateFloatAsState(
            targetValue = if (enabled && isPressed) 0.92f else 1f,
            animationSpec = OneUiMotion.PressSpring,
            label = "oneUiPressAlpha",
        )
        this.graphicsLayer {
            scaleX = scale
            scaleY = scale
            this.alpha = alpha
        }
    }
