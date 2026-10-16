package com.melodia.app

import android.Manifest
import android.app.Activity
import android.app.DownloadManager
import android.content.Intent
import android.content.pm.PackageManager
import android.content.pm.ShortcutInfo
import android.content.pm.ShortcutManager
import android.graphics.drawable.Icon
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Environment
import android.os.PowerManager
import android.provider.Settings
import android.view.View
import android.webkit.CookieManager
import android.webkit.URLUtil
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.TextView
import android.app.AlertDialog
import java.net.HttpURLConnection
import java.net.URL

class MainActivity : Activity() {
    private lateinit var web: WebView
    private lateinit var status: TextView
    private val home = "http://127.0.0.1:5000/"
    private var loaded = false

    override fun onCreate(b: Bundle?) {
        super.onCreate(b)
        val prefs = getSharedPreferences("melodia", MODE_PRIVATE)

        web = WebView(this)
        status = TextView(this).apply {
            text = "Melodia\nAvvio del motore…"; setTextColor(0xFFFFFFFF.toInt()); textSize = 18f
            gravity = android.view.Gravity.CENTER; setBackgroundColor(0xFF000000.toInt())
        }
        val root = android.widget.FrameLayout(this)
        root.setBackgroundColor(0xFF000000.toInt())
        root.addView(web); root.addView(status)
        setContentView(root)
        web.visibility = View.INVISIBLE

        val s = web.settings
        s.javaScriptEnabled = true
        s.domStorageEnabled = true
        s.databaseEnabled = true
        s.mediaPlaybackRequiresUserGesture = false
        s.cacheMode = WebSettings.LOAD_DEFAULT
        s.mixedContentMode = WebSettings.MIXED_CONTENT_ALWAYS_ALLOW
        s.userAgentString = s.userAgentString.replace("; wv", "") + " MelodiaApp"
        CookieManager.getInstance().setAcceptCookie(true)
        web.setBackgroundColor(0xFF000000.toInt())
        web.webChromeClient = WebChromeClient()
        web.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(v: WebView, r: WebResourceRequest): Boolean {
                val u = r.url
                if (u.host == "127.0.0.1" || u.host == "localhost") return false
                try { startActivity(Intent(Intent.ACTION_VIEW, u)) } catch (_: Exception) {}
                return true
            }
            override fun onPageFinished(v: WebView, url: String) {
                status.visibility = View.GONE; web.visibility = View.VISIBLE
                checkUpdate()
            }
            override fun onReceivedError(v: WebView, r: WebResourceRequest, e: WebResourceError) {
                if (r.isForMainFrame) {
                    status.visibility = View.VISIBLE; web.visibility = View.INVISIBLE
                    status.text = "Melodia\nRiavvio del motore…"
                    loaded = false; waitAndLoad()
                }
            }
        }
        web.setDownloadListener { url, ua, cd, mime, _ ->
            try {
                val req = DownloadManager.Request(Uri.parse(url))
                req.setMimeType(mime); req.addRequestHeader("User-Agent", ua)
                req.setTitle(URLUtil.guessFileName(url, cd, mime))
                req.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
                req.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, URLUtil.guessFileName(url, cd, mime))
                (getSystemService(DOWNLOAD_SERVICE) as DownloadManager).enqueue(req)
            } catch (_: Exception) {}
        }

        // 1) permessi (una sola volta, poi non chiede più)
        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED)
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 1)
        if (Build.VERSION.SDK_INT >= 30 && !Environment.isExternalStorageManager()) {
            try {
                startActivity(Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION, Uri.parse("package:$packageName")))
            } catch (_: Exception) {
                startActivity(Intent(Settings.ACTION_MANAGE_ALL_FILES_ACCESS_PERMISSION))
            }
        } else if (Build.VERSION.SDK_INT in 23..29 && checkSelfPermission(Manifest.permission.WRITE_EXTERNAL_STORAGE) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(arrayOf(Manifest.permission.WRITE_EXTERNAL_STORAGE, Manifest.permission.READ_EXTERNAL_STORAGE), 2)
        }

        // 2) sveglia il cloud (Render) in anticipo, così login/sync sono pronti
        Thread {
            try {
                (URL("https://melodia-server-9yo3.onrender.com/api/server_info").openConnection() as HttpURLConnection).apply {
                    connectTimeout = 15000; readTimeout = 70000
                }.inputStream.close()
            } catch (_: Exception) {}
        }.start()

        // 3) prima volta: chiede di mettere l'icona nella schermata Home
        if (!prefs.getBoolean("shortcutAsked", false)) {
            prefs.edit().putBoolean("shortcutAsked", true).apply()
            askHomeShortcut()
        }

        // 4) batteria: chiede di non fermare il motore in background (una sola volta)
        if (!prefs.getBoolean("batteryAsked", false)) {
            prefs.edit().putBoolean("batteryAsked", true).apply()
            try {
                val pm = getSystemService(POWER_SERVICE) as PowerManager
                if (!pm.isIgnoringBatteryOptimizations(packageName))
                    startActivity(Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, Uri.parse("package:$packageName")))
            } catch (_: Exception) {}
        }

        val svc = Intent(this, ServerService::class.java)
        if (Build.VERSION.SDK_INT >= 26) startForegroundService(svc) else startService(svc)
        waitAndLoad()
    }

    private var updateChecked = false
    /** Controlla su GitHub se esiste un APK più recente di quello installato e, in caso, propone di scaricarlo. */
    private fun checkUpdate() {
        if (updateChecked) return
        updateChecked = true
        Thread {
            try {
                val c = URL("https://api.github.com/repos/tommyborgo/melodia-app/releases/latest").openConnection() as HttpURLConnection
                c.connectTimeout = 8000; c.readTimeout = 8000
                val body = c.inputStream.bufferedReader().readText()
                val m = Regex("\"updated_at\"\\s*:\\s*\"([^\"]+)\"", RegexOption.IGNORE_CASE).findAll(body).map { it.groupValues[1] }.toList()
                val last = m.maxOrNull() ?: return@Thread
                val fmt = java.text.SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", java.util.Locale.US)
                fmt.timeZone = java.util.TimeZone.getTimeZone("UTC")
                val t = fmt.parse(last)!!.time
                // la release viene pubblicata ~1-3 minuti dopo la compilazione: serve un margine
                if (t > BuildConfig.BUILD_TIME + 15 * 60 * 1000) {
                    runOnUiThread {
                        AlertDialog.Builder(this)
                            .setTitle("Aggiornamento disponibile")
                            .setMessage("È uscita una nuova versione di Melodia. Vuoi scaricarla?")
                            .setPositiveButton("Scarica") { _, _ ->
                                try { startActivity(Intent(Intent.ACTION_VIEW, Uri.parse("https://github.com/tommyborgo/melodia-app/releases/latest/download/melodia.apk"))) } catch (_: Exception) {}
                            }
                            .setNegativeButton("Più tardi", null).show()
                    }
                }
            } catch (_: Exception) {}
        }.start()
    }

    private fun askHomeShortcut() {
        try {
            if (Build.VERSION.SDK_INT >= 26) {
                val sm = getSystemService(ShortcutManager::class.java)
                if (sm.isRequestPinShortcutSupported) {
                    val i = Intent(this, MainActivity::class.java).setAction(Intent.ACTION_MAIN)
                    val info = ShortcutInfo.Builder(this, "melodia_home")
                        .setShortLabel("Melodia").setLongLabel("Melodia")
                        .setIcon(Icon.createWithResource(this, R.mipmap.ic_launcher))
                        .setIntent(i).build()
                    sm.requestPinShortcut(info, null)
                }
            } else {
                val i = Intent(this, MainActivity::class.java).setAction(Intent.ACTION_MAIN)
                val add = Intent("com.android.launcher.action.INSTALL_SHORTCUT")
                add.putExtra(Intent.EXTRA_SHORTCUT_INTENT, i)
                add.putExtra(Intent.EXTRA_SHORTCUT_NAME, "Melodia")
                add.putExtra(Intent.EXTRA_SHORTCUT_ICON_RESOURCE, Intent.ShortcutIconResource.fromContext(this, R.mipmap.ic_launcher))
                sendBroadcast(add)
            }
        } catch (_: Exception) {}
    }

    private fun waitAndLoad() {
        if (loaded) return
        loaded = true
        Thread {
            var ok = false
            val t0 = System.currentTimeMillis()
            while (System.currentTimeMillis() - t0 < 120000) {
                try {
                    val c = URL(home + "api/server_info").openConnection() as HttpURLConnection
                    c.connectTimeout = 800; c.readTimeout = 2000
                    if (c.responseCode == 200) { ok = true; break }
                } catch (_: Exception) {}
                Thread.sleep(400)
            }
            runOnUiThread {
                if (ok) web.loadUrl(home)
                else { status.text = "Melodia\nMotore non partito:\n" + (ServerService.lastError ?: "timeout"); loaded = false }
            }
        }.start()
    }

    @Deprecated("")
    override fun onBackPressed() {
        if (web.canGoBack()) web.goBack() else moveTaskToBack(true)
    }

    // NIENTE web.onPause(): così la musica continua con lo schermo spento / app in background.
    override fun onResume() {
        super.onResume()
        if (Build.VERSION.SDK_INT >= 26 && !ServerService.started) {
            val svc = Intent(this, ServerService::class.java); startForegroundService(svc)
        }
    }
}
