# Keep DTO field names stable for Gson reflection-based (de)serialization.
-keepclassmembers class dev.tyejaedon.pricing.admin.data.network.dto.** {
    <fields>;
}
-keep class dev.tyejaedon.pricing.admin.data.network.dto.** { *; }
