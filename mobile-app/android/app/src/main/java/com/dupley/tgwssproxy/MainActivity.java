package com.dupley.tgwssproxy;

import android.Manifest;
import android.annotation.SuppressLint;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.PowerManager;
import android.provider.Settings;
import android.widget.Toast;
import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.core.content.ContextCompat;
import androidx.core.view.WindowCompat;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {

    public static final String ACTION_START_PROXY = "com.dupley.tgwssproxy.ACTION_START_PROXY";
    public static final String ACTION_STOP_PROXY = "com.dupley.tgwssproxy.ACTION_STOP_PROXY";

    private final ActivityResultLauncher<String> requestPermissionLauncher =
            registerForActivityResult(new ActivityResultContracts.RequestPermission(), isGranted -> {
                if (isGranted) {
                    startProxyService();
                } else {
                    Toast.makeText(this, getString(R.string.notification_permission_needed), Toast.LENGTH_LONG).show();
                }
            });

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        
        registerPlugin(ProxyPlugin.class);
        WindowCompat.setDecorFitsSystemWindows(getWindow(), false);

        handleIntent(getIntent());

        checkNotificationPermission();
        checkBatteryOptimization();
        AutoStartHelper.requestAutoStart(this);

        // По умолчанию запускаем сервис, если не было команды на остановку
        if (!ACTION_STOP_PROXY.equals(getIntent().getAction())) {
            startProxyService();
        }
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        handleIntent(intent);
    }

    private void handleIntent(Intent intent) {
        if (intent == null || intent.getAction() == null) return;

        String action = intent.getAction();
        if (ACTION_START_PROXY.equals(action)) {
            startProxyService();
        } else if (ACTION_STOP_PROXY.equals(action)) {
            stopProxyService();
        }
    }

    private void checkNotificationPermission() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) !=
                    PackageManager.PERMISSION_GRANTED) {
                requestPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS);
            }
        }
    }

    private void startProxyService() {
        Intent serviceIntent = new Intent(this, ProxyForegroundService.class);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(serviceIntent);
        } else {
            startService(serviceIntent);
        }
    }

    private void stopProxyService() {
        Intent serviceIntent = new Intent(this, ProxyForegroundService.class);
        serviceIntent.setAction(ProxyForegroundService.ACTION_STOP_SERVICE);
        startService(serviceIntent);
    }

    @SuppressLint("BatteryLife")
    private void checkBatteryOptimization() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            String packageName = getPackageName();
            PowerManager pm = (PowerManager) getSystemService(Context.POWER_SERVICE);
            if (pm != null && !pm.isIgnoringBatteryOptimizations(packageName)) {
                try {
                    Intent intent = new Intent();
                    intent.setAction(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS);
                    intent.setData(Uri.parse("package:" + packageName));
                    startActivity(intent);
                    Toast.makeText(this, getString(R.string.battery_optimization_toast), Toast.LENGTH_LONG).show();
                } catch (Exception e) {
                    Intent intent = new Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS);
                    startActivity(intent);
                }
            }
        }
    }
}
