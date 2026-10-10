# Keep DTO field names stable for Gson reflection-based (de)serialization.
-keepclassmembers class edu.strathmore.pricing.data.network.dto.** {
    <fields>;
}
-keep class edu.strathmore.pricing.data.network.dto.** { *; }

