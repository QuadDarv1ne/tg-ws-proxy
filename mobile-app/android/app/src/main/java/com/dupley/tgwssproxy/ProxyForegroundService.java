package com.dupley.tgwssproxy;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.SharedPreferences;
import android.net.ConnectivityManager;
import android.net.NetworkInfo;
import android.net.Uri;
import android.os.BatteryManager;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.os.PowerManager;
import android.util.Log;
import androidx.core.app.NotificationCompat;
import com.chaquo.python.PyObject;
import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;
import java.util.Map;

public class ProxyForegroundService extends Service {
    private static final String TAG = "ProxyService";
    private static final String CHANNEL_ID = "ProxyServiceChannel";
    public static final String ACTION_STOP_SERVICE = "STOP_PROXY_SERVICE";
    public static final String ACTION_STATUS_UPDATE = "com.dupley.tgwssproxy.STATUS_UPDATE";
    private static final int NOTIFICATION_ID = 1;
    
    private static final String PREFS_NAME = "proxy_settings";
    private static final String KEY_PORT = "proxy_port";
    private static final String KEY_AUTO_PORT = "auto_port";
    private static final String KEY_WIFI_ONLY = "wifi_only";
    private static final String KEY_BATTERY_LEVEL = "battery_threshold";

    private boolean isPythonRunning = false;
    private Handler statsHandler = new Handler(Looper.getMainLooper());
    private Runnable statsRunnable;
    private PowerManager.WakeLock wakeLock;
    private Thread proxyThread;

    private final BroadcastReceiver systemReceiver = new BroadcastReceiver() {
        @Override
        public void onReceive(Context context, Intent intent) {
            String action = intent.getAction();
            if (Intent.ACTION_BATTERY_CHANGED.equals(action)) {
                checkBattery(intent);
            } else if (ConnectivityManager.CONNECTIVITY_ACTION.equals(action)) {
                updateNetworkType();
            }
        }
    };

    private void notifyStatusChanged(boolean isRunning) {
        Intent intent = new Intent(ACTION_STATUS_UPDATE);
        intent.putExtra("is_running", isRunning);
        sendBroadcast(intent);
    }

    private void checkBattery(Intent intent) {
        int level = intent.getIntExtra(BatteryManager.EXTRA_LEVEL, -1);
        int scale = intent.getIntExtra(BatteryManager.EXTRA_SCALE, -1);
        float batteryPct = level * 100 / (float)scale;

        SharedPreferences prefs = getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
        int threshold = prefs.getInt(KEY_BATTERY_LEVEL, 15);

        if (batteryPct <= threshold && isPythonRunning) {
            Log.w(TAG, "Battery below threshold (" + threshold + "%), stopping service.");
            stopProxy();
            stopForeground(true);
            stopSelf();
        }
    }

    private void updateNetworkType() {
        ConnectivityManager cm = (ConnectivityManager) getSystemService(Context.CONNECTIVITY_SERVICE);
        NetworkInfo info = cm.getActiveNetworkInfo();
        boolean isWifi = info != null && info.getType() == ConnectivityManager.TYPE_WIFI;
        boolean isConnected = info != null && info.isConnected();

        SharedPreferences prefs = getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
        boolean wifiOnly = prefs.getBoolean(KEY_WIFI_ONLY, false);

        if (wifiOnly && !isWifi && isPythonRunning) {
            stopProxy();
            return;
        }

        if (wifiOnly && isWifi && !isPythonRunning && isConnected) {
            startProxy();
            return;
        }
        
        if (isPythonRunning && Python.isStarted()) {
            try {
                Python.getInstance().getModule("android_entry").callAttr("on_network_changed", isWifi);
            } catch (Exception e) { }
        }
    }

