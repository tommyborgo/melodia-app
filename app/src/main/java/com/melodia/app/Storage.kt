package com.melodia.app

import android.content.Context
import android.os.Build
import android.os.Environment
import java.io.File

object Storage {
    const val FOLDER = "MELODIADEFINITIVA"

    fun hasAllFiles(): Boolean =
        if (Build.VERSION.SDK_INT >= 30) Environment.isExternalStorageManager() else true

    /** Cartella principale: /storage/emulated/0/MELODIADEFINITIVA (se permesso), altrimenti cartella privata dell'app. */
    fun root(ctx: Context): File {
        val dir = if (hasAllFiles()) File(Environment.getExternalStorageDirectory(), FOLDER)
        else File(ctx.getExternalFilesDir(null) ?: ctx.filesDir, FOLDER)
        try {
            dir.mkdirs()
            for (n in listOf("canzoni scaricate", "brani riprodotti", "testi")) File(dir, n).mkdirs()
        } catch (_: Exception) {}
        return dir
    }
}
