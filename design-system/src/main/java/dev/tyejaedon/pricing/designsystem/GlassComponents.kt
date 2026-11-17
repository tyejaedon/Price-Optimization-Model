package dev.tyejaedon.pricing.designsystem

import androidx.compose.animation.animateColorAsState
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsFocusedAsState
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.KeyboardArrowUp
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.SheetState
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextField
import androidx.compose.material3.TextFieldDefaults
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp

/**
 * One UI grouped translucent glass card (`24dp-26dp` rounded corners, `20dp` internal padding).
 */
@Composable
fun GlassCard(
    modifier: Modifier = Modifier,
    shape: Shape = OneUiShapes.OuterContainer,
    contentPadding: PaddingValues = PaddingValues(OneUiSpacing.CardPadding),
    onClick: (() -> Unit)? = null,
    content: @Composable ColumnScope.() -> Unit,
) {
    val interactionSource = remember { MutableInteractionSource() }
    val cardModifier =
        modifier
            .then(
                if (onClick != null) {
                    Modifier
                        .oneUiPressPhysics(interactionSource = interactionSource)
                        .glassCard(shape = shape)
                        .clickable(
                            interactionSource = interactionSource,
                            indication = null,
                            onClick = onClick,
                        )
                } else {
                    Modifier.glassCard(shape = shape)
                },
            ).padding(contentPadding)

    Column(modifier = cardModifier, content = content)
}

/**
 * Subtle One UI inset divider (`start = 16.dp`, `alpha = 0.08f`) for rows inside a [GlassCard].
 */
@Composable
fun GlassInsetDivider(
    modifier: Modifier = Modifier,
    startIndent: Dp = OneUiSpacing.Medium,
) {
    val glass = LocalOneUiGlassColors.current
    HorizontalDivider(
        modifier = modifier.padding(start = startIndent),
        thickness = 0.75.dp,
        color = glass.insetDivider,
    )
}

/**
 * Primary pill CTA with Electric Cobalt -> Indigo horizontal gradient and tactile spring physics.
 */
