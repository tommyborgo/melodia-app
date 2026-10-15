package com.melodia.app

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.net.wifi.WifiManager
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import java.io.File
import java.io.FileOutputStream

/** Tiene vivo il "motore" Melodia (server Python locale: ricerca, stream, download) anche con lo schermo spento. */
class ServerService : Service() {
    private var wake: PowerManager.WakeLock? = null
    private var wifi: WifiManager.WifiLock? = null

    override fun onBind(i: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val ch = "melodia_engine"
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        if (Build.VERSION.SDK_INT >= 26) nm.createNotificationChannel(NotificationChannel(ch, "Melodia", NotificationManager.IMPORTANCE_LOW))
        val pi = PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE)
        val n = (if (Build.VERSION.SDK_INT >= 26) Notification.Builder(this, ch) else Notification.Builder(this))
            .setContentTitle("Melodia").setContentText("Motore musicale attivo")
            .setSmallIcon(android.R.drawable.ic_media_play).setContentIntent(pi).setOngoing(true).build()
        if (Build.VERSION.SDK_INT >= 29) startForeground(1, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PLAYBACK) else startForeground(1, n)

        val pm = getSystemService(Context.POWER_SERVICE) as PowerManager
        if (wake == null) { wake = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "melodia:engine"); wake?.acquire() }
        val wm = applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
        if (wifi == null) { @Suppress("DEPRECATION") wifi = wm.createWifiLock(WifiManager.WIFI_MODE_FULL_HIGH_PERF, "melodia:wifi"); wifi?.acquire() }

        if (!started) {
            started = true
            val app = applicationContext
            Thread {
                try {
                    val www = File(app.filesDir, "www"); www.mkdirs()
                    for (f in listOf("spotify_moto.html", "sw.js")) {
                        app.assets.open(f).use { i -> FileOutputStream(File(www, f)).use { o -> i.copyTo(o) } }
                    }
                    if (!Python.isStarted()) Python.start(AndroidPlatform(app))
                    val root = Storage.root(app).absolutePath
                    Python.getInstance().getModule("android_glue").callAttr("start", root, www.absolutePath, 5000)
                } catch (e: Throwable) {
                    lastError = e.toString()
                    started = false
                }
            }.start()
        }
        return START_STICKY
    }

    override fun onDestroy() {
        wake?.let { if (it.isHeld) it.release() }
        wifi?.let { if (it.isHeld) it.release() }
        super.onDestroy()
    }

    companion object {
        @Volatile var started = false
        @Volatile var lastError: String? = null
    }
}
