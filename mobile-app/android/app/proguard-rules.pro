# Capacitor Specific Rules
-keep class com.getcapacitor.** { *; }
-keep @com.getcapacitor.NativePlugin public class *
-keep @com.getcapacitor.CapacitorPlugin public class *
-keepclassmembers class * extends com.getcapacitor.Plugin {
    @com.getcapacitor.PluginMethod public void *(com.getcapacitor.PluginCall);
}

# WebView & JS Interface
-keepattributes JavascriptInterface
-keepclassmembers class * {
    @android.webkit.JavascriptInterface <methods>;
}

# Bridge Classes
-keep class com.getcapacitor.Bridge { *; }
-keep class com.getcapacitor.MessageHandler { *; }

# Chaquopy Rules (though mostly automatic, these ensure bridge stability)
-keep class com.chaquo.python.** { *; }
-keepattributes *Annotation*, EnclosingMethod, InnerClasses, Signature

# App Specific Classes (to prevent obfuscation of our bridge)
-keep class com.dupley.tgwssproxy.** { *; }

# Stacktrace Debugging
-keepattributes SourceFile,LineNumberTable
-renamesourcefileattribute SourceFile
