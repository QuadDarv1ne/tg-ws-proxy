package com.dupley.tgwssproxy;

import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Build;
import android.os.VibrationEffect;
import android.os.Vibrator;
import android.provider.Settings;
import androidx.security.crypto.EncryptedSharedPreferences;
import androidx.security.crypto.MasterKeys;
import com.chaquo.python.PyObject;
import com.chaquo.python.Python;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import java.util.HashMap;
import java.util.Iterator;
import java.util.Map;
import org.json.JSONObject;

@CapacitorPlugin(name = "ProxyControl")
public class ProxyPlugin extends Plugin {

    private static final String PREFS_NAME = "proxy_settings";
    private static final String SECURE_PREFS_NAME = "proxy_secure_settings";
    private static final String KEY_PORT = "proxy_port";
    private static final String KEY_AUTO_PORT = "auto_port";
    private static final String KEY_USER = "proxy_user";
    private static final String KEY_PASS = "proxy_pass";
    private static final String KEY_PROFILES = "proxy_profiles";
    
    private static ProxyPlugin instance;

    @Override
    public void load() {
        super.load();
        instance = this;
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
    public void saveProfile(PluginCall call) {
        String name = call.getString("name");
        JSObject config = call.getObject("config");
        if (name == null || config == null) {
            call.reject("Name and config are required");
            return;
        }

        SharedPreferences prefs = getContext().getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
        try {
            JSONObject profiles;
            String existing = prefs.getString(KEY_PROFILES, "{}");
            profiles = new JSONObject(existing);
            profiles.put(name, config.toString());
            
            prefs.edit().putString(KEY_PROFILES, profiles.toString()).apply();
            call.resolve();
        } catch (Exception e) {
            call.reject(e.getMessage());
        }
    }

    @PluginMethod
    public void loadProfile(PluginCall call) {
        String name = call.getString("name");
        SharedPreferences prefs = getContext().getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
        try {
            JSONObject profiles = new JSONObject(prefs.getString(KEY_PROFILES, "{}"));
            if (profiles.has(name)) {
                String configStr = profiles.getString(name);
                importConfigInternal(configStr);
                call.resolve();
            } else {
                call.reject("Profile not found");
            }
        } catch (Exception e) {
            call.reject(e.getMessage());
        }
    }

    private void importConfigInternal(String jsonStr) throws Exception {
        JSONObject json = new JSONObject(jsonStr);
        SharedPreferences.Editor editor = getContext().getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE).edit();
        if (json.has("port")) editor.putInt(KEY_PORT, json.getInt("port"));
        if (json.has("autoPort")) editor.putBoolean(KEY_AUTO_PORT, json.getBoolean("autoPort"));
        editor.apply();

        if (json.has("username") || json.has("password")) {
            SharedPreferences.Editor secureEditor = getSecurePrefs().edit();
            if (json.has("username")) secureEditor.putString(KEY_USER, json.getString("username"));
            if (json.has("password")) secureEditor.putString(KEY_PASS, json.getString("password"));
            secureEditor.apply();
        }
    }

    public static void onStatusChanged(boolean active) {
        if (instance != null) {
            JSObject ret = new JSObject();
            ret.put("active", active);
            instance.notifyListeners("statusChange", ret);
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

    @PluginMethod
    public void getSettings(PluginCall call) {
        SharedPreferences normalPrefs = getContext().getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
        SharedPreferences securePrefs = getSecurePrefs();
        JSObject ret = new JSObject();
        ret.put("port", normalPrefs.getInt(KEY_PORT, 1080));
        ret.put("autoPort", normalPrefs.getBoolean(KEY_AUTO_PORT, true));
        ret.put("username", securePrefs.getString(KEY_USER, ""));
        ret.put("password", securePrefs.getString(KEY_PASS, ""));
        call.resolve(ret);
    }

    private void saveSettings(PluginCall call) {
        Integer port = call.getInt("port");
        Boolean autoPort = call.getBoolean("autoPort");
        String user = call.getString("username");
        String pass = call.getString("password");
        SharedPreferences.Editor normalEditor = getContext().getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE).edit();
        if (port != null) normalEditor.putInt(KEY_PORT, port);
        if (autoPort != null) normalEditor.putBoolean(KEY_AUTO_PORT, autoPort);
        normalEditor.apply();
        if (user != null || pass != null) {
            SharedPreferences.Editor secureEditor = getSecurePrefs().edit();
            if (user != null) secureEditor.putString(KEY_USER, user);
            if (pass != null) secureEditor.putString(KEY_PASS, pass);
            secureEditor.apply();
        }
    }
}
