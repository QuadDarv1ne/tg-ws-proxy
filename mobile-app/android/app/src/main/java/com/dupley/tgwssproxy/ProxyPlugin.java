package com.dupley.tgwssproxy;

import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Build;
import android.os.VibrationEffect;
import android.os.Vibrator;
import android.provider.Settings;
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
    private static final String KEY_PORT = "proxy_port";
    private static final String KEY_AUTO_PORT = "auto_port";
    private static final String KEY_USER = "proxy_user";
    private static final String KEY_PASS = "proxy_pass";
    
    private static ProxyPlugin instance;

    @Override
    public void load() {
        super.load();
        instance = this;
    }

    public static void onStatusChanged(boolean active) {
        if (instance != null) {
            JSObject ret = new JSObject();
            ret.put("active", active);
            instance.notifyListeners("statusChange", ret);
        }
    }

    @PluginMethod
    public void exportConfig(PluginCall call) {
        SharedPreferences prefs = getContext().getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
        JSObject config = new JSObject();
        config.put("port", prefs.getInt(KEY_PORT, 1080));
        config.put("autoPort", prefs.getBoolean(KEY_AUTO_PORT, true));
        config.put("username", prefs.getString(KEY_USER, ""));
        config.put("password", prefs.getString(KEY_PASS, ""));
        
        JSObject ret = new JSObject();
        ret.put("json", config.toString());
        call.resolve(ret);
    }

    @PluginMethod
    public void importConfig(PluginCall call) {
        String jsonStr = call.getString("json");
        try {
            JSONObject json = new JSONObject(jsonStr);
            SharedPreferences.Editor editor = getContext().getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE).edit();
            if (json.has("port")) editor.putInt(KEY_PORT, json.getInt("port"));
            if (json.has("autoPort")) editor.putBoolean(KEY_AUTO_PORT, json.getBoolean("autoPort"));
            if (json.has("username")) editor.putString(KEY_USER, json.getString("username"));
            if (json.has("password")) editor.putString(KEY_PASS, json.getString("password"));
            editor.apply();
            call.resolve();
        } catch (Exception e) {
            call.reject("Invalid config format: " + e.getMessage());
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

    @PluginMethod
    public void setAuth(PluginCall call) {
        String user = call.getString("username");
        String pass = call.getString("password");
        SharedPreferences.Editor editor = getContext().getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE).edit();
        editor.putString(KEY_USER, user);
        editor.putString(KEY_PASS, pass);
        editor.apply();
        if (Python.isStarted()) Python.getInstance().getModule("android_entry").callAttr("set_auth", user, pass);
        call.resolve();
    }

    @PluginMethod
    public void getProxyUrl(PluginCall call) {
        SharedPreferences prefs = getContext().getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
        int port = prefs.getInt(KEY_PORT, 1080);
        String user = prefs.getString(KEY_USER, null);
        String pass = prefs.getString(KEY_PASS, null);
        String url = (user != null && !user.isEmpty()) 
            ? "https://t.me/socks?server=127.0.0.1&port=" + port + "&user=" + user + "&pass=" + pass
            : "https://t.me/socks?server=127.0.0.1&port=" + port;
        JSObject ret = new JSObject();
        ret.put("url", url);
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
        SharedPreferences prefs = getContext().getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
        JSObject ret = new JSObject();
        ret.put("port", prefs.getInt(KEY_PORT, 1080));
        ret.put("autoPort", prefs.getBoolean(KEY_AUTO_PORT, true));
        ret.put("username", prefs.getString(KEY_USER, ""));
        ret.put("password", prefs.getString(KEY_PASS, ""));
        call.resolve(ret);
    }

    private void saveSettings(PluginCall call) {
        Integer port = call.getInt("port");
        Boolean autoPort = call.getBoolean("autoPort");
        String user = call.getString("username");
        String pass = call.getString("password");
        SharedPreferences.Editor editor = getContext().getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE).edit();
        if (port != null) editor.putInt(KEY_PORT, port);
        if (autoPort != null) editor.putBoolean(KEY_AUTO_PORT, autoPort);
        if (user != null) editor.putString(KEY_USER, user);
        if (pass != null) editor.putString(KEY_PASS, pass);
        editor.apply();
    }
}