    @Override
    public void onCreate() {
        super.onCreate();
        createNotificationChannel();
        initPython();
        acquireWakeLock();
        
        IntentFilter filter = new IntentFilter();
        filter.addAction(Intent.ACTION_BATTERY_CHANGED);
        filter.addAction(ConnectivityManager.CONNECTIVITY_ACTION);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            registerReceiver(systemReceiver, filter, Context.RECEIVER_NOT_EXPORTED);
        } else {
            registerReceiver(systemReceiver, filter);
        }
    }

    private void initPython() {
        if (!Python.isStarted()) {
            Python.start(new AndroidPlatform(this));
        }
    }

    private void acquireWakeLock() {
        PowerManager powerManager = (PowerManager) getSystemService(Context.POWER_SERVICE);
        if (powerManager != null) {
            wakeLock = powerManager.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "TGWSProxy:ServiceWakeLock");
            wakeLock.acquire(10 * 60 * 1000L);
        }
    }

    private void releaseWakeLock() {
        if (wakeLock != null && wakeLock.isHeld()) {
            wakeLock.release();
        }
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && ACTION_STOP_SERVICE.equals(intent.getAction())) {
            stopProxy();
            stopForeground(true);
            stopSelf();
            return START_NOT_STICKY;
        }
        startForeground(NOTIFICATION_ID, createNotification(getString(R.string.proxy_starting), ""));
        startProxy();
        startStatsUpdateLoop();
        return START_STICKY;
    }

    private void startProxy() {
        SharedPreferences prefs = getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
        boolean wifiOnly = prefs.getBoolean(KEY_WIFI_ONLY, false);
        
        if (wifiOnly) {
            ConnectivityManager cm = (ConnectivityManager) getSystemService(Context.CONNECTIVITY_SERVICE);
            NetworkInfo info = cm.getActiveNetworkInfo();
            if (info == null || info.getType() != ConnectivityManager.TYPE_WIFI) return;
        }

        if (isPythonRunning && proxyThread != null && proxyThread.isAlive()) return;
        
        proxyThread = new Thread(() -> {
            try {
                Python py = Python.getInstance();
                PyObject proxyModule = py.getModule("android_entry");
                proxyModule.callAttr("start_proxy", "127.0.0.1", prefs.getInt(KEY_PORT, 1080), prefs.getBoolean(KEY_AUTO_PORT, true));
                isPythonRunning = true;
                notifyStatusChanged(true);
                ProxyPlugin.onStatusChanged(true);
                updateNetworkType();
            } catch (Exception e) {
                Log.e(TAG, "Error starting proxy", e);
                isPythonRunning = false;
                notifyStatusChanged(false);
                ProxyPlugin.onStatusChanged(false);
            }
        });
        proxyThread.start();
    }

    private void startStatsUpdateLoop() {
        statsRunnable = new Runnable() {
            @Override
            public void run() {
                if (isPythonRunning && (proxyThread == null || !proxyThread.isAlive())) {
                    startProxy();
                }
                if (isPythonRunning) {
                    updateNotificationWithStats();
                }
                statsHandler.postDelayed(this, 5000);
            }
        };
        statsHandler.post(statsRunnable);
    }

    private void updateNotificationWithStats() {
        try {
            Python py = Python.getInstance();
            Map<PyObject, PyObject> stats = py.getModule("android_entry").callAttr("get_proxy_stats_dict").asMap();
            
            PyObject portObj = null;
            PyObject connObj = null;
            PyObject upObj = null;
            PyObject downObj = null;

            for (Map.Entry<PyObject, PyObject> entry : stats.entrySet()) {
                String key = entry.getKey().toString();
                if (key.equals("port")) portObj = entry.getValue();
                else if (key.equals("connections_ws")) connObj = entry.getValue();
                else if (key.equals("bytes_up")) upObj = entry.getValue();
                else if (key.equals("bytes_down")) downObj = entry.getValue();
            }
            
            if (portObj == null || connObj == null) return;

            int port = portObj.toInt();
            int conn = connObj.toInt();
            long up = upObj != null ? upObj.toLong() : 0;
            long down = downObj != null ? downObj.toLong() : 0;
            
            NotificationManager manager = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
            manager.notify(NOTIFICATION_ID, createNotification(
                getString(R.string.proxy_status_template, port, conn),
                getString(R.string.proxy_traffic_template, formatBytes(up), formatBytes(down))
            ));
        } catch (Exception e) {
            Log.e(TAG, "Failed to update notification stats", e);
        }
    }

    private String formatBytes(long bytes) {
        if (bytes < 1024) return bytes + " B";
        int exp = (int) (Math.log(bytes) / Math.log(1024));
        return String.format(java.util.Locale.US, "%.1f %sB", bytes / Math.pow(1024, exp), "KMGTPE".charAt(exp - 1) + "");
    }

    private Notification createNotification(String content, String subContent) {
        Intent stopIntent = new Intent(this, ProxyForegroundService.class).setAction(ACTION_STOP_SERVICE);
        PendingIntent stopPendingIntent = PendingIntent.getService(this, 0, stopIntent, PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        Intent openTgIntent = new Intent(Intent.ACTION_VIEW, Uri.parse("tg://socks?server=127.0.0.1&port=1080"));
        PendingIntent openTgPendingIntent = PendingIntent.getActivity(this, 1, openTgIntent, PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        
        return new NotificationCompat.Builder(this, CHANNEL_ID)
                .setContentTitle(getString(R.string.proxy_running_title))
                .setContentText(content).setSubText(subContent).setSmallIcon(R.mipmap.ic_launcher)
                .setContentIntent(PendingIntent.getActivity(this, 0, new Intent(this, MainActivity.class), PendingIntent.FLAG_IMMUTABLE))
                .setOngoing(true).addAction(android.R.drawable.ic_menu_close_clear_cancel, getString(R.string.proxy_stop), stopPendingIntent)
                .addAction(android.R.drawable.ic_menu_send, getString(R.string.proxy_open_tg), openTgPendingIntent)
                .setPriority(NotificationCompat.PRIORITY_LOW).setOnlyAlertOnce(true).build();
    }

    private void stopProxy() {
        if (statsRunnable != null) statsHandler.removeCallbacks(statsRunnable);
        try {
            if (Python.isStarted()) {
                Python py = Python.getInstance();
                PyObject proxyModule = py.getModule("android_entry");
                proxyModule.callAttr("stop_proxy");
            }
            isPythonRunning = false;
            notifyStatusChanged(false);
            ProxyPlugin.onStatusChanged(false);
        } catch (Exception e) {
            Log.e(TAG, "Error stopping proxy", e);
        }
    }

    @Override
    public void onDestroy() {
        try { unregisterReceiver(systemReceiver); } catch (Exception e) { }
        stopProxy();
        releaseWakeLock();
        super.onDestroy();
    }

    @Override public IBinder onBind(Intent intent) { return null; }

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel serviceChannel = new NotificationChannel(CHANNEL_ID, getString(R.string.proxy_service_channel_name), NotificationManager.IMPORTANCE_DEFAULT);
            serviceChannel.setDescription(getString(R.string.proxy_service_channel_desc));
            NotificationManager manager = getSystemService(NotificationManager.class);
            if (manager != null) manager.createNotificationChannel(serviceChannel);
        }
    }
}
