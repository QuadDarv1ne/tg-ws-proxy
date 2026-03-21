package com.dupley.tgwssproxy;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.net.ConnectivityManager;
import android.net.NetworkInfo;
import android.util.Log;

public class NetworkChangeReceiver extends BroadcastReceiver {
    private static final String TAG = "NetworkChangeReceiver";

    @Override
    public void onReceive(Context context, Intent intent) {
        if (ConnectivityManager.CONNECTIVITY_ACTION.equals(intent.getAction())) {
            ConnectivityManager cm = (ConnectivityManager) context.getSystemService(Context.CONNECTIVITY_SERVICE);
            NetworkInfo activeNetwork = cm.getActiveNetworkInfo();
            boolean isConnected = activeNetwork != null && activeNetwork.isConnectedOrConnecting();

            Log.i(TAG, "Network status changed. Connected: " + isConnected);

            if (isConnected) {
                // Если сеть появилась, а сервис не запущен или завис — можем пнуть его.
                // В нашем случае, если сервис уже работает, startForegroundService просто обновит его.
                Intent serviceIntent = new Intent(context, ProxyForegroundService.class);
                if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.O) {
                    context.startForegroundService(serviceIntent);
                } else {
                    context.startService(serviceIntent);
                }
            }
        }
    }
}
