package com.dupley.tgwssproxy;

import android.content.Intent;
import android.os.Build;
import com.chaquo.python.PyObject;
import com.chaquo.python.Python;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import java.util.Map;

@CapacitorPlugin(name = "ProxyControl")
public class ProxyPlugin extends Plugin {

    @PluginMethod
    public void startProxy(PluginCall call) {
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
        Intent serviceIntent = new Intent(getContext(), ProxyForegroundService.class);
        serviceIntent.setAction(ProxyForegroundService.ACTION_STOP_SERVICE);
        getContext().startService(serviceIntent);
        JSObject ret = new JSObject();
        ret.put("status", "stopping");
        call.resolve(ret);
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
