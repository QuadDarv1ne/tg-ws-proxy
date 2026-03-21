package com.dupley.tgwssproxy;

import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.os.Build;
import android.util.Log;

import java.util.List;

public class AutoStartHelper {

    private static final String TAG = "AutoStartHelper";

    /**
     * Список известных Intent-ов для настроек автозапуска у разных производителей
     */
    private static final Intent[] AUTO_START_INTENTS = {
            new Intent().setComponent(new ComponentName("com.miui.securitycenter", "com.miui.permcenter.autostart.AutoStartManagementActivity")),
            new Intent().setComponent(new ComponentName("com.letv.android.letvsafe", "com.letv.android.letvsafe.AutobootManageActivity")),
            new Intent().setComponent(new ComponentName("com.huawei.systemmanager", "com.huawei.systemmanager.optimize.process.ProtectActivity")),
            new Intent().setComponent(new ComponentName("com.huawei.systemmanager", "com.huawei.systemmanager.appcontrol.activity.StartupAppControlActivity")),
            new Intent().setComponent(new ComponentName("com.coloros.safecenter", "com.coloros.safecenter.permission.startup.StartupAppListActivity")),
            new Intent().setComponent(new ComponentName("com.coloros.safecenter", "com.coloros.safecenter.startupapp.StartupAppListActivity")),
            new Intent().setComponent(new ComponentName("com.oppo.safe", "com.oppo.safe.permission.startup.StartupAppListActivity")),
            new Intent().setComponent(new ComponentName("com.iqoo.secure", "com.iqoo.secure.ui.phoneoptimize.AddWhiteListActivity")),
            new Intent().setComponent(new ComponentName("com.iqoo.secure", "com.iqoo.secure.ui.phoneoptimize.BgStartUpManager")),
            new Intent().setComponent(new ComponentName("com.vivo.permissionmanager", "com.vivo.permissionmanager.activity.BgStartUpManagerActivity")),
            new Intent().setComponent(new ComponentName("com.samsung.android.lool", "com.samsung.android.sm.ui.battery.BatteryActivity")),
            new Intent().setComponent(new ComponentName("com.htc.pitroad", "com.htc.pitroad.landingpage.activity.LandingPageActivity")),
            new Intent().setComponent(new ComponentName("com.asus.mobilemanager", "com.asus.mobilemanager.autostart.AutoStartActivity"))
    };

    public static void requestAutoStart(Context context) {
        if (isAutoStartPermissionRequested(context)) {
            return;
        }

        for (Intent intent : AUTO_START_INTENTS) {
            if (isIntentCallable(context, intent)) {
                try {
                    intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                    context.startActivity(intent);
                    markAutoStartRequested(context);
                    break;
                } catch (Exception e) {
                    Log.e(TAG, "Failed to start auto-start settings", e);
                }
            }
        }
    }

    private static boolean isIntentCallable(Context context, Intent intent) {
        List<ResolveInfo> list = context.getPackageManager().queryIntentActivities(intent, PackageManager.MATCH_DEFAULT_ONLY);
        return list != null && !list.isEmpty();
    }

    private static boolean isAutoStartPermissionRequested(Context context) {
        return context.getSharedPreferences("proxy_prefs", Context.MODE_PRIVATE)
                .getBoolean("autostart_requested", false);
    }

    private static void markAutoStartRequested(Context context) {
        context.getSharedPreferences("proxy_prefs", Context.MODE_PRIVATE)
                .edit()
                .putBoolean("autostart_requested", true)
                .apply();
    }
}
