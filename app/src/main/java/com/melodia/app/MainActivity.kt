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
