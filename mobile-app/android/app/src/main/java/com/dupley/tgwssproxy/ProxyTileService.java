package com.dupley.tgwssproxy;

import android.app.ActivityManager;
import android.content.Context;
import android.content.Intent;
import android.graphics.drawable.Icon;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.service.quicksettings.Tile;
import android.service.quicksettings.TileService;
import android.util.Log;

import androidx.annotation.RequiresApi;

import com.chaquo.python.PyObject;
import com.chaquo.python.Python;

import java.util.Map;

@RequiresApi(api = Build.VERSION_CODES.N)
public class ProxyTileService extends TileService {
    private static final String TAG = "ProxyTile";
    private Handler updateHandler = new Handler(Looper.getMainLooper());
    private Runnable updateRunnable;

    @Override
    public void onStartListening() {
        super.onStartListening();
        startTileUpdates();
    }

    @Override
    public void onStopListening() {
        stopTileUpdates();
        super.onStopListening();
    }

    @Override
    public void onClick() {
        super.onClick();
        boolean isActive = isServiceRunning(ProxyForegroundService.class);
        
        Intent intent = new Intent(this, ProxyForegroundService.class);
        if (isActive) {
            intent.setAction(ProxyForegroundService.ACTION_STOP_SERVICE);
            startService(intent);
        } else {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                startForegroundService(intent);
            } else {
                startService(intent);
            }
        }
        
        // Кратковременная задержка для обновления статуса
        updateHandler.postDelayed(this::updateTile, 500);
    }

    private void startTileUpdates() {
        updateRunnable = new Runnable() {
            @Override
            public void run() {
                updateTile();
                updateHandler.postDelayed(this, 3000); // Обновляем раз в 3 секунды
            }
        };
        updateHandler.post(updateRunnable);
    }

    private void stopTileUpdates() {
        if (updateRunnable != null) {
            updateHandler.removeCallbacks(updateRunnable);
        }
    }

    private void updateTile() {
        Tile tile = getQsTile();
        if (tile == null) return;

        boolean isActive = isServiceRunning(ProxyForegroundService.class);
        
        if (isActive) {
            tile.setState(Tile.STATE_ACTIVE);
            String speedInfo = getSpeedFromPython();
            tile.setLabel(getString(R.string.tile_label));
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                tile.setSubtitle(speedInfo != null ? speedInfo : getString(R.string.tile_on));
            }
        } else {
            tile.setState(Tile.STATE_INACTIVE);
            tile.setLabel(getString(R.string.tile_label));
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                tile.setSubtitle(getString(R.string.tile_off));
            }
        }

        tile.updateTile();
    }

    private String getSpeedFromPython() {
        try {
            if (!Python.isStarted()) return null;
            Python py = Python.getInstance();
            Map<PyObject, PyObject> stats = py.getModule("android_entry").callAttr("get_proxy_stats_dict").asMap();
            
            PyObject speedUp = null;
            PyObject speedDown = null;

            for (Map.Entry<PyObject, PyObject> entry : stats.entrySet()) {
                String key = entry.getKey().toString();
                if (key.equals("speed_up")) speedUp = entry.getValue();
                else if (key.equals("speed_down")) speedDown = entry.getValue();
            }
            
            if (speedUp != null && speedDown != null) {
                Object[] upList = speedUp.asList().toArray();
                Object[] downList = speedDown.asList().toArray();
                if (upList.length > 0 && downList.length > 0) {
                    return String.format("↑%s KB/s  ↓%s KB/s", 
                        upList[upList.length-1], downList[downList.length-1]);
                }
            }
        } catch (Exception e) {
            Log.e(TAG, "Error getting speed from Python: " + e.getMessage());
        }
        return null;
    }

    private boolean isServiceRunning(Class<?> serviceClass) {
        ActivityManager manager = (ActivityManager) getSystemService(Context.ACTIVITY_SERVICE);
        if (manager != null) {
            for (ActivityManager.RunningServiceInfo service : manager.getRunningServices(Integer.MAX_VALUE)) {
                if (serviceClass.getName().equals(service.service.getClassName())) {
                    return true;
                }
            }
        }
        return false;
    }
}
