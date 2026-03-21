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

@CapacitorPlugin(name = "ProxyControl")
public class ProxyPlugin extends Plugin {

    private static final String PREFS_NAME = "proxy_settings";
    private static final String KEY_PORT = "proxy_port";
    private static final String KEY_AUTO_PORT = "auto_port";

    @PluginMethod
    public void startProxy(PluginCall call) {
        saveSettings(call);
        vibrate(50);
        
        Intent serviceIntent = new Intent(getContext(), ProxyForegroundService.class);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            getContext().startForegroundService(serviceIntent);
        } else {
            getContext().startService(serviceIntent);
        }
        JSObject ret = new JSObject();
        ret.put("status", "starting");
        call.resolve(ret);
    }

    @PluginMethod
    public void stopProxy(PluginCall call) {
        vibrate(100);
        Intent serviceIntent = new Intent(getContext(), ProxyForegroundService.class);
        serviceIntent.setAction(ProxyForegroundService.ACTION_STOP_SERVICE);
        getContext().startService(serviceIntent);
        JSObject ret = new JSObject();
        ret.put("status", "stopping");
        call.resolve(ret);
    }

    @PluginMethod
    public void openTelegramProxy(PluginCall call) {
        SharedPreferences prefs = getContext().getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
        int port = prefs.getInt(KEY_PORT, 1080);
        String url = "tg://socks?server=127.0.0.1&port=" + port;
        
        try {
            Intent intent = new Intent(Intent.ACTION_VIEW, Uri.parse(url));
            intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            getContext().startActivity(intent);
            call.resolve();
        } catch (Exception e) {
            call.reject("Could not open Telegram: " + e.getMessage());
        }
    }

    @PluginMethod
    public void openSystemProxySettings(PluginCall call) {
        try {
            Intent intent = new Intent(Settings.ACTION_WIFI_SETTINGS); // Прямого пути к Proxy нет, это лучший вариант
            intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            getContext().startActivity(intent);
            call.resolve();
        } catch (Exception e) {
            call.reject("Could not open settings: " + e.getMessage());
        }
    }

    private void vibrate(long duration) {
        Vibrator v = (Vibrator) getContext().getSystemService(Context.VIBRATOR_SERVICE);
        if (v != null) {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                v.vibrate(VibrationEffect.createOneShot(duration, VibrationEffect.DEFAULT_AMPLITUDE));
            } else {
                v.vibrate(duration);
            }
        }
    }

    @PluginMethod
    public void clearDNS(PluginCall call) {
        try {
            if (Python.isStarted()) {
                Python py = Python.getInstance();
                PyObject module = py.getModule("android_entry");
                boolean success = module.callAttr("clear_dns").toBoolean();
                JSObject ret = new JSObject();
                ret.put("success", success);
                call.resolve(ret);
            } else {
                call.reject("Python not started");
            }
        } catch (Exception e) {
            call.reject(e.getMessage());
        }
    }

    @PluginMethod
    public void setCustomDCs(PluginCall call) {
        JSObject dcs = call.getObject("dcs");
        if (dcs == null) {
            call.reject("Missing 'dcs' object. Format: { '2': '1.2.3.4' }");
            return;
        }

        try {
            if (Python.isStarted()) {
                Python py = Python.getInstance();
                PyObject module = py.getModule("android_entry");
                
                Map<String, String> dcMap = new HashMap<>();
                Iterator<String> keys = dcs.keys();
                while (keys.hasNext()) {
                    String key = keys.next();
                    dcMap.put(key, dcs.getString(key));
                }
                
                boolean success = module.callAttr("set_custom_dc_ips", dcMap).toBoolean();
                JSObject ret = new JSObject();
                ret.put("success", success);
                call.resolve(ret);
            } else {
                call.reject("Python not started");
            }
        } catch (Exception e) {
            call.reject(e.getMessage());
        }
    }

    @PluginMethod
    public void getSettings(PluginCall call) {
        SharedPreferences prefs = getContext().getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
        JSObject ret = new JSObject();
        ret.put("port", prefs.getInt(KEY_PORT, 1080));
        ret.put("autoPort", prefs.getBoolean(KEY_AUTO_PORT, true));
        call.resolve(ret);
    }

    private void saveSettings(PluginCall call) {
        Integer port = call.getInt("port");
        Boolean autoPort = call.getBoolean("autoPort");
        
        SharedPreferences.Editor editor = getContext().getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE).edit();
        if (port != null) editor.putInt(KEY_PORT, port);
        if (autoPort != null) editor.putBoolean(KEY_AUTO_PORT, autoPort);
        editor.apply();
    }

    @PluginMethod
    public void getStatus(PluginCall call) {
        JSObject ret = new JSObject();
        try {
            if (Python.isStarted()) {
                Python py = Python.getInstance();
                PyObject module = py.getModule("android_entry");
                boolean running = module.callAttr("is_running").toBoolean();
                ret.put("active", running);
            } else {
                ret.put("active", false);
            }
        } catch (Exception e) {
            ret.put("active", false);
            ret.put("error", e.getMessage());
        }
        call.resolve(ret);
    }

    @PluginMethod
    public void getLogs(PluginCall call) {
        JSObject ret = new JSObject();
        try {
            if (Python.isStarted()) {
                Python py = Python.getInstance();
                PyObject module = py.getModule("android_entry");
                String logs = module.callAttr("get_recent_logs").toString();
                ret.put("logs", logs);
            } else {
                ret.put("logs", "Python not started");
            }
        } catch (Exception e) {
            ret.put("error", e.getMessage());
        }
        call.resolve(ret);
    }

    @PluginMethod
    public void checkConnection(PluginCall call) {
        new Thread(() -> {
            try {
                if (Python.isStarted()) {
                    Python py = Python.getInstance();
                    PyObject module = py.getModule("android_entry");
                    PyObject resultObj = module.callAttr("test_connection_to_tg");
                    Map<PyObject, PyObject> resultMap = resultObj.asMap();
                    
                    JSObject ret = new JSObject();
                    for (Map.Entry<PyObject, PyObject> entry : resultMap.entrySet()) {
                        String key = entry.getKey().toString();
                        PyObject value = entry.getValue();
                        if (value.isTrue() || value.isFalse()) {
                            ret.put(key, value.toBoolean());
                        } else if (value.isInstance(py.getBuiltins().get("float"))) {
                            ret.put(key, value.toDouble());
                        } else {
                            ret.put(key, value.toString());
                        }
                    }
                    call.resolve(ret);
                } else {
                    call.reject("Python not started");
                }
            } catch (Exception e) {
                call.reject(e.getMessage());
            }
        }).start();
    }

    @PluginMethod
    public void getStats(PluginCall call) {
        JSObject ret = new JSObject();
        try {
            if (Python.isStarted()) {
                Python py = Python.getInstance();
                PyObject module = py.getModule("android_entry");
                PyObject statsObj = module.callAttr("get_proxy_stats_dict");
                Map<PyObject, PyObject> statsMap = statsObj.asMap();
                
                for (Map.Entry<PyObject, PyObject> entry : statsMap.entrySet()) {
                    String key = entry.getKey().toString();
                    PyObject value = entry.getValue();
                    
                    if (value.isTrue() || value.isFalse()) {
                        ret.put(key, value.toBoolean());
                    } else if (value.isInstance(py.getBuiltins().get("int"))) {
                        ret.put(key, value.toInt());
                    } else if (value.isInstance(py.getBuiltins().get("float"))) {
                        ret.put(key, value.toDouble());
                    } else {
                        ret.put(key, value.toString());
                    }
                }
            } else {
                ret.put("error", "Python not started");
            }
        } catch (Exception e) {
            ret.put("error", e.getMessage());
        }
        call.resolve(ret);
    }
}
