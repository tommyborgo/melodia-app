"""Colla Android: avvia il server Melodia locale (stesso server.py del PC) dentro l'app,
inoltra al cloud Render le sole funzioni di account/sincronizzazione, e sostituisce ffmpeg
con il convertitore WAV nativo di Android."""
import os, sys, re, time, threading, urllib.request, urllib.error

CLOUD = os.environ.get('MELODIA_CLOUD', 'https://melodia-server-9yo3.onrender.com').rstrip('/')
CLOUD_PREFIXES = ('/api/register', '/api/login', '/api/account_data', '/api/sync',
                  '/api/share_playlist', '/api/get_shared', '/api/share_track',
                  '/api/get_shared_track', '/api/connect/sync', '/api/feedback',
                  '/api/cat/', '/api/announce', '/api/push')

_ui = {'started': False}
_EXTRAS_RE = re.compile(r'<script[^>]*melodia_extras\.js[^>]*></script>')


def _ui_file():
    return os.path.join(os.environ.get('MELODIA_DATA_DIR', '.'), 'cloud_ui.html')


def _refresh_ui():
    """Scarica dal cloud l'ultima versione dell'interfaccia (così le novità arrivano senza reinstallare l'app)."""
    while True:
        try:
            req = urllib.request.Request(CLOUD + '/spotify_moto.html?app=1', headers={'User-Agent': 'MelodiaApp'})
            with urllib.request.urlopen(req, timeout=90) as r:
                if r.status == 200:
                    html = r.read().decode('utf-8', 'replace')
                    if len(html) > 100000 and '</body>' in html and 'function goHome' in html:
                        html = _EXTRAS_RE.sub('', html)
                        tmp = _ui_file() + '.tmp'
                        with open(tmp, 'w', encoding='utf-8') as f:
                            f.write(html)
                        os.replace(tmp, _ui_file())
        except Exception:
            pass
        time.sleep(6 * 3600)


def init(app, request, jsonify, Response):
    @app.before_request
    def _cloud_ui():
        p = request.path
        if p in ('/', '/spotify_moto.html') or p.startswith('/s/'):
            if not _ui['started']:
                _ui['started'] = True
                threading.Thread(target=_refresh_ui, daemon=True).start()
            try:
                with open(_ui_file(), encoding='utf-8') as f:
                    html = f.read()
                r = Response(html, mimetype='text/html')
                r.headers['Cache-Control'] = 'no-store'
                return r
            except Exception:
                return None   # nessuna copia ancora: usa quella inclusa nell'app
        return None

    @app.before_request
    def _to_cloud():
        p = request.path
        if not p.startswith(CLOUD_PREFIXES):
            return None
        url = CLOUD + p
        qs = request.query_string.decode('utf-8', 'ignore')
        if qs:
            url += '?' + qs
        data = request.get_data() if request.method in ('POST', 'PUT') else None
        req = urllib.request.Request(url, data=data, method=request.method,
                                     headers={'Content-Type': request.headers.get('Content-Type', 'application/json')})
        try:
            with urllib.request.urlopen(req, timeout=75) as r:
                return Response(r.read(), status=r.status, content_type=r.headers.get('Content-Type', 'application/json'))
        except urllib.error.HTTPError as e:
            return Response(e.read(), status=e.code, content_type=e.headers.get('Content-Type', 'application/json'))
        except Exception as e:
            return jsonify({'error': 'cloud_unreachable', 'detail': str(e)}), 503


    @app.after_request
    def _inject(resp):
        try:
            p = request.path
            if (p in ('/', '/spotify_moto.html') or p.startswith('/s/')) and resp.status_code == 200 and resp.mimetype == 'text/html':
                html = resp.get_data(as_text=True)
                if '</body>' in html and 'melodia_extras.js' not in html:
                    tag = '<script async src="%s/melodia_extras.js"></script>' % CLOUD
                    resp.set_data(html.replace('</body>', tag + '</body>', 1))
        except Exception:
            pass
        return resp


def patch_ffmpeg():
    from yt_dlp.postprocessor import ffmpeg as F
    from yt_dlp.utils import PostProcessingError
    from java import jclass
    Wav = jclass('com.melodia.app.Wav')

    def run(self, info):
        src = info['filepath']
        codec = getattr(self, 'mapping', None) or getattr(self, '_preferredcodec', 'best')
        if codec != 'wav':
            raise PostProcessingError('Conversione in %s non disponibile su Android' % codec)
        dst = os.path.splitext(src)[0] + '.wav'
        Wav.convert(src, dst)
        info['filepath'] = dst
        info['ext'] = 'wav'
        return [src] if src != dst else [], info

    F.FFmpegExtractAudioPP.run = run


def start(root, www, port=5000):
    os.environ['MELODIA_ROOT'] = root
    os.environ['MELODIA_WWW'] = www
    os.environ['MELODIA_DATA_DIR'] = os.path.join(root, 'testi')
    os.environ['TMPDIR'] = os.path.join(www, 'tmp')
    os.makedirs(os.environ['TMPDIR'], exist_ok=True)
    os.makedirs(os.environ['MELODIA_DATA_DIR'], exist_ok=True)
    os.chdir(www)
    import tempfile
    tempfile.tempdir = os.environ['TMPDIR']
    patch_ffmpeg()
    import server
    server.app.run(host='127.0.0.1', port=port, threaded=True, use_reloader=False)
