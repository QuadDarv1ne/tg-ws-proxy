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
import com.getcapacitor.JSArray;
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
import java.util.List;
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
    private static final String KEY_BATTERY_LEVEL = "battery_threshold";
    
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
            call.reject("Gemini API Key not set.");
            return;
        }
        try {
            Python py = Python.getInstance();
            PyObject module = py.getModule("android_entry");
            String logs = module.callAttr("get_recent_logs").toString();
            String crashLogs = module.callAttr("get_crash_logs").toString();
            JSObject stats = getStatsInternal();

            GenerativeModel gm = new GenerativeModel("gemini-1.5-flash", apiKey);
            GenerativeModelFutures model = GenerativeModelFutures.from(gm);

            // Улучшенный промпт (Task 4)
            String systemInfo = String.format("Android: %s, SDK: %d, Device: %s, Proxy Stats: %s", 
                Build.VERSION.RELEASE, Build.VERSION.SDK_INT, Build.MODEL, stats.toString());

            String prompt = "Ты - эксперт по сетевым прокси. Проанализируй логи Telegram Proxy для Android и предложи решение проблемы. " +
                           "Отвечай кратко, технически грамотно и только на русском языке.\n\n" +
                           "ИНФОРМАЦИЯ О СИСТЕМЕ:\n" + systemInfo + "\n\n" +
                           "ЛОГИ:\n" + logs + "\n\nИСТОРИЯ ОШИБОК:\n" + crashLogs;

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
                public void onFailure(@NonNull Throwable t) { call.reject(t.getMessage()); }
            }, ContextCompat.getMainExecutor(getContext()));
        } catch (Exception e) { call.reject(e.getMessage()); }
    }

    @PluginMethod
    public void setBatteryThreshold(PluginCall call) {
        Integer level = call.getInt("level");
        if (level != null) {
            getContext().getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE).edit().putInt(KEY_BATTERY_LEVEL, level).apply();
            call.resolve();
        } else call.reject("Missing level");
    }

    @PluginMethod
    public void getStats(PluginCall call) {
        call.resolve(getStatsInternal());
    }

    private JSObject getStatsInternal() {
        JSObject ret = new JSObject();
        try {
            if (Python.isStarted()) {
                PyObject statsObj = Python.getInstance().getModule("android_entry").callAttr("get_proxy_stats_dict");
                Map<PyObject, PyObject> statsMap = statsObj.asMap();
                for (Map.Entry<PyObject, PyObject> entry : statsMap.entrySet()) {
                    String key = entry.getKey().toString();
                    PyObject val = entry.getValue();
                    if (val.isInstance(Python.getInstance().getBuiltins().get("list"))) {
                        JSArray jsArray = new JSArray();
                        for (PyObject item : val.asList()) jsArray.put(item.toString());
                        ret.put(key, jsArray);
                    } else if (val.isTrue() || val.isFalse()) ret.put(key, val.toBoolean());
                    else if (val.isInstance(Python.getInstance().getBuiltins().get("int"))) ret.put(key, val.toInt());
                    else if (val.isInstance(Python.getInstance().getBuiltins().get("float"))) ret.put(key, val.toDouble());
                    else ret.put(key, val.toString());
                }
            } else ret.put("error", "Python not started");
        } catch (Exception e) { ret.put("error", e.getMessage()); }
        return ret;
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

    private SharedPreferences getSecurePrefs() {
        try {
            String masterKeyAlias = MasterKeys.getOrCreate(MasterKeys.AES256_GCM_SPEC);
            return EncryptedSharedPreferences.create(SECURE_PREFS_NAME, masterKeyAlias, getContext(),
                EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM);
        } catch (Exception e) { return getContext().getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE); }
    }

    private void vibrate(long duration) {
        Vibrator v = (Vibrator) getContext().getSystemService(Context.VIBRATOR_SERVICE);
        if (v != null) {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) v.vibrate(VibrationEffect.createOneShot(duration, VibrationEffect.DEFAULT_AMPLITUDE));
            else v.vibrate(duration);
        }
    }

    public static void onStatusChanged(boolean active) {
        if (instance != null) {
            JSObject ret = new JSObject();
            ret.put("active", active);
            instance.notifyListeners("statusChange", ret);
        }
    }

    private void saveSettings(PluginCall call) {
        Integer port = call.getInt("port");
        Boolean autoPort = call.getBoolean("autoPort");
        Boolean wifiOnly = call.getBoolean("wifiOnly");
        SharedPreferences.Editor normalEditor = getContext().getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE).edit();
        if (port != null) normalEditor.putInt(KEY_PORT, port);
        if (autoPort != null) normalEditor.putBoolean(KEY_AUTO_PORT, autoPort);
        if (wifiOnly != null) normalEditor.putBoolean(KEY_WIFI_ONLY, wifiOnly);
        normalEditor.apply();
    }
}
