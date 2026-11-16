package dev.tyejaedon.pricing.admin.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import dev.tyejaedon.pricing.admin.domain.IAdminRepository

class AdminViewModelFactory(
    private val repository: IAdminRepository,
) : ViewModelProvider.Factory {
    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>): T = AdminViewModel(repository) as T
}
