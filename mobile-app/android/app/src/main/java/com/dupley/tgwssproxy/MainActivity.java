package com.dupley.tgwssproxy;

import android.content.Intent;
import android.os.Build;
import android.os.Bundle;
import androidx.core.view.WindowCompat;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        
        // Включает отображение контента "от края до края"
        WindowCompat.setDecorFitsSystemWindows(getWindow(), false);

        // Запуск фонового сервиса для стабильной работы прокси
        startProxyService();
    }

    private void startProxyService() {
        Intent serviceIntent = new Intent(this, ProxyForegroundService.class);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(serviceIntent);
        } else {
            startService(serviceIntent);
        }
    }
}
