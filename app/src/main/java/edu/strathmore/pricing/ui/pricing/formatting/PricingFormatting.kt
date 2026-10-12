package edu.strathmore.pricing.ui.pricing.formatting

import java.text.NumberFormat
import java.util.Locale

internal fun formatKesRate(rate: Float): String =
    NumberFormat
        .getNumberInstance(Locale.getDefault())
        .apply {
            maximumFractionDigits = 0
            minimumFractionDigits = 0
        }.format(rate)
