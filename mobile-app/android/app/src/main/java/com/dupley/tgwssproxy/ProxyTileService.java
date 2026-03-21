package com.dupley.tgwssproxy;

import android.app.ActivityManager;
import android.content.Context;
import android.content.Intent;
import android.graphics.drawable.Icon;
import android.os.Build;
import android.service.quicksettings.Tile;
import android.service.quicksettings.TileService;

import androidx.annotation.RequiresApi;

@RequiresApi(api = Build.VERSION_CODES.N)
public class ProxyTileService extends TileService {

    @Override
    public void onStartListening() {
        super.onStartListening();
        updateTile();
    }

    @Override
    public void onClick() {
        super.onClick();
        boolean isActive = isServiceRunning(ProxyForegroundService.class);
        
        if (isActive) {
            Intent stopIntent = new Intent(this, ProxyForegroundService.class);
            stopIntent.setAction(ProxyForegroundService.ACTION_STOP_SERVICE);
            startService(stopIntent);
        } else {
            Intent startIntent = new Intent(this, ProxyForegroundService.class);
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                startForegroundService(startIntent);
            } else {
                startService(startIntent);
            }
        }
        
        updateTile();
    }

    private void updateTile() {
        Tile tile = getQsTile();
        if (tile == null) return;

        boolean isActive = isServiceRunning(ProxyForegroundService.class);
        
        if (isActive) {
            tile.setState(Tile.STATE_ACTIVE);
            tile.setLabel(getString(R.string.tile_on));
        } else {
            tile.setState(Tile.STATE_INACTIVE);
            tile.setLabel(getString(R.string.tile_off));
        }

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            tile.setIcon(Icon.createWithResource(this, R.mipmap.ic_launcher));
        }
        
        tile.updateTile();
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
