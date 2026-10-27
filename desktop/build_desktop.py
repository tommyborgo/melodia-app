"""Costruisce l'eseguibile Melodia per il sistema su cui gira (usato da GitHub Actions)."""
import os, sys, subprocess, shutil, platform
sep = ';' if os.name == 'nt' else ':'
name = 'Melodia'
args = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onefile', '--name', name,
        '--add-data', 'spotify_moto.html' + sep + '.', '--add-data', 'sw.js' + sep + '.',
        '--collect-all', 'yt_dlp', '--collect-all', 'imageio_ffmpeg',
        '--hidden-import', 'server', '--hidden-import', 'android_glue',
        '--exclude-module', 'tkinter', 'desktop_main.py']
print(' '.join(args))
subprocess.check_call(args)
print(os.listdir('dist'))
