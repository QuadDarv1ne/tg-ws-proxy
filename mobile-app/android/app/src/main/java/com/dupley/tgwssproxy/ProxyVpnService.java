package com.dupley.tgwssproxy;

import android.content.Intent;
import android.net.VpnService;
import android.os.ParcelFileDescriptor;
import android.util.Log;

import java.io.IOException;

/**
 * Прототип VPN-сервиса (Task 10)
 * В будущем позволит проксировать трафик всего устройства через WebSocket туннель.
 */
public class ProxyVpnService extends VpnService {
    private static final String TAG = "ProxyVpnService";
    private ParcelFileDescriptor vpnInterface = null;

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && "STOP".equals(intent.getAction())) {
            stopVpn();
            return START_NOT_STICKY;
        }
        startVpn();
        return START_STICKY;
    }

    private void startVpn() {
        if (vpnInterface != null) return;

        Builder builder = new Builder();
        builder.setSession("TG WS Proxy VPN")
               .addAddress("10.0.0.2", 24)
               .addDnsServer("8.8.8.8")
               .addRoute("0.0.0.0", 0); // Перехват всего трафика

        try {
            vpnInterface = builder.establish();
            Log.i(TAG, "VPN Interface established");
            
            // В полноценной реализации здесь должен быть цикл чтения из vpnInterface 
            // и перенаправления данных в наш SOCKS5 Python сервер.
        } catch (Exception e) {
            Log.e(TAG, "Failed to start VPN", e);
        }
    }

    private void stopVpn() {
        if (vpnInterface != null) {
            try {
                vpnInterface.close();
            } catch (IOException e) {
                Log.e(TAG, "Error closing VPN", e);
            }
            vpnInterface = null;
        }
        stopSelf();
    }

    @Override
    public void onDestroy() {
        stopVpn();
        super.onDestroy();
    }
}
