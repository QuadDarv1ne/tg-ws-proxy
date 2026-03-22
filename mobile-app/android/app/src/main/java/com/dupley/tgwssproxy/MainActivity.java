package com.dupley.tgwssproxy;

import android.Manifest;
import android.annotation.SuppressLint;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.pm.PackageManager;
import android.content.res.Configuration;
import android.net.ConnectivityManager;
import android.net.NetworkCapabilities;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.PowerManager;
import android.provider.Settings;
import android.util.Log;
import android.widget.Toast;
import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.annotation.NonNull;
import androidx.core.content.ContextCompat;
import androidx.core.splashscreen.SplashScreen;
import androidx.core.view.WindowCompat;
import com.getcapacitor.BridgeActivity;
import com.getcapacitor.JSObject;
import java.io.File;
import java.io.FileOutputStream;
import java.io.PrintWriter;
import java.io.StringWriter;
import java.util.Date;

public class MainActivity extends BridgeActivity {

    public static final String ACTION_START_PROXY = "com.dupley.tgwssproxy.ACTION_START_PROXY";
    public static final String ACTION_STOP_PROXY = "com.dupley.tgwssproxy.ACTION_STOP_PROXY";
    public static final String ACTION_STATUS_UPDATE = "com.dupley.tgwssproxy.STATUS_UPDATE";
    private static final String TAG = "MainActivity";

    private final BroadcastReceiver statusReceiver = new BroadcastReceiver() {
        @Override
        public void onReceive(Context context, Intent intent) {
            if (ACTION_STATUS_UPDATE.equals(intent.getAction())) {
                boolean isRunning = intent.getBooleanExtra("is_running", false);
                updateUiStatus(isRunning);
            }
        }
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        SplashScreen splashScreen = SplashScreen.installSplashScreen(this);
        super.onCreate(savedInstanceState);
        
        setupCrashReporting();
        syncSystemTheme();
        WindowCompat.setDecorFitsSystemWindows(getWindow(), false);

        handleIntent(getIntent());
        checkNotificationPermission();
        checkBatteryOptimization();
        AutoStartHelper.requestAutoStart(this);

        if (!ACTION_STOP_PROXY.equals(getIntent().getAction()) && isNetworkAvailable()) {
            startProxyService();
        } else if (!isNetworkAvailable()) {
            Toast.makeText(this, "Нет подключения к сети", Toast.LENGTH_SHORT).show();
        }
    }

    @Override
    public void onResume() {
        super.onResume();
        IntentFilter filter = new IntentFilter(ACTION_STATUS_UPDATE);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            registerReceiver(statusReceiver, filter, Context.RECEIVER_NOT_EXPORTED);
        } else {
            registerReceiver(statusReceiver, filter);
        }
        syncSystemTheme();
    }

    @Override
    public void onPause() {
        super.onPause();
        unregisterReceiver(statusReceiver);
    }

    private void updateUiStatus(boolean isRunning) {
        if (bridge != null && bridge.getWebView() != null) {
            JSObject data = new JSObject();
            data.put("status", isRunning ? "running" : "stopped");
            bridge.getWebView().post(() -> bridge.getWebView().evaluateJavascript(
                "window.dispatchEvent(new CustomEvent('proxyStatusChanged', {detail: " + data.toString() + "}))", 
                null
            ));
        }
    }

    private boolean isNetworkAvailable() {
        ConnectivityManager cm = (ConnectivityManager) getSystemService(Context.CONNECTIVITY_SERVICE);
        if (cm == null) return false;
        NetworkCapabilities capabilities = cm.getNetworkCapabilities(cm.getActiveNetwork());
        return capabilities != null && (
                capabilities.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) ||
                capabilities.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR) ||
                capabilities.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET));
    }

    private void setupCrashReporting() {
        Thread.UncaughtExceptionHandler defaultHandler = Thread.getDefaultUncaughtExceptionHandler();
        Thread.setDefaultUncaughtExceptionHandler((thread, throwable) -> {
            try {
                StringWriter sw = new StringWriter();
                throwable.printStackTrace(new PrintWriter(sw));
                String crashInfo = String.format("\n--- JAVA CRASH AT %s ---\n%s\n", new Date(), sw.toString());
                
                File crashFile = new File(getFilesDir(), "crash_log.txt");
                try (FileOutputStream fos = new FileOutputStream(crashFile, true)) {
                    fos.write(crashInfo.getBytes());
                }
            } catch (Exception e) {
                Log.e(TAG, "Failed to write crash log", e);
            }
            if (defaultHandler != null) {
                defaultHandler.uncaughtException(thread, throwable);
            }
        });
    }

    private void syncSystemTheme() {
        int nightModeFlags = getResources().getConfiguration().uiMode & Configuration.UI_MODE_NIGHT_MASK;
        if (bridge != null && bridge.getWebView() != null) {
            boolean isDark = nightModeFlags == Configuration.UI_MODE_NIGHT_YES;
            bridge.getWebView().post(() -> bridge.getWebView().evaluateJavascript(
                "document.documentElement.setAttribute('data-theme', '" + (isDark ? "dark" : "light") + "')", 
                null
            ));
        }
    }

    @Override
    public void onConfigurationChanged(Configuration newConfig) {
        super.onConfigurationChanged(newConfig);
        syncSystemTheme();
    }

    private final ActivityResultLauncher<String> requestPermissionLauncher =
            registerForActivityResult(new ActivityResultContracts.RequestPermission(), isGranted -> {
                if (isGranted) {
                    startProxyService();
                } else {
                    Toast.makeText(this, getString(R.string.notification_permission_needed), Toast.LENGTH_LONG).show();
                }
            });

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        handleIntent(intent);
    }

    private void handleIntent(Intent intent) {
        if (intent == null) return;
        String action = intent.getAction();
        Uri data = intent.getData();

        if (Intent.ACTION_VIEW.equals(action) && data != null) {
            handleDeepLink(data);
        }

        if (ACTION_START_PROXY.equals(action)) {
            startProxyService();
        } else if (ACTION_STOP_PROXY.equals(action)) {
            stopProxyService();
        }
    }

    private void handleDeepLink(Uri uri) {
        String server = uri.getQueryParameter("server");
        String port = uri.getQueryParameter("port");
        if (server != null && port != null) {
            JSObject config = new JSObject();
            config.put("server", server);
            config.put("port", Integer.parseInt(port));
            bridge.getWebView().post(() -> bridge.getWebView().evaluateJavascript(
                "window.dispatchEvent(new CustomEvent('deepLinkConfig', {detail: " + config.toString() + "}))", 
                null
            ));
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
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) startForegroundService(serviceIntent);
        else startService(serviceIntent);
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
                    Intent intent = new Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS);
                    intent.setData(Uri.parse("package:" + packageName));
                    startActivity(intent);
                    Toast.makeText(this, getString(R.string.battery_optimization_toast), Toast.LENGTH_LONG).show();
                } catch (Exception e) {
                    try {
                        startActivity(new Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS));
                    } catch (Exception ignored) {}
                }
            }
        }
    }
}
