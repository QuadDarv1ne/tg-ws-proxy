package com.dupley.tgwssproxy;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
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
    private static final int NOTIFICATION_ID = 1;
    
    private static final String PREFS_NAME = "proxy_settings";
    private static final String KEY_PORT = "proxy_port";
    private static final String KEY_AUTO_PORT = "auto_port";

    private boolean isPythonRunning = false;
    private Handler statsHandler = new Handler(Looper.getMainLooper());
    private Runnable statsRunnable;
    private PowerManager.WakeLock wakeLock;
    private Thread proxyThread;

    @Override
    public void onCreate() {
        super.onCreate();
        initPython();
        acquireWakeLock();
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
            Log.i(TAG, "WakeLock acquired");
        }
    }

    private void releaseWakeLock() {
        if (wakeLock != null && wakeLock.isHeld()) {
            wakeLock.release();
            Log.i(TAG, "WakeLock released");
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
        if (isPythonRunning && proxyThread != null && proxyThread.isAlive()) return;
        
        proxyThread = new Thread(() -> {
            try {
                SharedPreferences prefs = getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
                int savedPort = prefs.getInt(KEY_PORT, 1080);
                boolean autoPort = prefs.getBoolean(KEY_AUTO_PORT, true);

                Python py = Python.getInstance();
                PyObject proxyModule = py.getModule("android_entry");
                
                PyObject result = proxyModule.callAttr("start_proxy", "127.0.0.1", savedPort, autoPort);
                int actualPort = result.asMap().get(py.getBuiltins().get("str").call("port")).toInt();
                
                if (actualPort != savedPort) {
                    prefs.edit().putInt(KEY_PORT, actualPort).apply();
                }

                isPythonRunning = true;
                ProxyPlugin.onStatusChanged(true);
                Log.i(TAG, "Python Proxy started on port: " + actualPort);
            } catch (Exception e) {
                Log.e(TAG, "Error starting Python Proxy: " + e.getMessage());
                isPythonRunning = false;
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
                    Log.w(TAG, "Watchdog: Python thread died, restarting...");
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
            PyObject module = py.getModule("android_entry");
            PyObject statsObj = module.callAttr("get_proxy_stats_dict");
            Map<PyObject, PyObject> stats = statsObj.asMap();

            int connections = stats.get(py.getBuiltins().get("str").call("connections_ws")).toInt();
            long bytesUp = stats.get(py.getBuiltins().get("str").call("bytes_up")).toLong();
            long bytesDown = stats.get(py.getBuiltins().get("str").call("bytes_down")).toLong();
            int port = stats.get(py.getBuiltins().get("str").call("port")).toInt();

            String content = getString(R.string.proxy_status_template, port, connections);
            String subContent = getString(R.string.proxy_traffic_template, formatBytes(bytesUp), formatBytes(bytesDown));

            NotificationManager manager = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
            if (manager != null) {
                manager.notify(NOTIFICATION_ID, createNotification(content, subContent));
            }
        } catch (Exception e) {
            Log.e(TAG, "Failed to update notification stats: " + e.getMessage());
        }
    }

    private String formatBytes(long bytes) {
        if (bytes < 1024) return bytes + " B";
        int exp = (int) (Math.log(bytes) / Math.log(1024));
        String pre = "KMGTPE".charAt(exp - 1) + "";
        return String.format(java.util.Locale.US, "%.1f %sB", bytes / Math.pow(1024, exp), pre);
    }

    private Notification createNotification(String content, String subContent) {
        Intent stopIntent = new Intent(this, ProxyForegroundService.class);
        stopIntent.setAction(ACTION_STOP_SERVICE);
        PendingIntent stopPendingIntent = PendingIntent.getService(this, 0, stopIntent, 
                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);

        Intent openTgIntent = new Intent(Intent.ACTION_VIEW, Uri.parse("tg://socks?server=127.0.0.1&port=1080"));
        PendingIntent openTgPendingIntent = PendingIntent.getActivity(this, 1, openTgIntent, 
                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);

        Intent notificationIntent = new Intent(this, MainActivity.class);
        PendingIntent pendingIntent = PendingIntent.getActivity(this, 0, notificationIntent, 
                PendingIntent.FLAG_IMMUTABLE);

        return new NotificationCompat.Builder(this, CHANNEL_ID)
                .setContentTitle(getString(R.string.proxy_running_title))
                .setContentText(content)
                .setSubText(subContent)
                .setSmallIcon(R.mipmap.ic_launcher)
                .setContentIntent(pendingIntent)
                .setOngoing(true)
                .addAction(android.R.drawable.ic_menu_close_clear_cancel, getString(R.string.proxy_stop), stopPendingIntent)
                .addAction(android.R.drawable.ic_menu_send, getString(R.string.proxy_open_tg), openTgPendingIntent)
                .setPriority(NotificationCompat.PRIORITY_LOW)
                .setOnlyAlertOnce(true)
                .build();
    }

    private void stopProxy() {
        statsHandler.removeCallbacks(statsRunnable);
        try {
            Python py = Python.getInstance();
            PyObject proxyModule = py.getModule("android_entry");
            proxyModule.callAttr("stop_proxy");
            isPythonRunning = false;
            ProxyPlugin.onStatusChanged(false);
        } catch (Exception e) {
            Log.e(TAG, "Error stopping Python Proxy: " + e.getMessage());
        }
    }

    @Override
    public void onDestroy() {
        stopProxy();
        releaseWakeLock();
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel serviceChannel = new NotificationChannel(
                    CHANNEL_ID,
                    getString(R.string.proxy_service_channel_name),
                    NotificationManager.IMPORTANCE_DEFAULT
            );
            serviceChannel.setDescription(getString(R.string.proxy_service_channel_desc));
            NotificationManager manager = getSystemService(NotificationManager.class);
            if (manager != null) {
                manager.createNotificationChannel(serviceChannel);
            }
        }
    }
}
