package com.dupley.tgwssproxy;

import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.BatteryManager;
import android.os.Build;
import android.os.VibrationEffect;
import android.os.Vibrator;
import android.provider.Settings;
import android.util.Base64;
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
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.util.HashMap;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.concurrent.Executor;
import javax.crypto.Cipher;
import javax.crypto.spec.IvParameterSpec;
import javax.crypto.spec.SecretKeySpec;
import org.json.JSONObject;

@CapacitorPlugin(name = "ProxyControl")
public class ProxyPlugin extends Plugin {

    private static final String PREFS_NAME = "proxy_settings";
    private static final String SECURE_PREFS_NAME = "proxy_secure_settings";
    private static final String KEY_PORT = "proxy_port";
    private static final String KEY_AUTO_PORT = "auto_port";
    private static final String KEY_USER = "proxy_user";
    private static final String KEY_PASS = "proxy_pass";
    private static final String KEY_GEMINI_KEY = "gemini_api_key";
    
    private static ProxyPlugin instance;

    @Override
    public void load() {
        super.load();
        instance = this;
    }

    @PluginMethod
    public void predictNetworkIssues(PluginCall call) {
        SharedPreferences securePrefs = getSecurePrefs();
        String apiKey = securePrefs.getString(KEY_GEMINI_KEY, "");
        if (apiKey.isEmpty()) {
            call.reject("Gemini Key required");
            return;
        }

        try {
            JSObject stats = getStatsInternal();
            GenerativeModel gm = new GenerativeModel("gemini-1.5-flash", apiKey);
            GenerativeModelFutures model = GenerativeModelFutures.from(gm);

            String prompt = "На основе этой статистики прокси: " + stats.toString() + 
                           "\nСделай предиктивный анализ: есть ли риск обрыва соединения или блокировки? " +
                           "Ответь очень кратко на русском.";

            Content content = new Content.Builder().addText(prompt).build();
            ListenableFuture<GenerateContentResponse> response = model.generateContent(content);
            Futures.addCallback(response, new FutureCallback<GenerateContentResponse>() {
                @Override
                public void onSuccess(GenerateContentResponse result) {
                    JSObject ret = new JSObject();
                    ret.put("prediction", result.getText());
                    call.resolve(ret);
                }
                @Override
                public void onFailure(@NonNull Throwable t) { call.reject(t.getMessage()); }
            }, ContextCompat.getMainExecutor(getContext()));
        } catch (Exception e) { call.reject(e.getMessage()); }
    }

    @PluginMethod
    public void getBatteryAnalytics(PluginCall call) {
        JSObject ret = new JSObject();
        try {
            BatteryManager bm = (BatteryManager) getContext().getSystemService(Context.BATTERY_SERVICE);
            if (bm != null) {
                ret.put("capacity", bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY));
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                    ret.put("isCharging", bm.isCharging());
                }
            }
            call.resolve(ret);
        } catch (Exception e) { call.reject(e.getMessage()); }
    }

    @PluginMethod
    public void exportConfigEncrypted(PluginCall call) {
        String password = call.getString("password");
        if (password == null) { call.reject("Password required"); return; }
        try {
            SharedPreferences prefs = getContext().getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
            SharedPreferences securePrefs = getSecurePrefs();
            JSONObject config = new JSONObject();
            config.put("port", prefs.getInt(KEY_PORT, 1080));
            config.put("username", securePrefs.getString(KEY_USER, ""));
            config.put("password", securePrefs.getString(KEY_PASS, ""));
            String encrypted = encrypt(config.toString(), password);
            JSObject ret = new JSObject();
            ret.put("data", encrypted);
            call.resolve(ret);
        } catch (Exception e) { call.reject(e.getMessage()); }
    }

    @PluginMethod
    public void importConfigEncrypted(PluginCall call) {
        String data = call.getString("data");
        String password = call.getString("password");
        try {
            String decrypted = decrypt(data, password);
            JSONObject json = new JSONObject(decrypted);
            SharedPreferences.Editor editor = getContext().getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE).edit();
            if (json.has("port")) editor.putInt(KEY_PORT, json.getInt("port"));
            editor.apply();
            SharedPreferences.Editor secureEditor = getSecurePrefs().edit();
            if (json.has("username")) secureEditor.putString(KEY_USER, json.getString("username"));
            if (json.has("password")) secureEditor.putString(KEY_PASS, json.getString("password"));
            secureEditor.apply();
            call.resolve();
        } catch (Exception e) { call.reject("Import failed"); }
    }

    private String encrypt(String value, String password) throws Exception {
        byte[] key = MessageDigest.getInstance("SHA-256").digest(password.getBytes(StandardCharsets.UTF_8));
        SecretKeySpec secretKey = new SecretKeySpec(key, "AES");
        Cipher cipher = Cipher.getInstance("AES/CBC/PKCS5Padding");
        byte[] iv = new byte[16];
        new SecureRandom().nextBytes(iv);
        cipher.init(Cipher.ENCRYPT_MODE, secretKey, new IvParameterSpec(iv));
        byte[] encrypted = cipher.doFinal(value.getBytes(StandardCharsets.UTF_8));
        byte[] combined = new byte[iv.length + encrypted.length];
        System.arraycopy(iv, 0, combined, 0, iv.length);
        System.arraycopy(encrypted, 0, combined, iv.length, encrypted.length);
        return Base64.encodeToString(combined, Base64.NO_WRAP);
    }

    private String decrypt(String combinedBase64, String password) throws Exception {
        byte[] combined = Base64.decode(combinedBase64, Base64.NO_WRAP);
        byte[] key = MessageDigest.getInstance("SHA-256").digest(password.getBytes(StandardCharsets.UTF_8));
        SecretKeySpec secretKey = new SecretKeySpec(key, "AES");
        Cipher cipher = Cipher.getInstance("AES/CBC/PKCS5Padding");
        byte[] iv = new byte[16];
        System.arraycopy(combined, 0, iv, 0, 16);
        cipher.init(Cipher.DECRYPT_MODE, secretKey, new IvParameterSpec(iv));
        return new String(cipher.doFinal(combined, 16, combined.length - 16));
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
        vibrate(50);
        Intent intent = new Intent(getContext(), ProxyForegroundService.class);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) getContext().startForegroundService(intent);
        else getContext().startService(intent);
        call.resolve();
    }

    @PluginMethod
    public void stopProxy(PluginCall call) {
        vibrate(100);
        Intent intent = new Intent(getContext(), ProxyForegroundService.class).setAction(ProxyForegroundService.ACTION_STOP_SERVICE);
        getContext().startService(intent);
        call.resolve();
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
}
