package com.dupley.tgwssproxy;

import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Build;
import android.os.VibrationEffect;
import android.os.Vibrator;
import android.provider.Settings;
import androidx.annotation.NonNull;
import androidx.biometric.BiometricPrompt;
import androidx.core.content.ContextCompat;
import androidx.fragment.app.FragmentActivity;
import androidx.security.crypto.EncryptedSharedPreferences;
import androidx.security.crypto.MasterKeys;
import com.chaquo.python.PyObject;
import com.chaquo.python.Python;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.google.ai.client.generativeai.GenerativeModel;
import com.google.ai.client.generativeai.java.GenerativeModelFutures;
import com.google.ai.client.generativeai.type.Content;
import com.google.ai.client.generativeai.type.GenerateContentResponse;
import com.google.common.util.concurrent.FutureCallback;
import com.google.common.util.concurrent.Futures;
import com.google.common.util.concurrent.ListenableFuture;
import java.util.HashMap;
import java.util.Iterator;
import java.util.Map;
import java.util.concurrent.Executor;
import org.json.JSONObject;

@CapacitorPlugin(name = "ProxyControl")
public class ProxyPlugin extends Plugin {

    private static final String PREFS_NAME = "proxy_settings";
    private static final String SECURE_PREFS_NAME = "proxy_secure_settings";
    private static final String KEY_PORT = "proxy_port";
    private static final String KEY_AUTO_PORT = "auto_port";
    private static final String KEY_USER = "proxy_user";
    private static final String KEY_PASS = "proxy_pass";
    private static final String KEY_WIFI_ONLY = "wifi_only";
    private static final String KEY_GEMINI_KEY = "gemini_api_key";
    
    private static ProxyPlugin instance;

    @Override
    public void load() {
        super.load();
        instance = this;
    }

    @PluginMethod
    public void analyzeLogsWithAI(PluginCall call) {
        SharedPreferences securePrefs = getSecurePrefs();
        String apiKey = securePrefs.getString(KEY_GEMINI_KEY, "");
        
        if (apiKey.isEmpty()) {
            call.reject("Gemini API Key not set. Please provide it in settings.");
            return;
        }

        try {
            Python py = Python.getInstance();
            PyObject module = py.getModule("android_entry");
            String logs = module.callAttr("get_recent_logs").toString();
            String crashLogs = module.callAttr("get_crash_logs").toString();

            GenerativeModel gm = new GenerativeModel("gemini-1.5-flash", apiKey);
            GenerativeModelFutures model = GenerativeModelFutures.from(gm);

            String prompt = "Analyze these Telegram Proxy logs and suggest a solution for any errors found. " +
                           "Keep it concise and in Russian language. Logs:\n" + logs + "\nCrash History:\n" + crashLogs;

            Content content = new Content.Builder().addText(prompt).build();
            ListenableFuture<GenerateContentResponse> response = model.generateContent(content);

            Futures.addCallback(response, new FutureCallback<GenerateContentResponse>() {
                @Override
                public void onSuccess(GenerateContentResponse result) {
                    JSObject ret = new JSObject();
                    ret.put("analysis", result.getText());
                    call.resolve(ret);
                }

                @Override
                public void onFailure(@NonNull Throwable t) {
                    call.reject("AI Analysis failed: " + t.getMessage());
                }
            }, ContextCompat.getMainExecutor(getContext()));

        } catch (Exception e) {
            call.reject(e.getMessage());
        }
    }

    @PluginMethod
    public void setGeminiKey(PluginCall call) {
        String key = call.getString("key");
        if (key != null) {
            getSecurePrefs().edit().putString(KEY_GEMINI_KEY, key).apply();
            call.resolve();
        } else {
            call.reject("Key is missing");
        }
    }

    @PluginMethod
    public void authenticate(PluginCall call) {
        getBridge().executeOnMainThread(() -> {
            Executor executor = ContextCompat.getMainExecutor(getContext());
            BiometricPrompt biometricPrompt = new BiometricPrompt((FragmentActivity) getActivity(),
                    executor, new BiometricPrompt.AuthenticationCallback() {
                @Override
                public void onAuthenticationSucceeded(@NonNull BiometricPrompt.AuthenticationResult result) {
                    super.onAuthenticationSucceeded(result);
                    call.resolve();
                }

                @Override
                public void onAuthenticationError(int errorCode, @NonNull CharSequence errString) {
                    super.onAuthenticationError(errorCode, errString);
                    call.reject(errString.toString());
                }

                @Override
                public void onAuthenticationFailed() {
                    super.onAuthenticationFailed();
                }
            });

            BiometricPrompt.PromptInfo promptInfo = new BiometricPrompt.PromptInfo.Builder()
                    .setTitle("Authentication Required")
                    .setSubtitle("Authenticate to access proxy settings")
                    .setNegativeButtonText("Cancel")
                    .build();

            biometricPrompt.authenticate(promptInfo);
        });
    }

