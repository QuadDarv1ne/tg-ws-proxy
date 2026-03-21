# Специфические правила для Capacitor
-keep class com.getcapacitor.** { *; }
-keep @com.getcapacitor.NativePlugin public class *
-keep @com.getcapacitor.CapacitorPlugin public class *
-keepclassmembers class * extends com.getcapacitor.Plugin {
    @com.getcapacitor.PluginMethod public void *(com.getcapacitor.PluginCall);
}

# Для работы WebView и JavaScript интерфейсов
-keepattributes JavascriptInterface
-keepclassmembers class * {
    @android.webkit.JavascriptInterface <methods>;
}

# Предотвращение удаления классов моста
-keep class com.getcapacitor.Bridge { *; }
-keep class com.getcapacitor.MessageHandler { *; }

# Стандартные настройки для отладки (стек-трейсы)
-keepattributes SourceFile,LineNumberTable
-renamesourcefileattribute SourceFile
