"""Melodia per computer (Windows, Mac, Linux): avvia il motore musicale in locale e apre Melodia nel browser.
Stesso server dell'app Android; account e playlist restano sul server cloud, la musica la trova il tuo computer."""
import os, sys, time, shutil, socket, threading, webbrowser

PORT = 5000
URL = 'http://127.0.0.1:%d/' % PORT


def resource(name):
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def port_open():
    s = socket.socket()
    s.settimeout(0.4)
    try:
        s.connect(('127.0.0.1', PORT))
        return True
    except Exception:
        return False
    finally:
        s.close()


def setup_ffmpeg(www):
    """Usa l'ffmpeg incluso (imageio-ffmpeg) per la conversione in WAV, senza chiedere nulla all'utente."""
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        bindir = os.path.join(www, 'bin')
        os.makedirs(bindir, exist_ok=True)
        dst = os.path.join(bindir, 'ffmpeg.exe' if os.name == 'nt' else 'ffmpeg')
        if not os.path.exists(dst) or os.path.getsize(dst) != os.path.getsize(exe):
            shutil.copyfile(exe, dst)
            os.chmod(dst, 0o755)
        os.environ['PATH'] = bindir + os.pathsep + os.environ.get('PATH', '')
    except Exception as e:
        print('ffmpeg non disponibile (il download in WAV non funzionerà):', e)


def main():
    if port_open():
        print('Melodia è già aperta: la riapro nel browser.')
        webbrowser.open(URL)
        return
    root = os.path.join(os.path.expanduser('~'), 'Melodia')
    www = os.path.join(root, '.app')
    os.makedirs(www, exist_ok=True)
    for f in ('spotify_moto.html', 'sw.js'):
        shutil.copyfile(resource(f), os.path.join(www, f))
    os.environ['MELODIA_ROOT'] = root
    os.environ['MELODIA_WWW'] = www
    os.environ['MELODIA_DATA_DIR'] = os.path.join(root, 'testi')
    os.environ['TMPDIR'] = os.path.join(www, 'tmp')
    for d in (os.environ['MELODIA_DATA_DIR'], os.environ['TMPDIR']):
        os.makedirs(d, exist_ok=True)
    import tempfile
    tempfile.tempdir = os.environ['TMPDIR']
    setup_ffmpeg(www)
    os.chdir(www)
    print('=' * 52)
    print('  MELODIA — avvio del motore musicale…')
    print('  Non chiudere questa finestra finché ascolti musica.')
    print('  Le tue canzoni sono nella cartella:', root)
    print('=' * 52)
    import server
    t = threading.Thread(target=lambda: server.app.run(host='127.0.0.1', port=PORT, threaded=True, use_reloader=False), daemon=True)
    t.start()
    for _ in range(80):
        if port_open():
            break
        time.sleep(0.25)
    webbrowser.open(URL)
    print('Melodia è aperta nel browser: %s' % URL)
    print('Per chiudere Melodia chiudi questa finestra.')
    try:
        while t.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