    @PluginMethod
    public void setWifiOnly(PluginCall call) {
        Boolean wifiOnly = call.getBoolean("enabled");
        if (wifiOnly != null) {
            SharedPreferences prefs = getContext().getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
            prefs.edit().putBoolean(KEY_WIFI_ONLY, wifiOnly).apply();
            call.resolve();
        } else {
            call.reject("Missing 'enabled' parameter");
        }
    }

    private SharedPreferences getSecurePrefs() {
        try {
            String masterKeyAlias = MasterKeys.getOrCreate(MasterKeys.AES256_GCM_SPEC);
            return EncryptedSharedPreferences.create(
                SECURE_PREFS_NAME, masterKeyAlias, getContext(),
                EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
            );
        } catch (Exception e) {
            return getContext().getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
        }
    }

    @PluginMethod
    public void startProxy(PluginCall call) {
        saveSettings(call);
        vibrate(50);
        Intent serviceIntent = new Intent(getContext(), ProxyForegroundService.class);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) getContext().startForegroundService(serviceIntent);
        else getContext().startService(serviceIntent);
        JSObject ret = new JSObject();
        ret.put("status", "starting");
        call.resolve(ret);
    }

    @PluginMethod
    public void stopProxy(PluginCall call) {
        vibrate(100);
        Intent serviceIntent = new Intent(getContext(), ProxyForegroundService.class).setAction(ProxyForegroundService.ACTION_STOP_SERVICE);
        getContext().startService(serviceIntent);
        JSObject ret = new JSObject();
        ret.put("status", "stopping");
        call.resolve(ret);
    }

    private void vibrate(long duration) {
        Vibrator v = (Vibrator) getContext().getSystemService(Context.VIBRATOR_SERVICE);
        if (v != null) {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) v.vibrate(VibrationEffect.createOneShot(duration, VibrationEffect.DEFAULT_AMPLITUDE));
            else v.vibrate(duration);
        }
    }

    @PluginMethod
    public void getStats(PluginCall call) {
        JSObject ret = new JSObject();
        try {
            if (Python.isStarted()) {
                PyObject statsObj = Python.getInstance().getModule("android_entry").callAttr("get_proxy_stats_dict");
                Map<PyObject, PyObject> statsMap = statsObj.asMap();
                for (Map.Entry<PyObject, PyObject> entry : statsMap.entrySet()) {
                    String key = entry.getKey().toString();
                    PyObject val = entry.getValue();
                    if (val.isTrue() || val.isFalse()) ret.put(key, val.toBoolean());
                    else if (val.isInstance(Python.getInstance().getBuiltins().get("int"))) ret.put(key, val.toInt());
                    else if (val.isInstance(Python.getInstance().getBuiltins().get("float"))) ret.put(key, val.toDouble());
                    else ret.put(key, val.toString());
                }
            } else ret.put("error", "Python not started");
        } catch (Exception e) { ret.put("error", e.getMessage()); }
        call.resolve(ret);
    }

    public static void onStatusChanged(boolean active) {
        if (instance != null) {
            JSObject ret = new JSObject();
            ret.put("active", active);
            instance.notifyListeners("statusChange", ret);
        }
    }

    @PluginMethod
    public void getSettings(PluginCall call) {
        SharedPreferences normalPrefs = getContext().getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
        SharedPreferences securePrefs = getSecurePrefs();
        JSObject ret = new JSObject();
        ret.put("port", normalPrefs.getInt(KEY_PORT, 1080));
        ret.put("autoPort", normalPrefs.getBoolean(KEY_AUTO_PORT, true));
        ret.put("wifiOnly", normalPrefs.getBoolean(KEY_WIFI_ONLY, false));
        ret.put("username", securePrefs.getString(KEY_USER, ""));
        ret.put("password", securePrefs.getString(KEY_PASS, ""));
        call.resolve(ret);
    }

    private void saveSettings(PluginCall call) {
        Integer port = call.getInt("port");
        Boolean autoPort = call.getBoolean("autoPort");
        Boolean wifiOnly = call.getBoolean("wifiOnly");
        String user = call.getString("username");
        String pass = call.getString("password");
        
        SharedPreferences.Editor normalEditor = getContext().getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE).edit();
        if (port != null) normalEditor.putInt(KEY_PORT, port);
        if (autoPort != null) normalEditor.putBoolean(KEY_AUTO_PORT, autoPort);
        if (wifiOnly != null) normalEditor.putBoolean(KEY_WIFI_ONLY, wifiOnly);
        normalEditor.apply();

        if (user != null || pass != null) {
            SharedPreferences.Editor secureEditor = getSecurePrefs().edit();
            if (user != null) secureEditor.putString(KEY_USER, user);
            if (pass != null) secureEditor.putString(KEY_PASS, pass);
            secureEditor.apply();
        }
    }
}
