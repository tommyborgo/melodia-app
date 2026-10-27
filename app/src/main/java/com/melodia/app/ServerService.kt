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
import java.net.HttpURLConnection
import java.net.URL
import org.json.JSONObject

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
        startNewsWatcher()
        return START_STICKY
    }

    /** Controlla ogni pochi minuti gli annunci del proprietario (aggiornamenti, manutenzione) e li mostra come notifica,
     *  anche con l'app chiusa (finché il motore è attivo). */
    private fun startNewsWatcher() {
        if (newsStarted) return
        newsStarted = true
        val app = applicationContext
        Thread {
            val prefs = app.getSharedPreferences("melodia", MODE_PRIVATE)
            val nm = app.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            if (Build.VERSION.SDK_INT >= 26) nm.createNotificationChannel(NotificationChannel("melodia_news", "Avvisi di Melodia", NotificationManager.IMPORTANCE_HIGH))
            Thread.sleep(20000)
            while (true) {
                try {
                    val first = !prefs.contains("news_since")
                    val since = prefs.getLong("news_since", 0L)
                    val c = URL("https://melodia-server-9yo3.onrender.com/api/announce/latest?since=$since").openConnection() as HttpURLConnection
                    c.connectTimeout = 20000; c.readTimeout = 60000
                    val j = JSONObject(c.inputStream.bufferedReader().readText())
                    val items = j.optJSONArray("items")
                    var last = since
                    val now = System.currentTimeMillis() / 1000.0
                    if (items != null) for (i in 0 until items.length()) {
                        val o = items.getJSONObject(i)
                        val id = o.getLong("id")
                        if (id > last) last = id
                        if (!first && now - o.optDouble("ts", 0.0) < 6 * 3600) {
                            val pi = PendingIntent.getActivity(app, id.toInt(), Intent(app, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE)
                            val b = if (Build.VERSION.SDK_INT >= 26) Notification.Builder(app, "melodia_news") else Notification.Builder(app)
                            val n = b.setContentTitle(o.optString("title", "Melodia")).setContentText(o.optString("body", ""))
                                .setStyle(Notification.BigTextStyle().bigText(o.optString("body", "")))
                                .setSmallIcon(android.R.drawable.ic_dialog_info).setContentIntent(pi).setAutoCancel(true).build()
                            nm.notify(1000 + (id % 1000).toInt(), n)
                        }
                    }
                    val serverLast = j.optLong("lastId", last)
                    prefs.edit().putLong("news_since", maxOf(last, if (first) serverLast else last)).apply()
                } catch (e: Throwable) { /* rete assente o server in avvio: riprova al giro dopo */ }
                try { Thread.sleep(180000) } catch (e: InterruptedException) { return@Thread }
            }
        }.start()
    }

    override fun onDestroy() {
        wake?.let { if (it.isHeld) it.release() }
        wifi?.let { if (it.isHeld) it.release() }
        super.onDestroy()
    }

    companion object {
        @Volatile var started = false
        @Volatile var newsStarted = false
        @Volatile var lastError: String? = null
    }
}