@Composable
fun GlassPrimaryButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    contentDescription: String? = null,
) {
    val interactionSource = remember { MutableInteractionSource() }
    val glass = LocalOneUiGlassColors.current

    Box(
        modifier =
            modifier
                .defaultMinSize(minHeight = OneUiSpacing.MinTouchTarget)
                .oneUiPressPhysics(interactionSource = interactionSource, enabled = enabled)
                .clip(CircleShape)
                .then(
                    if (enabled) {
                        Modifier.background(brush = glass.primaryPillBrush, shape = CircleShape)
                    } else {
                        Modifier.background(
                            color = glass.primaryAccent.copy(alpha = 0.30f),
                            shape = CircleShape,
                        )
                    },
                ).border(
                    width = 1.dp,
                    color = Color.White.copy(alpha = if (enabled) 0.28f else 0.10f),
                    shape = CircleShape,
                ).clickable(
                    interactionSource = interactionSource,
                    indication = null,
                    enabled = enabled,
                    role = Role.Button,
                    onClick = onClick,
                ).semantics {
                    if (contentDescription != null) {
                        this.contentDescription = contentDescription
                    }
                }.padding(horizontal = OneUiSpacing.Large, vertical = 12.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = text,
            style = MaterialTheme.typography.labelLarge.copy(fontWeight = FontWeight.SemiBold),
            color = if (enabled) Color.White else Color.White.copy(alpha = 0.65f),
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
    }
}

/**
 * Secondary translucent glass pill button with specular rim border and tactile spring physics.
 */
@Composable
fun GlassSecondaryButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    contentDescription: String? = null,
) {
    val interactionSource = remember { MutableInteractionSource() }
    val glass = LocalOneUiGlassColors.current

    Box(
        modifier =
            modifier
                .defaultMinSize(minHeight = OneUiSpacing.MinTouchTarget)
                .oneUiPressPhysics(interactionSource = interactionSource, enabled = enabled)
                .glassCard(shape = CircleShape)
                .clickable(
                    interactionSource = interactionSource,
                    indication = null,
                    enabled = enabled,
                    role = Role.Button,
                    onClick = onClick,
                ).semantics {
                    if (contentDescription != null) {
                        this.contentDescription = contentDescription
                    }
                }.padding(horizontal = OneUiSpacing.Large, vertical = 12.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = text,
            style = MaterialTheme.typography.labelLarge,
            color = if (enabled) glass.textPrimary else glass.textMuted,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
    }
}

/**
 * Borderless text field seated inside a `16dp` recessed glass well with soft accent focus ring.
 */
@Composable
fun GlassTextField(
    value: String,
    onValueChange: (String) -> Unit,
    label: String,
    modifier: Modifier = Modifier,
    supportingText: String? = null,
    leadingIcon: @Composable (() -> Unit)? = null,
    trailingIcon: @Composable (() -> Unit)? = null,
    singleLine: Boolean = true,
    minLines: Int = 1,
    readOnly: Boolean = false,
    keyboardOptions: KeyboardOptions = KeyboardOptions.Default,
    visualTransformation: VisualTransformation = VisualTransformation.None,
    textFieldModifier: Modifier = Modifier,
) {
    val glass = LocalOneUiGlassColors.current
    val interactionSource = remember { MutableInteractionSource() }
    val focused by interactionSource.collectIsFocusedAsState()

    Column(modifier = modifier.fillMaxWidth()) {
        Box(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .heightIn(min = OneUiSpacing.InputMinHeight)
                    .recessedGlassWell(shape = OneUiShapes.InputWell, focused = focused),
        ) {
            TextField(
                value = value,
                onValueChange = onValueChange,
                label = { Text(label) },
                leadingIcon = leadingIcon,
                trailingIcon = trailingIcon,
                singleLine = singleLine,
                minLines = minLines,
                readOnly = readOnly,
                keyboardOptions = keyboardOptions,
                visualTransformation = visualTransformation,
                interactionSource = interactionSource,
                colors =
                    TextFieldDefaults.colors(
                        focusedContainerColor = Color.Transparent,
                        unfocusedContainerColor = Color.Transparent,
                        disabledContainerColor = Color.Transparent,
                        focusedIndicatorColor = Color.Transparent,
                        unfocusedIndicatorColor = Color.Transparent,
                        disabledIndicatorColor = Color.Transparent,
                        focusedLabelColor = glass.primaryAccent,
                        unfocusedLabelColor = glass.textMuted,
                        focusedTextColor = glass.textPrimary,
                        unfocusedTextColor = glass.textPrimary,
                        cursorColor = glass.primaryAccent,
                    ),
                modifier = textFieldModifier.fillMaxWidth(),
            )
        }
        if (supportingText != null) {
            Text(
                text = supportingText,
                style = MaterialTheme.typography.labelSmall,
                color = glass.textMuted,
                modifier = Modifier.padding(start = 12.dp, top = 4.dp),
            )
        }
    }
}

/**
 * Dropdown selector styled in a `16dp` recessed glass well with frosted elevated menu surface.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun GlassDropdownField(
    label: String,
    displayValue: String,
    expanded: Boolean,
    onExpandedChange: (Boolean) -> Unit,
    modifier: Modifier = Modifier,
    anchorSemanticsDescription: String? = null,
    menuContent: @Composable ColumnScope.() -> Unit,
) {
    val glass = LocalOneUiGlassColors.current
    ExposedDropdownMenuBox(
        expanded = expanded,
        onExpandedChange = onExpandedChange,
        modifier = modifier,
    ) {
        Box(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .heightIn(min = OneUiSpacing.InputMinHeight)
                    .recessedGlassWell(shape = OneUiShapes.InputWell, focused = expanded)
                    .menuAnchor(),
        ) {
            TextField(
                value = displayValue,
                onValueChange = {},
                readOnly = true,
                label = { Text(label) },
                trailingIcon = {
                    Icon(
                        imageVector = if (expanded) Icons.Filled.KeyboardArrowUp else Icons.Filled.KeyboardArrowDown,
                        contentDescription = null,
                        tint = glass.textSecondary,
                    )
                },
                colors =
                    TextFieldDefaults.colors(
                        focusedContainerColor = Color.Transparent,
                        unfocusedContainerColor = Color.Transparent,
                        focusedIndicatorColor = Color.Transparent,
                        unfocusedIndicatorColor = Color.Transparent,
                        focusedLabelColor = glass.primaryAccent,
                        unfocusedLabelColor = glass.textMuted,
                        focusedTextColor = glass.textPrimary,
                        unfocusedTextColor = glass.textPrimary,
                    ),
                modifier =
                    Modifier
                        .fillMaxWidth()
                        .semantics {
                            if (anchorSemanticsDescription != null) {
                                contentDescription = anchorSemanticsDescription
                            }
                        },
            )
        }
        ExposedDropdownMenu(
            expanded = expanded,
            onDismissRequest = { onExpandedChange(false) },
            modifier =
                Modifier.background(
                    if (glass.isDark) Color(0xFF1D2230) else Color(0xFFFDFEFF),
                ),
            content = menuContent,
        )
    }
}

@Composable
fun GlassDropdownItem(
    text: String,
    onClick: () -> Unit,
) {
    val glass = LocalOneUiGlassColors.current
    DropdownMenuItem(
        text = { Text(text = text, color = glass.textPrimary, style = MaterialTheme.typography.bodyLarge) },
        onClick = onClick,
    )
}

/**
 * Floating frosted glass pill dock anchored at the bottom interaction zone.
 */
@Composable
fun <T> GlassFloatingNavDock(
    items: List<T>,
    selectedItem: T,
    onSelectItem: (T) -> Unit,
    labelProvider: (T) -> String,
    modifier: Modifier = Modifier,
) {
    val glass = LocalOneUiGlassColors.current

    Row(
        modifier =
            modifier
                .fillMaxWidth()
                .glassElevated(shape = CircleShape, blurRadius = 30.dp, shadowElevation = 14.dp)
                .padding(6.dp),
        horizontalArrangement = Arrangement.spacedBy(4.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        items.forEach { item ->
            val selected = item == selectedItem
            val interactionSource = remember { MutableInteractionSource() }
            val pillColor by animateColorAsState(
                targetValue =
                    if (selected) {
                        glass.primaryAccent.copy(alpha = if (glass.isDark) 0.28f else 0.16f)
                    } else {
                        Color.Transparent
                    },
                animationSpec = OneUiMotion.TransitionTween as androidx.compose.animation.core.AnimationSpec<Color>,
                label = "dockPillColor",
            )
            val contentColor by animateColorAsState(
                targetValue = if (selected) glass.primaryAccent else glass.textSecondary,
                animationSpec = OneUiMotion.TransitionTween as androidx.compose.animation.core.AnimationSpec<Color>,
                label = "dockTextColor",
            )

            Box(
                modifier =
                    Modifier
                        .weight(1f)
                        .defaultMinSize(minHeight = OneUiSpacing.MinTouchTarget)
                        .oneUiPressPhysics(interactionSource = interactionSource)
                        .clip(CircleShape)
                        .background(color = pillColor, shape = CircleShape)
                        .then(
                            if (selected) {
                                Modifier.border(
                                    width = 1.dp,
                                    color = glass.primaryAccent.copy(alpha = 0.35f),
                                    shape = CircleShape,
                                )
                            } else {
                                Modifier
                            },
                        ).clickable(
                            interactionSource = interactionSource,
                            indication = null,
                            role = Role.Tab,
                            onClick = { onSelectItem(item) },
                        ).padding(horizontal = 8.dp, vertical = 10.dp),
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    text = labelProvider(item),
                    color = contentColor,
                    style =
                        MaterialTheme.typography.labelLarge.copy(
                            fontWeight = if (selected) FontWeight.Bold else FontWeight.Medium,
                        ),
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }
    }
}

/**
 * Translucent semantic status pill badge with high-contrast tint and 1dp border.
 */
@Composable
fun GlassStatusBadge(
    text: String,
    tint: Color,
    modifier: Modifier = Modifier,
) {
    Box(
        modifier =
            modifier
                .clip(CircleShape)
                .background(color = tint.copy(alpha = 0.16f), shape = CircleShape)
                .border(border = BorderStroke(1.dp, tint.copy(alpha = 0.28f)), shape = CircleShape)
                .padding(horizontal = 12.dp, vertical = 5.dp),
    ) {
        Text(
            text = text,
            color = tint,
            style = MaterialTheme.typography.labelSmall,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
    }
}

/**
 * Plump One UI pill switch.
 */
@Composable
fun GlassSwitch(
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit,
    modifier: Modifier = Modifier,
) {
    val glass = LocalOneUiGlassColors.current
    Switch(
        checked = checked,
        onCheckedChange = onCheckedChange,
        modifier = modifier,
        colors =
            SwitchDefaults.colors(
                checkedThumbColor = Color.White,
                checkedTrackColor = glass.primaryAccent,
                checkedBorderColor = glass.primaryAccentDeep,
                uncheckedThumbColor = glass.textSecondary,
                uncheckedTrackColor = glass.recessedWellFill,
                uncheckedBorderColor = glass.recessedWellBorder,
            ),
    )
}

/**
 * Floating rounded One UI glass bottom sheet replacing boxy AlertDialogs.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun GlassModalBottomSheet(
    onDismissRequest: () -> Unit,
    title: String,
    modifier: Modifier = Modifier,
    sheetState: SheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
    actions: @Composable RowScope.() -> Unit,
    content: @Composable ColumnScope.() -> Unit,
) {
    val glass = LocalOneUiGlassColors.current
    ModalBottomSheet(
        onDismissRequest = onDismissRequest,
        sheetState = sheetState,
        shape = OneUiShapes.BottomSheet,
        containerColor = Color.Transparent,
        scrimColor = Color.Black.copy(alpha = 0.55f),
        dragHandle = null,
    ) {
        Column(
            modifier =
                modifier
                    .fillMaxWidth()
                    .padding(horizontal = OneUiSpacing.Medium, vertical = OneUiSpacing.Small)
                    .navigationBarsPadding()
                    .glassElevated(shape = RoundedCornerShape(28.dp))
                    .padding(OneUiSpacing.Large),
            verticalArrangement = Arrangement.spacedBy(OneUiSpacing.Medium),
        ) {
            Box(
                modifier =
                    Modifier
                        .align(Alignment.CenterHorizontally)
                        .width(42.dp)
                        .height(4.dp)
                        .clip(CircleShape)
                        .background(glass.textMuted.copy(alpha = 0.4f)),
            )
            Text(
                text = title,
                style = MaterialTheme.typography.titleLarge,
                color = glass.textPrimary,
            )
            content()
            Spacer(modifier = Modifier.height(OneUiSpacing.ExtraSmall))
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(OneUiSpacing.Small),
                content = actions,
            )
        }
    }
}

/**
 * Encouraging One UI glass empty-state card with an icon, clear value-oriented headline,
 * supporting explanation, and optional single primary action.
 */
@Composable
fun OneUiEmptyStateCard(
    icon: ImageVector,
    title: String,
    description: String,
    modifier: Modifier = Modifier,
    actionLabel: String? = null,
    onAction: (() -> Unit)? = null,
) {
    val glass = LocalOneUiGlassColors.current
    GlassCard(modifier = modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.fillMaxWidth(),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(OneUiSpacing.Small),
        ) {
            Box(
                modifier =
                    Modifier
                        .clip(CircleShape)
                        .background(glass.primaryAccent.copy(alpha = 0.14f))
                        .padding(14.dp),
            ) {
                Icon(
                    imageVector = icon,
                    contentDescription = null,
                    tint = glass.primaryAccent,
                )
            }
            Text(
                text = title,
                style = MaterialTheme.typography.titleMedium,
                color = glass.textPrimary,
            )
            Text(
                text = description,
                style = MaterialTheme.typography.bodyMedium,
                color = glass.textSecondary,
                textAlign = androidx.compose.ui.text.style.TextAlign.Center,
            )
            if (actionLabel != null && onAction != null) {
                Spacer(modifier = Modifier.height(OneUiSpacing.ExtraSmall))
                GlassPrimaryButton(
                    text = actionLabel,
                    onClick = onAction,
                )
            }
        }
    }
}
