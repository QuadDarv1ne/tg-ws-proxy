package com.dupley.tgwssproxy;

import android.content.Context;
import android.util.Log;
import androidx.annotation.NonNull;
import androidx.work.Worker;
import androidx.work.WorkerParameters;
import com.chaquo.python.PyObject;
import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;

public class ConfigUpdateWorker extends Worker {
    private static final String TAG = "ConfigUpdateWorker";
    private static final String DEFAULT_CONFIG_URL = "https://raw.githubusercontent.com/dupley/tg-ws-proxy/main/dcs.json";

    public ConfigUpdateWorker(@NonNull Context context, @NonNull WorkerParameters params) {
        super(context, params);
    }

    @NonNull
    @Override
    public Result doWork() {
        Log.i(TAG, "Starting background config update...");
        
        try {
            if (!Python.isStarted()) {
                Python.start(new AndroidPlatform(getApplicationContext()));
            }
            
            Python py = Python.getInstance();
            PyObject module = py.getModule("android_entry");
            
            // Пытаемся обновить конфиг из удаленного источника
            boolean success = module.callAttr("update_dc_config_remote", DEFAULT_CONFIG_URL).toBoolean();
            
            if (success) {
                Log.i(TAG, "Config updated successfully in background");
                return Result.success();
            } else {
                Log.w(TAG, "Config update failed or no changes");
                return Result.retry();
            }
        } catch (Exception e) {
            Log.e(TAG, "Error in background update: " + e.getMessage());
            return Result.failure();
        }
    }
}
