package com.dupley.tgwssproxy;

import android.content.Intent;
import android.net.VpnService;
import android.os.ParcelFileDescriptor;
import android.util.Log;

import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.ByteBuffer;

/**
 * Реализация VPN-маршрутизации (v2.36.0)
 * Перехватывает трафик приложений и может направлять его в локальный SOCKS5 прокси.
 */
public class ProxyVpnService extends VpnService implements Runnable {
    private static final String TAG = "ProxyVpnService";
    public static final String ACTION_CONNECT = "com.dupley.tgwssproxy.START";
    public static final String ACTION_DISCONNECT = "com.dupley.tgwssproxy.STOP";

    private Thread vpnThread;
    private ParcelFileDescriptor vpnInterface;

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && ACTION_DISCONNECT.equals(intent.getAction())) {
            stopVpn();
            return START_NOT_STICKY;
        }
        
        if (vpnThread == null || !vpnThread.isAlive()) {
            vpnThread = new Thread(this, "ProxyVpnThread");
            vpnThread.start();
        }
        return START_STICKY;
    }

    @Override
    public void run() {
        try {
            Log.i(TAG, "Starting VPN...");
            setupVpn();
            processPackets();
        } catch (Exception e) {
            Log.e(TAG, "VPN Runtime Error: " + e.getMessage());
        } finally {
            stopVpn();
        }
    }

    private void setupVpn() throws Exception {
        Builder builder = new Builder();
        builder.setSession("TG WS Proxy")
               .setMtu(1500)
               .addAddress("10.0.0.2", 32)
               .addRoute("0.0.0.0", 0) // Весь IPv4 трафик
               .addDnsServer("1.1.1.1")
               .addDnsServer("8.8.8.8");

        // Опционально: можно ограничить VPN только приложением Telegram
        try {
            builder.addAllowedApplication("org.telegram.messenger");
            builder.addAllowedApplication("org.thunderdog.challegram"); // Telegram X
        } catch (Exception e) {
            Log.w(TAG, "Could not restrict to Telegram apps, routing all traffic");
        }

        vpnInterface = builder.establish();
        if (vpnInterface == null) {
            throw new RuntimeException("Failed to establish VPN interface");
        }
        Log.i(TAG, "VPN Interface established: " + vpnInterface);
    }

    private void processPackets() throws IOException {
        FileInputStream in = new FileInputStream(vpnInterface.getFileDescriptor());
        ByteBuffer packet = ByteBuffer.allocate(32768);

        // В полноценной реализации здесь должен быть NAT или прокси-движок (например, tun2socks)
        // Для v2.36.0 мы обеспечиваем стабильный жизненный цикл интерфейса.
        while (!Thread.interrupted()) {
            int length = in.read(packet.array());
            if (length > 0) {
                // Пакеты принимаются. Логика пересылки в Python SOCKS5 будет добавлена в v2.37
                packet.clear();
            }
        }
    }

    private void stopVpn() {
        Log.i(TAG, "Stopping VPN...");
        if (vpnThread != null) {
            vpnThread.interrupt();
            vpnThread = null;
        }
        if (vpnInterface != null) {
            try {
                vpnInterface.close();
            } catch (IOException e) {
                Log.e(TAG, "Error closing VPN interface: " + e.getMessage());
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
