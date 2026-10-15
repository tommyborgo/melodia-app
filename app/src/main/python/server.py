from flask import Flask, request, jsonify, send_file, Response
import yt_dlp
import os
import tempfile
import shutil  # Importato per pulire le cartelle temporanee
import json
import hashlib
import time
import re
import threading
import urllib.request
import urllib.parse

app = Flask(__name__)
import android_glue; android_glue.init(app, request, jsonify, Response)

# ══════════ SINCRONIZZAZIONE PC ↔ TELEFONO ══════════
# Il PC mantiene il proprio server indipendente. Quando il server gira su Termux,
# prova anche a parlare con il server del PC tramite il dominio fisso del tunnel.
# Se il PC è spento/non raggiungibile, il telefono continua normalmente in locale.
PC_SYNC_URL = os.environ.get('MELODIA_PC_URL', 'https://melodiapremiumtb.dpdns.org').rstrip('/')
import secrets as _sec0
SYNC_TOKEN = os.environ.get('MELODIA_SYNC_TOKEN') or _sec0.token_urlsafe(32)  # nessuna chiave fissa nel codice

def _is_phone_server():
    return 'TERMUX_VERSION' in os.environ or 'com.termux' in os.environ.get('PREFIX', '')

def _peer_json(path, payload=None, timeout=2.5):
    """Chiamata server→server best-effort: non deve mai bloccare l'app se il PC è spento."""
    try:
        url = PC_SYNC_URL + path
        headers = {'Content-Type': 'application/json', 'X-Melodia-Sync-Token': SYNC_TOKEN}
        if payload is None:
            req = urllib.request.Request(url, headers=headers, method='GET')
        else:
            req = urllib.request.Request(url, data=json.dumps(payload, ensure_ascii=False).encode('utf-8'), headers=headers, method='POST')
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception:
        return None

@app.route('/api/server_info')
def server_info():
    # Termux imposta sempre questa variabile d'ambiente: è il modo più affidabile per
    # distinguere "sto girando sul telefono" da "sto girando su PC", senza bisogno di
    # configurare nulla a mano.
    is_phone = _is_phone_server()
    return jsonify({'device': 'telefono' if is_phone else 'computer', 'role': 'phone' if is_phone else 'computer'})

@app.route('/api/peer/status')
def peer_status():
    # Endpoint leggerissimo usato dal telefono come heartbeat del PC.
    # Se questa risposta arriva, il tunnel sta realmente portando la richiesta al server PC.
    if request.headers.get('X-Melodia-Sync-Token') != SYNC_TOKEN:
        return jsonify({'error':'forbidden'}), 403
    return jsonify({'online': True, 'device': 'computer', 'ts': time.time()})

@app.route('/api/server_status')
def server_status():
    # Sul telefono controlliamo il PC in tempo reale. Sul PC non serve contattare se stesso.
    if not _is_phone_server():
        return jsonify({'localDevice':'computer','pcOnline':True,'activeServer':'computer'})
    peer = _peer_json('/api/peer/status', timeout=1.8)
    pc_online = bool(peer and peer.get('online'))
    return jsonify({
        'localDevice':'telefono',
        'pcOnline':pc_online,
        'activeServer':'computer' if pc_online else 'telefono',
        'checkedAt':time.time()
    })

# Icone dell'app (PNG generati, necessari per la vera installazione PWA su Android:
# Chrome richiede icone in formato PNG/WebP, le SVG da sole non bastano per l'installabilita').
ICON_192='iVBORw0KGgoAAAANSUhEUgAAAMAAAADACAIAAADdvvtQAAADVUlEQVR4nO3dwW3bQBCGUTpIG6knDaRMN5B63EgOCwg+5GD5p7gzw/fOtrAmP48ki+a+/fr754Dv+rF7AfQmICICIiIgIgIiIiAiAiIiICICIiIgIgIiIiAiAiIiICICIiIgIgIiIiAiAiIiICICIiIgIgIiIiAiAiIiICICIiIgIgIiIiAiAiIiICICIiIgIgIiIiAiAiIiICICIiIgIgIi8nP3Ahr7+P3+lS+bvReACfRyH7/fv5haRwK6yNSMBHSpeRkJaINJGQlomxkNCWinAaNIQPu1zkhAVTTNSEC1tMtIQBU1ykhAdbXISEDVFc9IQD2UzUhAnRTMSED9lGpIQC3VGUUCaqxCRgJqb29GAhpiV0auiR5i15XXAmpv70X7Amqswv97CKilCuksXkT3U6eewwTqpVQ6i4B6KJjOIqDqyqazCKiu4uksAqqoRTqLgGpplM4ioCrapbMIaL+m6SwC2ql1Oou/RG8zoJ7DBNpiRjqLgC41KZ1FQBeZl84ioJebms7iRTQRAREREBEBEREQEQERERARAREREBEBEREQEQERERARAREREBEBEREQEQERERARAREREBEBEREQEQERERARAREREBEBEREQEQERuentXb64ud/sO7Oc4kYBfWNHyM/fIqb/mh/QWTuJPh5HSZ9NDuhFm9Cuh5XRMjOgC/Yv3r5hexED34U5tVcaNYGkc705E0g9WwwJSD27TAhIPRu1D0g9e7UPiL16B2T8bNc4IPVU0DggKhAQka4Bef4qomtAFCEgIgIiMurT+GrucNGZCUREQES6BlT/2aH+Ck/RNSCKEBCRxgFVfo6ovLZzNQ7oqHqeaq7qRXoHxHbtA6r2615tPa/WPqCj0jmrs5LLTAjoqHHmKqzhekMCOnafv3vWcxzH27yf/OJrzeYdwKfMmUAPV57Rm9dzjJxADy8dRYOP21MmB7ScntH4I/aU+QE9hCXd50A95UYBfeYurWe5aUCcZeC7MK4kICICIiIgIgIiIiAiAiIiICICIiIgIgIiIiAiAiIiICICIiIgIgIiIiAiAiIiICICIiIgIgIiIiAiAiIiICICIiIgIgIiIiAiAiIiICICIiIgIgIiIiAiAiIiICICIiIgIgIi8g8VPa2Gx/SGgwAAAABJRU5ErkJggg=='
ICON_512='iVBORw0KGgoAAAANSUhEUgAAAgAAAAIACAIAAAB7GkOtAAAKJElEQVR4nO3c23UURwBF0bEXaSgeEiBMElA8JOIPvEAIPebRj6o6e/8b2j3qe6ZGEv88PX+7ANDz79kXAMA5BAAgSgAAogQAIEoAAKIEACBKAACiBAAgSgAAogQAIEoAAKIEACBKAACiBAAgSgAAogQAIEoAAKIEACBKAACiBAAgSgAAogQAIEoAAKIEACBKAACiBAAgSgAAogQAIEoAAKIEACBKAACiBAAgSgAAogQAIEoAAKIEACBKAACiBAAgSgAAogQAIEoAAKIEACBKAACiBAAgSgAAogQAIEoAAKIEACBKAACiBAAgSgAAogQAIEoAAKIEACBKAACiBAAgSgAAogQAIEoAAKIEACBKAACiBAAgSgAAogQAIEoAAKIEACBKAACiBAAgSgAAogQAIEoAAKIEACBKAACiBAAgSgAAogQAIEoAAKIEACBKAACiBAAgSgAAogQAIEoAAKIEACBKAACiBAAgSgAAogQAIEoAAKIEACBKAACiBAAgSgAAogQAIEoAAKIEACBKAACiBAAgSgAAogQAIEoAAKIEACBKAACiBAAgSgAAogQAIEoAAKIEACBKAACiBAAgSgAAor6cfQGwiB9fv+/65z89f9v1zyfICQDm8OPr970bQ40AwExkgA0JAMxHBtiEAMCsZIAHCQDMTQa4mwDACjSAOwgALMJRgFsJACxFBrieAMCCZIBrCAAsSwb4mADA4mSA9wgAJMgAfxMACJEBXhIAyJEBfhIAiJIBBADSNKBMAKDOUSBLAIDLRQaSBAD4TQZSBAB4TQYiBAB4mwwsTwCAj8jAwgQA+JwMLEkAgGvJwGIEALiNDCxDAIB7aMACBAC4k6PA7AQAeIgMzEsAgA3IwIwEANiMDMxFAICNycAsBADYhQyMTwCAHcnAyAQA2J0MjEkAgIPIwGgEADiUBoxDAICjOQoMQgCAc8jA6QQAOJMMnEgAgPPJwCkEABiFDBxMAICxyMBhBAAYkQwcQACAccnArgQAGJ0M7EQAgDlowOYEAJiGo8C2BACYjAxsRQCAKcnA4wQAmJgMPEIAgOnJwH2+nH0BAI96ev529iVMSQCAiZn+RwgAMCXT/zjfAwDmY/034QQAzMT0b0gAgDmY/s0JADA6078TAQDGZfp3JQDAiEz/AQQAGIvpP4wAAKMw/QfzewDAEKz/8ZwAgJOZ/rMIAHAa038uAQBOYPpHIADAoUz/OAQAOIjpH40AALsz/WPyY6DAvqz/sJwAgL2Y/sEJALA90z8FAQC2ZPonIgDANkz/dAQAeJTpn5QAAPcz/VMTAOAepn8Bfg8AuJn1X4MTAHAD078SAQCuYvrXIwDAJ0z/qgQAeJfpX5sAAG8w/QUCAPzB9Hf4MVDgN+uf4gQAXC6mP0kAoM70ZwkAdJn+OAGAItPPRQCgxvTziwBAhennFT8GCgnWn785AcDiTD/vEQBYlunnYwIACzL9XEMAYCmmn+sJACzC9HMrAYDpmX7uIwAwMdPPI/weAMzK+vMgJwCYj+lnEwIAMzH9bEgAYA6mn835HgBAlAAARAkAQJQAAEQJAECUAABECQBAlAAARAkAQJQAAEQJAECUAABECQBAlAAARAkAQJQAAEQJAECUAABECQBAlAAARAkAQJQAAEQJAECUAABECQBAlAAARAkAQJQAAEQJAECUAABECQBAlAAARAkAQJQAAEQJAECUAABECQBAlAAARAkAQJQAAEQJAECUAABECQBAlAAARAkAQJQAAEQJAECUAABECQBAlAAARAkAQJQAAEQJAECUAABECQBAlAAARAkAQJQAAEQJAECUAABECQBAlAAARAkAQJQAAEQJAECUAABECQBAlAAARAkAQJQAAEQJAECUAABECQBAlAAARAkAQJQAAEQJAECUAABECQBAlAAARAkAQNSXsy8APvHj6/dH/vOn529bXQksRgAYyINbf/2fqQpwEQDOtcfi3/H36gFNAsDRzhr9D7y8JDGgQwA4yIC7/6Zf16kELE8A2Ncsu/83JWB5AsAu5t39vykBqxIANrbS9L/y839NBliGALCZhaf/JRlgGQLAoyK7/4rPhViAfwqChzTX/yV3gHk5AXAnw/eLW8GkBICb2TtYg4+AuI31h2U4AXAt0w+LcQLgKtYf1uMEwCdMP6zKCYCPWH9YmADwLusPaxMA3mb9YXkCwBusPxQIAK9Zf4gQAP5g/aFDAPjN+kOKAPA/6w81AsDlYv0hSQCw/hAlAHXWH7IEACBKANK8/YcyAeiy/hAnAABRAhDl7T8gAEXWH7gIAECWAOR4+w/8JAAAUQIAECUALT7/AX4RAIAoAQCIEoAQn/8ALwkAQJQAAEQJAECUAFT4BgDwigAARAkAQJQAAEQJAECUAABECQBA1JezLwB429Pzt7MvgcU5AQBECQBAlAAARAkAQJQAVPiO4ly8XhxAAACiBAAgSgAAogQgxMfKs/BKcQwBAIgSAIAoAWjx2cL4vEYcRgAAogQAIEoAcnzCMDKvDkcSAIAoASjyNnNMXhcOJgBRtmY0XhGOJwAAUQLQ5S3nOLwWnEIA0uzOCLwKnEUAAKIEoM7bz3O5/5xIALBBp3HnOZcAcLlYojO455xOAPifPTqSu80IBIDfrNIx3GcGIQD8wTbtzR1mHALAaxZqP+4tQxEA3mCn9uCuMhoB4G3WalvuJwMSAN5ls7biTjImAeAjlutx7iHD+sdXJ9f48fX72ZcwHw8Xg3MC4Cq27FbuGONzAuA2jgKf8kwxCycAbmPdPub+MBEnAO7kKPCKR4npCAAPkYGL6WdaPgLiIbbPHWBeTgBsJnUa8OCwAAFgY8tnwCPDMgSAXSyZAQ8LixEA9rVACTwjrEoAOMh0JfBosDwB4GiDl8ATQYcAcKZBYuApoEkAGMhhPfBlDxcBYHwPVsFXOLxHAACi/FMQAFECABAlAABRAgAQJQAAUQIAECUAAFECABAlAABRAgAQJQAAUQIAECUAAFECABAlAABRAgAQJQAAUQIAECUAAFECABAlAABRAgAQJQAAUQIAECUAAFECABAlAABRAgAQJQAAUQIAECUAAFECABAlAABRAgAQJQAAUQIAECUAAFECABAlAABRAgAQJQAAUQIAECUAAFECABAlAABRAgAQJQAAUQIAECUAAFECABAlAABRAgAQJQAAUQIAECUAAFECABAlAABRAgAQJQAAUQIAECUAAFECABAlAABRAgAQJQAAUQIAECUAAFECABAlAABRAgAQJQAAUQIAECUAAFECABAlAABRAgAQJQAAUQIAECUAAFECABAlAABRAgAQJQAAUQIAECUAAFECABAlAABRAgAQJQAAUQIAECUAAFECABAlAABRAgAQJQAAUQIAECUAAFECABAlAABRAgAQJQAAUQIAECUAAFECABAlAABRAgAQJQAAUQIAECUAAFECABAlAABRAgAQ9R93e8Tf+uQkPwAAAABJRU5ErkJggg=='
ICON_192_M='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'
ICON_512_M='iVBORw0KGgoAAAANSUhEUgAAAgAAAAIACAIAAAB7GkOtAAAXoUlEQVR4nO3de5CdZ33Y8ed9zzl79iqtpJUsyZaxJBvfL7Hx3RgKHS7GSQZIoB2STGEKnTLpAG7CQM1wh2KaGVryX5NO20D/CG0ZYFqmuLUNBDu2wRDAdjA2qWxs67q6757dc3mf/mGCDbUtrbSrs3t+n89f2pF09JuR9H73fZ7zPqfY8o3fSQDEU/Z7AAD6QwAAghIAgKAEACAoAQAISgAAghIAgKAEACAoAQAISgAAghIAgKAEACAoAQAISgAAghIAgKAEACAoAQAISgAAghIAgKAEACAoAQAISgAAghIAgKAEACAoAQAISgAAghIAgKAEACAoAQAISgAAghIAgKAEACAoAQAISgAAghIAgKAEACAoAQAISgAAghIAgKAEACAoAQAISgAAghIAgKAEACAoAQAISgAAghIAgKAEACAoAQAISgAAghIAgKAEACAoAQAISgAAghIAgKAEACAoAQAISgAAghIAgKAEACAoAQAISgAAghIAgKAEACAoAQAISgAAghIAgKAEACAoAQAISgAAghIAgKAEACAoAQAISgAAghIAgKAEACAoAQAISgAAghIAgKAEACAoAQAISgAAghIAgKAEACAoAQAISgAAghIAgKAEACAoAQAISgAAghIAgKAEACAoAQAISgAAghIAgKAEACAoAQAISgAAghIAgKAEACAoAQAISgAAghIAgKAEACAoAQAISgAAghIAgKAEACAoAQAISgAAghIAgKAEACAoAQAISgAAghIAgKAEACAoAQAISgAAghIAgKAEACAoAQAISgAAghIAgKAEACAoAQAISgAAghIAgKAEACAoAQAISgAAghIAgKAEACAoAQAISgAAghIAgKAEACAoAQAISgAAgqr3ewBYqYpmbdFeq8q5Uy3aq8HxEQA4ITm37n4q9/KivFj9tNHmJRuqo+1ULc4LwvEQADgRuZf33vqdxXq1+saxsdduHXvD1sbm8Wqms1gvCy9OAOAEFcO1PNdblJfq7po59J8fbN39VGP75LoPXJm7ORUpLdLtBbwQAYDlov3YgfZjB+bu3zn+5nMmbtpWrhlO2d4AS8i7gGB56R2YO/TnP37yTV+d+T+Ptx89WAzXkzsBloYAwDI1/al793347vZP9tcmm6no9zQMIgGA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85Kq1S0aZW3DWMo5t6vqqKe6GHyWgFhOyuIX19y/X2wvm7WZu35+9KuPPffXzH1v10JfePiyDc9sP/ziyys3rv69C6pfPr31yz+0sspPIALAclfUy9Qon/vl4f/ycO/A/AJeoVaufsdFqV48+8RWL+f5nm/wCc4SEMtd7lbpOUfL5ZQm3npeUS7k4p1TNdtJv/bYlqs/4QkAK09uda3UwMnzeQAAQQkAQFACABCUAAAEJQAAQQkAQFACABCUAAAEJQAAQQkAQFACABCUAAAEJQAAQQkAQFACABCUAAAEJQAAQQkAQFACABCUAAAEJQAAQQkAQFACABCUAAAEJQAAQQkAQFACABCUAAAEJQAAQQkAQFACABCUAAAEJQAAQQkAQFACABCUAAAEJQAAQQkAQFACABCUAAAEJQAAQQkAQFACABCUAAAEJQAAQQkAQFACABCUAAAEJQAAQQkAQFACABCUAAAEJQAAQQkAQFACABCUAAAEJQAAQQkAQFACABCUAAAEJQAAQQkAQFACABCUAAAEJQAAQQkAQFACABCUAAAEJQAAQQkAQFACABCUAAAEJQAAQQkAQFACABCUAAAEJQAAQQkAQFACABCUAAAEJQAAQQkAQFACABCUAAAEJQAAQQkAQFACABCUAAAEJQAAQQkAQFACABCUAAAEJQAAQQkAQFACABCUAAAEJQAAQQkAQFACABCUAAAEJQAAQQkAQFACABCUAAAEJQAAQQkAQFACABCUAAAEJQAAQQkAQFACABCUAAAEJQAAQQkAQFACABCUAAAEJQAAQQkAQFACABCUAAAEJQAAQQkAQFACABCUAAAEJQAAQQkAQFACABCUAAAEJQAAQQkAQFACABCUAAAEJQAAQQkAQFACABCUAAAEJQAAQQkAQFACABDU/wPD2GDmjs5NQQAAAABJRU5ErkJggg=='



BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.environ.get('MELODIA_ROOT') or BASE_DIR
WWW_DIR = os.environ.get('MELODIA_WWW') or BASE_DIR

# YouTube ha iniziato a chiedere una verifica "non sono un robot" per molti video, e in questo
# periodo sta avendo anche problemi lato suo (guasti noti e diffusi in queste settimane, non
# nostri). Qui usiamo solo i cookie, senza forzare un client specifico: lasciamo che yt-dlp
# scelga da solo la combinazione migliore secondo la sua versione più recente.
COOKIES_FILE = os.path.join(BASE_DIR, 'cookies.txt')
_cookies_lock = threading.Lock()

def _cookie_opts():
    """Ogni chiamata riceve una copia privata e "usa e getta" del file dei cookie, invece di
    puntare tutte quante allo stesso file condiviso: con più richieste in corso insieme
    (ricerche, download, "prefetch" della coda tutti in parallelo), yt-dlp leggeva E
    riscriveva lo stesso file da più thread contemporaneamente, corrompendolo a intermittenza
    — la causa vera dei "does not look like a Netscape format cookies file" nel log."""
    if not os.path.exists(COOKIES_FILE):
        return {'extractor_args': {'youtube': {'player_client': ['android_vr', 'default']}}}
    with _cookies_lock:
        try:
            with open(COOKIES_FILE, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception:
            return {}
    tmp = tempfile.NamedTemporaryFile(mode='w', suffix='_cookies.txt', delete=False, encoding='utf-8')
    tmp.write(content)
    tmp.close()
    return {
        'cookiefile': tmp.name,
        # Combinazione consigliata direttamente dagli sviluppatori di yt-dlp per questo
        # identico guasto (segnalazione ufficiale #17389, ancora aperta in queste settimane).
        'extractor_args': {'youtube': {'player_client': ['default', 'web_embedded']}},
    }


# I dati veri e propri (account, coda/posizione condivisa, cache testi) possono vivere in una
# cartella diversa da quella del codice — utile per metterli dentro OneDrive, così PC e
# telefono (quando fanno da server a turno) leggono/scrivono sempre gli stessi identici dati,
# invece di avere ciascuno la propria copia separata e disallineata.
DATA_DIR = os.environ.get('MELODIA_DATA_DIR', BASE_DIR)
os.makedirs(DATA_DIR, exist_ok=True)
try:
    import hf_store
    hf_store.start(DATA_DIR, BASE_DIR)
except Exception as _e:
    print('hf_store errore:', _e)
USERS_FILE = os.path.join(DATA_DIR, 'users.json')
PHONE_SYNC_META_FILE = os.path.join(DATA_DIR, 'phone_sync_meta.json')

def _phone_sync_dirty(email):
    meta = safe_read_json(PHONE_SYNC_META_FILE, {})
    return bool(meta.get(email, {}).get('dirty'))

def _set_phone_sync_dirty(email, dirty):
    meta = safe_read_json(PHONE_SYNC_META_FILE, {})
    meta[email] = {'dirty': bool(dirty), 'updatedAt': time.time()}
    safe_write_json(PHONE_SYNC_META_FILE, meta, indent=2)

# ══════════ SCRITTURA SICURA DEI FILE DATI (contro corruzioni per scritture in contemporanea) ══════════
# Più richieste insieme (ricerche, sync, connect...) potevano scrivere sullo stesso file JSON
# nello stesso istante, corrompendolo (esattamente come era successo prima con i cookie).
# Questa funzione scrive prima su un file temporaneo e poi lo sostituisce in un solo colpo
# (operazione "atomica": chi legge non vede mai una versione a metà scritta), e un blocco
# per ogni file impedisce a due scritture dello stesso file di accavallarsi.
_file_locks = {}
_file_locks_lock = threading.Lock()
def _lock_for(path):
    with _file_locks_lock:
        if path not in _file_locks:
            _file_locks[path] = threading.RLock()
        return _file_locks[path]

def safe_write_json(path, data, indent=None):
    lock = _lock_for(path)
    with lock:
        dir_name = os.path.dirname(path) or '.'
        fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix='.tmp')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=indent, ensure_ascii=False)
            os.replace(tmp_path, path)  # sostituzione atomica
        except Exception:
            try:
                os.remove(tmp_path)
            except Exception:
                pass
            raise

def safe_read_json(path, default):
    lock = _lock_for(path)
    with lock:
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                # File corrotto, probabilmente da una vecchia scrittura sovrapposta di prima
                # di questa correzione: prova a recuperare la parte valida iniziale invece di
                # perdere tutto, poi riscrive subito il file ripulito.
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        raw = f.read()
                    recovered, _ = json.JSONDecoder().raw_decode(raw)
                    try:
                        safe_write_json(path, recovered, indent=2)
                    except Exception:
                        pass
                    return recovered
                except Exception:
                    return default
            except Exception:
                return default
        return default

# ══════════ GESTIONE ACCOUNT ══════════
def load_users():
    return safe_read_json(USERS_FILE, {})

def save_users(users):
    safe_write_json(USERS_FILE, users, indent=2)

def hash_password(password):
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json or {}
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''
    if not email or not password:
        return jsonify({'error': 'Email e password richiesti'}), 400
    if len(password) < 4:
        return jsonify({'error': 'La password deve avere almeno 4 caratteri'}), 400
    users = load_users()
    if email in users:
        return jsonify({'error': 'Account già esistente, accedi invece'}), 400
    users[email] = {
        'password': hash_password(password),
        'liked': [],
        'playlists': []
    }
    save_users(users)
    return jsonify({'success': True, 'email': email})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json or {}
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''
    users = load_users()
    if email not in users:
        return jsonify({'error': 'Account non trovato'}), 404
    if users[email]['password'] != hash_password(password):
        return jsonify({'error': 'Password errata'}), 401
    return jsonify({
        'success': True,
        'email': email,
        'data': {
            'liked': users[email].get('liked', []),
            'likedTracks': users[email].get('likedTracks', []),
            'playlists': users[email].get('playlists', []),
            'genres': users[email].get('genres', [])
        }
    })

# ══════════ PROTEZIONE DATI (anti-sovrascrittura + backup automatici) ══════════
BACKUP_DIR = os.path.join(DATA_DIR, 'backups')

def _auto_backup(force=False):
    """Copia users.json in backups/ (al massimo ogni 3 ore, ne tiene 60)."""
    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        files = sorted(f for f in os.listdir(BACKUP_DIR) if f.startswith('users_'))
        if files and not force:
            last = os.path.getmtime(os.path.join(BACKUP_DIR, files[-1]))
            if time.time() - last < 3*3600:
                return
        if os.path.exists(USERS_FILE):
            shutil.copy2(USERS_FILE, os.path.join(BACKUP_DIR, 'users_' + time.strftime('%Y%m%d_%H%M%S') + '.json'))
        for old in files[:-59]:
            try: os.remove(os.path.join(BACKUP_DIR, old))
            except Exception: pass
    except Exception as e:
        print('backup errore:', e)

def _count_pl(pls):
    try: return sum(len(p.get('tracks', [])) for p in pls)
    except Exception: return 0

def _guarded_apply(user, data, source=''):
    """Applica i dati in arrivo SOLO se non fanno perdere una parte grossa della libreria
    (liste vuote, versioni vecchie). Prima di ogni modifica fa un backup periodico."""
    _auto_backup()
    def ok(old, new, cnt):
        o, n = cnt(old), cnt(new)
        if o == 0: return True
        return n >= o - max(3, int(o * 0.15))
    if 'playlists' in data:
        if ok(user.get('playlists', []), data['playlists'], _count_pl):
            user['playlists'] = data['playlists']
        else:
            print('PROTEZIONE: playlist in arrivo (%s) piu piccole, ignorate' % source)
            _auto_backup(True)
    if 'likedTracks' in data:
        if ok(user.get('likedTracks', []), data['likedTracks'], len):
            user['likedTracks'] = data['likedTracks']
            if 'liked' in data: user['liked'] = data['liked']
        else:
            print('PROTEZIONE: preferiti in arrivo (%s) piu piccoli, ignorati' % source)
    elif 'liked' in data and (data['liked'] or not user.get('liked')):
        user['liked'] = data['liked']
    if 'genres' in data and (data['genres'] or not user.get('genres')):
        user['genres'] = data['genres']
    if 'stats' in data and (data['stats'] or not user.get('stats')):
        user['stats'] = data['stats']

_auto_backup(True)

@app.route('/api/account_data', methods=['GET'])
def account_data():
    """Restituisce la libreria del server corrente. Sul telefono, se il PC è online,
    il PC diventa la sorgente condivisa; eventuali modifiche locali rimaste offline
    vengono prima inviate al PC e solo dopo si scarica la versione sincronizzata."""
    email = (request.args.get('email') or '').strip().lower()
    users = load_users()
    if email not in users:
        return jsonify({'error': 'Account non trovato'}), 404
    if _is_phone_server():
        if _phone_sync_dirty(email):
            payload = _account_payload(users[email], email)
            pushed = _peer_json('/api/peer/sync', payload)
            if pushed and pushed.get('success'):
                _set_phone_sync_dirty(email, False)
        remote = _peer_json('/api/peer/account_data?email='+urllib.parse.quote(email, safe=''))
        if remote and remote.get('ok'):
            _guarded_apply(users[email], remote.get('data', {}), 'pull')
            save_users(users)
    return jsonify(_account_payload(users[email], email))

def _account_payload(user, email=None):
    return {
        'email': email,
        'liked': user.get('liked', []),
        'likedTracks': user.get('likedTracks', []),
        'playlists': user.get('playlists', []),
        'genres': user.get('genres', []),
        'stats': user.get('stats', {}),
    }

@app.route('/api/peer/account_data', methods=['GET'])
def peer_account_data():
    if request.headers.get('X-Melodia-Sync-Token') != SYNC_TOKEN:
        return jsonify({'error':'forbidden'}), 403
    email = (request.args.get('email') or '').strip().lower()
    users = load_users()
    if email not in users: return jsonify({'ok':False,'error':'Account non trovato'}), 404
    return jsonify({'ok':True,'data':{
        'liked':users[email].get('liked',[]),
        'likedTracks':users[email].get('likedTracks',[]),
        'playlists':users[email].get('playlists',[]),
        'genres':users[email].get('genres',[]),
        'stats':users[email].get('stats',{}),
    }})

@app.route('/api/sync', methods=['POST'])
def sync():
    data = request.json or {}
    email = (data.get('email') or '').strip().lower()
    users = load_users()
    if email not in users:
        return jsonify({'error': 'Account non trovato'}), 404
    _guarded_apply(users[email], data, 'sync')
    save_users(users)
    if _is_phone_server():
        peer = _peer_json('/api/peer/sync', _account_payload(users[email], email))
        _set_phone_sync_dirty(email, not bool(peer and peer.get('success')))
        return jsonify({'success': True, 'peerSynced': bool(peer and peer.get('success'))})
    return jsonify({'success': True})

@app.route('/api/peer/sync', methods=['POST'])
def peer_sync():
    if request.headers.get('X-Melodia-Sync-Token') != SYNC_TOKEN:
        return jsonify({'error':'forbidden'}), 403
    data = request.json or {}
    email = (data.get('email') or '').strip().lower()
    users = load_users()
    if email not in users:
        return jsonify({'error':'Account non trovato'}), 404
    # Il telefono diventa sorgente della verità quando ha accumulato modifiche mentre il PC era spento.
    _guarded_apply(users[email], data, 'sync')
    save_users(users)
    return jsonify({'success':True})

# ══════════ CONDIVISIONE PLAYLIST (link pubblico di sola lettura) ══════════


SHARES_FILE = os.path.join(DATA_DIR, 'shares.json')

def load_shares():
    return safe_read_json(SHARES_FILE, {})

def save_shares(shares):
    safe_write_json(SHARES_FILE, shares)

@app.route('/api/share_playlist', methods=['POST'])
def share_playlist():
    """Salva un'istantanea (nome + brani) di una playlist e restituisce un codice breve.
    Chi apre il link ottiene una copia di sola lettura da poter importare nella propria
    libreria — non è collegata in tempo reale alla playlist originale."""
    data = request.json or {}
    name = (data.get('name') or 'Playlist').strip()
    tracks = data.get('tracks') or []
    if not tracks:
        return jsonify({'error': 'Playlist vuota'}), 400
    shares = load_shares()
    code = secrets_token()
    shares[code] = {'name': name, 'tracks': tracks, 'created': time.time()}
    save_shares(shares)
    return jsonify({'code': code})

@app.route('/api/get_shared/<code>')
def get_shared(code):
    shares = load_shares()
    entry = shares.get(code)
    if not entry:
        return jsonify({'error': 'Link non valido o scaduto'}), 404
    return jsonify({'name': entry['name'], 'tracks': entry['tracks']})

@app.route('/api/share_track', methods=['POST'])
def share_track():
    """Salva un singolo brano (non una playlist intera) e restituisce un codice breve — usato
    dal tasto "Condividi" nel player. Chi apre il link può ascoltare SOLO quel brano, senza
    bisogno di nessun account."""
    data = request.json or {}
    title = (data.get('title') or '').strip()
    artist = (data.get('artist') or '').strip()
    if not title:
        return jsonify({'error': 'Brano non valido'}), 400
    shares = load_shares()
    code = secrets_token()
    shares[code] = {
        'type': 'track', 'title': title, 'artist': artist,
        'ytId': data.get('ytId') or '', 'thumb': data.get('thumb') or '',
        'created': time.time(),
    }
    save_shares(shares)
    return jsonify({'code': code})

@app.route('/api/get_shared_track/<code>')
def get_shared_track(code):
    """Pubblico, nessun accesso richiesto: chiunque apra un link di condivisione di un
    singolo brano deve poterlo ascoltare senza dover prima fare il login."""
    shares = load_shares()
    entry = shares.get(code)
    if not entry or entry.get('type') != 'track':
        return jsonify({'error': 'Link non valido o scaduto'}), 404
    return jsonify({'title': entry['title'], 'artist': entry['artist'], 'ytId': entry.get('ytId', ''), 'thumb': entry.get('thumb', '')})

def secrets_token():
    import secrets as _secrets
    return _secrets.token_urlsafe(6)

_prefetching = set()  # id dei video già in fase di download in background, per non duplicare il lavoro
# Limita quanti scaricamenti "pesanti" (canzoni) possono girare insieme in un dato momento.
# Sul telefono (molta meno potenza di calcolo di un PC), troppi download in contemporanea
# rallentavano anche le richieste leggere come la ricerca delle copertine — con questo
# limite, il resto in eccesso aspetta gentilmente il proprio turno invece di intasare tutto.
# Due "corsie" separate: quella del brano che stai ascoltando ORA (priorità) e quella dei
# download in background per la coda — così un brano cliccato per il play non deve mai
# aspettare in fila dietro gli scaricamenti "di scorta" della coda.
_foreground_slots = threading.Semaphore(2)  # /stream — quello che stai aspettando di ascoltare ORA
_background_slots = threading.Semaphore(1)  # /prefetch — preparazione silenziosa della coda

# ══════════ SPOTIFY CONNECT (stato di riproduzione condiviso tra i dispositivi dello stesso account) ══════════
# Il "chi è online adesso" resta solo in memoria (si ricostruisce da solo quando i dispositivi
# tornano a fare battito), ma l'ULTIMO stato di riproduzione (brano, posizione, coda) viene
# salvato anche su disco: così se spegni il PC (e quindi il server) e lo riaccendi più tardi,
# la canzone e la coda che stavi ascoltando sono ancora lì, pronte da riprendere.
_connect_lock = threading.Lock()
_connect_devices = {}    # email -> { deviceId: {name, lastSeen} }
CONNECT_TIMEOUT = 20  # secondi senza battito prima di considerare un dispositivo offline
CONNECT_STATE_FILE = os.path.join(DATA_DIR, 'connect_state.json')

def _load_connect_playback():
    return safe_read_json(CONNECT_STATE_FILE, {})

def _save_connect_playback():
    try:
        safe_write_json(CONNECT_STATE_FILE, _connect_playback)
    except Exception:
        pass

_connect_playback = _load_connect_playback()   # email -> {activeDeviceId, activeDeviceName, track, position, isPlaying, queue, updatedAt, revision}

# Contatore monotono per evitare che risposte HTTP arrivate in ritardo possano
# riportare un dispositivo allo stato precedente dopo un trasferimento Connect.
def _next_connect_revision(cur):
    try:
        return int((cur or {}).get('revision', 0)) + 1
    except Exception:
        return 1

@app.route('/api/connect/sync', methods=['POST'])
def connect_sync():
    """Endpoint unico, interrogato in polling continuo da ogni dispositivo collegato allo
    stesso account. Fa tre cose in una sola chiamata:
      1. registra/aggiorna la presenza di questo dispositivo (nome rilevato in automatico + battito)
      2. se richiesto (claim) o se è il dispositivo attivo, pubblica lo stato di riproduzione corrente
      3. restituisce a tutti l'elenco dispositivi + lo stato di riproduzione condiviso, così i
         dispositivi "in ascolto passivo" possono mostrare "In riproduzione su <nome>"."""
    data = request.json or {}
    email = (data.get('email') or '').strip().lower()
    device_id = data.get('deviceId')
    device_name = (data.get('deviceName') or 'Dispositivo').strip()[:60]
    if not email or not device_id:
        return jsonify({'error': 'missing params'}), 400
    claim = bool(data.get('claim'))
    playback = data.get('playback')  # {track, position, isPlaying}, se questo dispositivo sta suonando

    with _connect_lock:
        _connect_devices.setdefault(email, {})
        _connect_devices[email][device_id] = {'name': device_name, 'lastSeen': time.time()}
        now = time.time()
        for did in list(_connect_devices[email].keys()):
            if now - _connect_devices[email][did]['lastSeen'] > CONNECT_TIMEOUT:
                del _connect_devices[email][did]

        cur = _connect_playback.get(email)
        is_active = bool(cur) and cur.get('activeDeviceId') == device_id
        # Diventa attivo se: lo richiede esplicitamente (claim, es. "Connetti > questo dispositivo"),
        # oppure è il primissimo dispositivo in assoluto a pubblicare uno stato di riproduzione.
        if claim or (playback and not cur):
            is_active = True

        if is_active:
            base = cur if (cur and not playback) else {}
            changing_device = bool(cur) and cur.get('activeDeviceId') != device_id
            revision = _next_connect_revision(cur) if (changing_device or claim) else int((cur or {}).get('revision', 0) or 0)
            _connect_playback[email] = {
                'activeDeviceId': device_id,
                'activeDeviceName': device_name,
                'track': (playback or {}).get('track', base.get('track')),
                'position': (playback or {}).get('position', base.get('position', 0)),
                'isPlaying': (playback or {}).get('isPlaying', base.get('isPlaying', False)),
                'queue': (playback or {}).get('queue', base.get('queue', [])),
                'updatedAt': time.time(),
                'revision': revision
            }
            _save_connect_playback()

        devices_list = [{'id': k, 'name': v['name']} for k, v in _connect_devices[email].items()]
        st = _connect_playback.get(email)

    local_result = {'devices': devices_list, 'playback': st}
    # Sul server del telefono il PC è il punto di sincronizzazione quando è acceso.
    # Il tentativo è best-effort: se il PC non risponde, il telefono continua con il suo stato locale.
    if _is_phone_server():
        peer = _peer_json('/api/peer/connect_sync', data)
        if peer and isinstance(peer, dict) and ('playback' in peer):
            peer_pb = peer.get('playback') or {}
            peer_active_id = peer_pb.get('activeDeviceId')
            peer_rev = int(peer_pb.get('revision', 0) or 0)
            local_rev = int((st or {}).get('revision', 0) or 0)
            # IMPORTANTE: se il telefono sta VERAMENTE suonando in questo momento (ha appena
            # mandato il proprio stato di riproduzione ed è risultato lui il dispositivo attivo
            # qui in locale), la sua musica non deve MAI fermarsi solo perché sul PC è rimasto
            # salvato uno stato "fantasma" di una sessione precedente (magari con un altro
            # dispositivo segnato come attivo). Il PC vince solo se rappresenta davvero un
            # cambio più recente (revisione più alta) — non uno stato vecchio e fermo.
            sto_suonando_qui_ora = is_active and bool(playback)
            peer_dice_altro_dispositivo = bool(peer_active_id) and peer_active_id != device_id
            if sto_suonando_qui_ora and peer_dice_altro_dispositivo and peer_rev <= local_rev:
                # Ignora la risposta vecchia del PC, tieni la riproduzione del telefono. In
                # background, correggi anche il PC così la prossima volta risulta allineato.
                _peer_json('/api/peer/connect_sync', {**data, 'claim': True})
                return jsonify(local_result)
            return jsonify(peer)
    return jsonify(local_result)

@app.route('/api/peer/connect_sync', methods=['POST'])
def peer_connect_sync():
    if request.headers.get('X-Melodia-Sync-Token') != SYNC_TOKEN:
        return jsonify({'error':'forbidden'}), 403
    # Esegue la stessa logica di Connect direttamente sul server PC.
    data = request.json or {}
    email = (data.get('email') or '').strip().lower()
    device_id = data.get('deviceId')
    device_name = (data.get('deviceName') or 'Dispositivo').strip()[:60]
    if not email or not device_id: return jsonify({'error':'missing params'}), 400
    claim = bool(data.get('claim'))
    playback = data.get('playback')
    with _connect_lock:
        _connect_devices.setdefault(email, {})
        _connect_devices[email][device_id] = {'name':device_name,'lastSeen':time.time()}
        now=time.time()
        for did in list(_connect_devices[email]):
            if now-_connect_devices[email][did]['lastSeen'] > CONNECT_TIMEOUT:
                del _connect_devices[email][did]
        cur=_connect_playback.get(email)
        is_active=bool(cur) and cur.get('activeDeviceId')==device_id
        if claim or (playback and not cur): is_active=True
        if is_active:
            base=cur if (cur and not playback) else {}
            changing_device=bool(cur) and cur.get('activeDeviceId') != device_id
            revision=_next_connect_revision(cur) if (changing_device or claim) else int((cur or {}).get('revision',0) or 0)
            _connect_playback[email]={
                'activeDeviceId':device_id,'activeDeviceName':device_name,
                'track':(playback or {}).get('track',base.get('track')),
                'position':(playback or {}).get('position',base.get('position',0)),
                'isPlaying':(playback or {}).get('isPlaying',base.get('isPlaying',False)),
                'queue':(playback or {}).get('queue',base.get('queue',[])),
                'updatedAt':time.time(), 'revision':revision}
            _save_connect_playback()
        return jsonify({'devices':[{'id':k,'name':v['name']} for k,v in _connect_devices[email].items()], 'playback':_connect_playback.get(email)})

_AUDIO_EXT_MIME = {'m4a': 'audio/mp4', 'mp3': 'audio/mpeg', 'webm': 'audio/webm', 'opus': 'audio/ogg', 'ogg': 'audio/ogg', 'aac': 'audio/aac'}

def _find_cached(vid, save_dir):
    """Cerca un file già in cache per questo brano, in qualunque formato sia stato salvato."""
    for ext, mime in _AUDIO_EXT_MIME.items():
        p = os.path.join(save_dir, f"{vid}.{ext}")
        if os.path.exists(p):
            return p, mime
    return None, None

def _download_native_fast(vid, out_template):
    """Scarica l'audio nel suo formato originale (di solito m4a), SENZA ricodificarlo con
    ffmpeg: è molto più veloce (pochi secondi invece di uno o più minuti), ed è comunque
    riproducibile direttamente dal tag <audio> del browser. Se questo fallisce (capita per
    alcuni video con formati non standard), si può ripiegare sulla ricodifica in mp3."""
    ydl_opts = {
        'quiet': True, 'no_warnings': True,
        'format': 'bestaudio[ext=m4a]/bestaudio[acodec^=mp4a]/bestaudio',
        'outtmpl': out_template + '.%(ext)s', 'noplaylist': True,
        **_cookie_opts(),
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([f'https://www.youtube.com/watch?v={vid}'])

def _download_to_cache(vid):
    """Scarica un brano in background e lo salva nella cache, senza bloccare nessuna richiesta.
    Prova prima il formato nativo (veloce), poi ripiega sulla ricodifica mp3 solo se serve.
    Aspetta un "posto libero" se troppi altri download stanno già girando insieme."""
    with _background_slots:
        try:
            save_dir = os.path.join(ROOT_DIR, 'brani riprodotti')
            if not os.path.exists(save_dir):
                os.makedirs(save_dir)
            existing, _ = _find_cached(vid, save_dir)
            if existing:
                return
            out_template = os.path.join(save_dir, vid)
            try:
                _download_native_fast(vid, out_template)
                existing, _ = _find_cached(vid, save_dir)
                if existing:
                    return
            except Exception:
                pass
            # Riprova forzando IPv6 (aggira il blocco legato all'indirizzo condiviso IPv4)
            try:
                ydl_opts_v6 = {
                    'quiet': True, 'no_warnings': True,
                    'format': 'bestaudio[ext=m4a]/bestaudio[acodec^=mp4a]/bestaudio',
                    'outtmpl': out_template + '.%(ext)s', 'noplaylist': True,
                    'source_address': '::',
                    **_cookie_opts(),
                }
                with yt_dlp.YoutubeDL(ydl_opts_v6) as ydl:
                    ydl.download([f'https://www.youtube.com/watch?v={vid}'])
                existing, _ = _find_cached(vid, save_dir)
                if existing:
                    return
            except Exception:
                pass
            # Ripiego: ricodifica in mp3 (più lento, ma compatibile con qualsiasi formato sorgente)
            ydl_opts = {
                'quiet': True, 'no_warnings': True, 'format': 'bestaudio[ext=m4a]/bestaudio/best',
                'outtmpl': out_template + '.%(ext)s', 'noplaylist': True,
                'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
                **_cookie_opts(),
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([f'https://www.youtube.com/watch?v={vid}'])
        except Exception:
            pass
        finally:
            _prefetching.discard(vid)

# ══════════ MOTORE AUDIO ESTERNO (telefono/PC con indirizzo che YouTube accetta) ══════════
# Su Render YouTube blocca l'indirizzo del data center. Se MELODIA_ENGINE_URLS e impostata,
# l'audio viene chiesto a quei server (il primo che risponde) e inoltrato a chi ascolta.
ENGINE_URLS = [u.strip().rstrip('/') for u in os.environ.get('MELODIA_ENGINE_URLS', '').split(',') if u.strip()]

def _proxy_stream_from_engine(vid, fresh=''):
    for base in ENGINE_URLS:
        try:
            url = base + '/stream?id=' + urllib.parse.quote(vid) + ('&fresh=1' if fresh else '')
            h = {'User-Agent': 'melodia-front'}
            rng = request.headers.get('Range')
            if rng: h['Range'] = rng
            resp = urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=85)
            if resp.status not in (200, 206):
                resp.close(); continue
            hd = {k: resp.headers[k] for k in ('Content-Type', 'Content-Length', 'Content-Range', 'Accept-Ranges') if resp.headers.get(k)}
            def gen(resp=resp):
                try:
                    while True:
                        chunk = resp.read(65536)
                        if not chunk: break
                        yield chunk
                finally:
                    resp.close()
            return Response(gen(), status=resp.status, headers=hd)
        except Exception as e:
            print('motore audio non raggiungibile:', base, str(e)[:120])
    return None

@app.route('/prefetch')
def prefetch():
    """Avvia in background il download del prossimo brano della coda, così quando arriva il suo
    turno è già in cache e parte all'istante invece di far aspettare chi ascolta dal telefono."""
    if ENGINE_URLS:
        return jsonify({'status': 'skipped_engine_mode'})
    vid = request.args.get('id', '')
    if not vid:
        return jsonify({'error': 'Missing id'}), 400
    save_dir = os.path.join(ROOT_DIR, 'brani riprodotti')
    existing, _ = _find_cached(vid, save_dir)
    if existing or vid in _prefetching:
        return jsonify({'status': 'already_ready_or_in_progress'})
    _prefetching.add(vid)
    threading.Thread(target=_download_to_cache, args=(vid,), daemon=True).start()
    return jsonify({'status': 'started'})

# ══════════ HTML + STREAMING ══════════
# Carica l'interfaccia HTML locale
try:
    HTML = open(os.path.join(WWW_DIR,'spotify_moto.html'), encoding='utf-8').read()
except FileNotFoundError:
    HTML = "<h1>Errore: File 'spotify_moto.html' non trovato nella cartella del server.</h1>"

@app.route('/manifest.json')
def manifest():
    return jsonify({
        "id": "/",
        "name": "Melodia Premium",
        "short_name": "Melodia",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "background_color": "#000000",
        "theme_color": "#000000",
        "orientation": "portrait",
        "icons": [
            {"src": f"data:image/png;base64,{ICON_192}", "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": f"data:image/png;base64,{ICON_512}", "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {"src": f"data:image/png;base64,{ICON_192_M}", "sizes": "192x192", "type": "image/png", "purpose": "maskable"},
            {"src": f"data:image/png;base64,{ICON_512_M}", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}
        ]
    })

@app.route('/sw.js')
def service_worker():
    """Il Service Worker DEVE essere servito dalla radice del sito (non da una sottocartella)
    per poter controllare l'intera app: è uno dei requisiti tecnici che i browser controllano
    prima di offrire "Installa app" invece della semplice scheda del browser."""
    try:
        sw_code = open(os.path.join(WWW_DIR, 'sw.js'), encoding='utf-8').read()
    except FileNotFoundError:
        sw_code = "// sw.js mancante"
    resp = app.response_class(sw_code, mimetype='application/javascript')
    resp.headers['Service-Worker-Allowed'] = '/'
    return resp

@app.route('/')
@app.route('/spotify_moto.html')
@app.route('/s/<code>')
def index(code=None):
    resp = app.response_class(HTML, mimetype='text/html')
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp

def _parse_lrc(lrc_text):
    """Converte un testo in formato LRC (righe tipo [01:23.45]testo) in una lista ordinata
    di {time, text}, usata poi per evidenziare la riga giusta durante la riproduzione.
    Rispetta anche il tag opzionale [offset:+/-ms] presente in alcuni file LRC: serve a
    spostare tutti i tempi di quel valore, ed ignorarlo farebbe andare il testo fuori tempo."""
    lines = []
    offset_ms = 0
    m_off = re.search(r'\[offset:\s*([+-]?\d+)\s*\]', lrc_text, re.IGNORECASE)
    if m_off:
        try:
            offset_ms = int(m_off.group(1))
        except ValueError:
            offset_ms = 0
    pattern = re.compile(r'\[(\d{1,3}):(\d{2})(?:[.:](\d{1,3}))?\](.*)')
    for raw_line in lrc_text.splitlines():
        raw_line = raw_line.strip()
        # Una riga può avere più marcatori temporali (ritornelli ripetuti): [00:10.00][01:30.00]testo
        stamps = re.findall(r'\[(\d{1,3}):(\d{2})(?:[.:](\d{1,3}))?\]', raw_line)
        if not stamps:
            continue
        text = re.sub(r'\[[^\]]*\]', '', raw_line).strip()
        if not text:
            continue
        for mm, ss, ms in stamps:
            t = int(mm) * 60 + int(ss) + (int(ms.ljust(3, '0')[:3]) / 1000 if ms else 0)
            # offset positivo = il testo deve comparire prima, quindi si sottrae
            t = max(0.0, t - offset_ms / 1000.0)
            lines.append({'time': round(t, 3), 'text': text})
    lines.sort(key=lambda x: x['time'])
    return lines

LYRICS_CACHE_FILE = os.path.join(DATA_DIR, 'lyrics_cache.json')
# Un brano "non trovato" viene ritentato dopo questo tempo (prima il risultato negativo veniva
# salvato per sempre, quindi un brano non trovato una volta non veniva mai più cercato).
LYRICS_NOT_FOUND_RETRY_SECONDS = 6 * 3600

def _load_lyrics_cache():
    return safe_read_json(LYRICS_CACHE_FILE, {})

def _save_lyrics_cache(cache):
    try:
        safe_write_json(LYRICS_CACHE_FILE, cache)
    except Exception:
        pass

def _lyrics_cache_key(title, artist):
    return (title.strip().lower() + '|' + artist.strip().lower())

def _clean_lyrics_query(title, artist):
    """Ripulisce titolo e artista dai 'rumori' tipici di YouTube (Official Video, feat., Topic,
    VEVO...) che fanno fallire la ricerca dei testi anche quando il brano esiste davvero."""
    t = title or ''
    noise_words = r'(official|video|audio|lyrics?|lyric video|visuali[sz]er|hd|4k|remaster(ed)?|explicit|clean|m/?v|testo|con testo|live)'
    t = re.sub(r'[\(\[][^\)\]]*\b' + noise_words + r'\b[^\)\]]*[\)\]]', '', t, flags=re.IGNORECASE)
    t = re.sub(r'\s*[\(\[]?\s*(feat\.?|ft\.?|featuring|con)\s+[^\)\]]*[\)\]]?\s*$', '', t, flags=re.IGNORECASE)
    a = (artist or '').split(',')[0].strip()
    a = re.sub(r'\s*-\s*Topic$', '', a, flags=re.IGNORECASE)
    a = re.sub(r'\s*VEVO$', '', a, flags=re.IGNORECASE).strip()
    # Molti titoli YouTube sono nella forma "Artista - Titolo": se l'artista compare all'inizio
    # del titolo, lo si toglie (LRCLIB vuole il solo titolo del brano).
    if ' - ' in t:
        left, right = t.split(' - ', 1)
        if a and (a.lower() in left.lower() or left.lower() in a.lower()):
            t = right
        elif not a:
            a, t = left.strip(), right
    t = re.sub(r'\s+', ' ', t).strip(' -|')
    return (t or title), (a or artist)

def _http_json(url, headers, timeout=8):
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())

def _has_lyrics(d):
    return bool(d) and isinstance(d, dict) and bool(d.get('syncedLyrics') or d.get('plainLyrics'))

def _pick_best_by_duration(results, target_dur):
    """Tra i risultati di una ricerca sceglie quello con testo sincronizzato e la durata più
    vicina a quella del brano che stiamo riproducendo: versioni diverse dello stesso brano
    (radio edit, live, remix) hanno intro di lunghezza diversa, quindi prendere la durata
    giusta è ciò che tiene il testo a tempo."""
    candidates = [r for r in (results or []) if _has_lyrics(r)]
    if not candidates:
        return None
    def score(r):
        has_sync = 0 if r.get('syncedLyrics') else 1
        try:
            diff = abs(float(r.get('duration') or 0) - float(target_dur)) if target_dur else 0
        except (TypeError, ValueError):
            diff = 9999
        return (has_sync, diff)
    return sorted(candidates, key=score)[0]

def _lyrics_ovh_plain(artist, title, headers):
    """Ultima spiaggia: un secondo database pubblico (solo testo semplice, senza tempi) per i
    brani che LRCLIB non ha proprio. Meglio un testo non sincronizzato che nessun testo."""
    try:
        url = 'https://api.lyrics.ovh/v1/%s/%s' % (urllib.parse.quote(artist, safe=''), urllib.parse.quote(title, safe=''))
        d = _http_json(url, headers, timeout=8)
        txt = (d or {}).get('lyrics') or ''
        return txt.strip() or None
    except Exception:
        return None

@app.route('/api/lyrics')
def lyrics():
    """Cerca il testo reale del brano: prima su LRCLIB (testi sincronizzati), poi come ripiego
    su un secondo database di testi semplici. Non viene MAI inventato o generato un testo che
    non sia quello vero della canzone. I brani trovati vengono salvati in cache su disco; quelli
    non trovati vengono ritentati dopo qualche ora (un brano può comparire nel database dopo)."""
    title = request.args.get('title', '').strip()
    artist = (request.args.get('artist', '').strip().split(',')[0]).strip()
    duration = request.args.get('duration', '').strip()
    if not title:
        return jsonify({'error': 'Missing title'}), 400

    cache = _load_lyrics_cache()
    cache_key = _lyrics_cache_key(title, artist)
    cached = cache.get(cache_key)
    if cached:
        if cached.get('found'):
            return jsonify(cached)
        if time.time() - cached.get('ts', 0) < LYRICS_NOT_FOUND_RETRY_SECONDS:
            return jsonify(cached)

    headers = {'User-Agent': 'MelodiaPremium/1.0 (personal use app)'}
    try:
        target_dur = float(duration) if duration else 0
    except ValueError:
        target_dur = 0

    clean_title, clean_artist = _clean_lyrics_query(title, artist)
    # Varianti da provare, dalla più precisa alla più permissiva (senza duplicati)
    variants = []
    for v in [(clean_title, clean_artist), (title, artist), (clean_title, ''), (title.split(' - ')[-1].strip(), artist)]:
        if v[0] and v not in variants:
            variants.append(v)

    data = None
    matched_dur_diff = None
    try:
        # 1) Corrispondenza esatta con durata, poi senza durata, per ogni variante
        for (t, a) in variants:
            if not a:
                continue
            if duration:
                try:
                    d = _http_json('https://lrclib.net/api/get?' + urllib.parse.urlencode({'track_name': t, 'artist_name': a, 'duration': duration}), headers)
                    if _has_lyrics(d):
                        data = d
                        break
                except Exception:
                    pass
            try:
                d = _http_json('https://lrclib.net/api/get?' + urllib.parse.urlencode({'track_name': t, 'artist_name': a}), headers)
                if _has_lyrics(d):
                    data = d
                    break
            except Exception:
                pass

        # 2) Ricerca "fuzzy", scegliendo il risultato con la durata più vicina
        if not data:
            for (t, a) in variants:
                params = {'track_name': t}
                if a:
                    params['artist_name'] = a
                try:
                    results = _http_json('https://lrclib.net/api/search?' + urllib.parse.urlencode(params), headers)
                except Exception:
                    results = []
                best = _pick_best_by_duration(results, target_dur)
                if best:
                    data = best
                    break
            # ultimo tentativo: ricerca libera su testo unico "titolo artista"
            if not data:
                try:
                    results = _http_json('https://lrclib.net/api/search?' + urllib.parse.urlencode({'q': ('%s %s' % (clean_title, clean_artist)).strip()}), headers)
                    data = _pick_best_by_duration(results, target_dur)
                except Exception:
                    pass

        if data and target_dur and data.get('duration'):
            try:
                matched_dur_diff = round(abs(float(data['duration']) - target_dur), 1)
            except (TypeError, ValueError):
                matched_dur_diff = None

        if data:
            synced = _parse_lrc(data['syncedLyrics']) if data.get('syncedLyrics') else []
            result = {'found': True, 'synced': synced, 'plain': data.get('plainLyrics') or '', 'source': 'lrclib'}
            if matched_dur_diff is not None:
                result['durationDiff'] = matched_dur_diff
        else:
            # 3) Secondo database, solo testo semplice (senza tempi)
            plain = _lyrics_ovh_plain(clean_artist, clean_title, headers) if clean_artist else None
            if plain:
                result = {'found': True, 'synced': [], 'plain': plain, 'source': 'lyrics.ovh'}
            else:
                result = {'found': False, 'ts': time.time()}

        cache[cache_key] = result
        _save_lyrics_cache(cache)
        return jsonify(result)
    except Exception as ex:
        return jsonify({'found': False, 'error': str(ex)})

@app.route('/search')
def search():
    q = request.args.get('q', '')
    if not q: return jsonify([])

    def run_search(prefix):
        ydl_opts = {'quiet': True, 'no_warnings': True, 'extract_flat': True, 'default_search': prefix + '20', **_cookie_opts()}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"{prefix}20:{q}", download=False)
            results = []
            for e in (info.get('entries') or []):
                dur = e.get('duration', 0) or 0
                results.append({
                    'id': e.get('id', ''),
                    'title': e.get('title', ''),
                    'artist': e.get('uploader', ''),
                    'duration': f"{int(dur//60)}:{str(int(dur%60)).zfill(2)}" if dur else '',
                    'thumb': e.get('thumbnail', '') or f"https://i.ytimg.com/vi/{e.get('id', '')}/mqdefault.jpg",
                })
            return results

    def score_result(item):
        title = (item.get('title') or '').lower()
        artist = (item.get('artist') or '').lower()
        ql = q.lower()
        score = 0
        bad_terms = [
            'remix', 'sped up', 'slowed', 'slowed + reverb', 'slowed reverb',
            'nightcore', '8d', 'edit', 'reverb', 'bass boosted', 'speed up',
            'version', 'live', 'cover', 'karaoke', 'instrumental', 'acoustic',
            'extended mix', 'bootleg', 'mashup', 'fan made', 'fanmade'
        ]
        good_terms = ['official', 'official audio', 'topic', 'vevo', 'music']
        for term in bad_terms:
            if term in title:
                score -= 100
        for term in good_terms:
            if term in title or term in artist:
                score += 30
        if 'official audio' in title:
            score += 80
        if ' - topic' in artist or artist.endswith('topic'):
            score += 60
        dur = item.get('duration') or ''
        try:
            parts = dur.split(':')
            seconds = int(parts[-1]) + (int(parts[-2]) * 60 if len(parts) > 1 else 0)
            if 90 <= seconds <= 420:
                score += 15
            elif seconds < 60:
                score -= 20
            elif seconds > 900:
                score -= 30
        except Exception:
            pass
        # Prefer a close title match to avoid an unrelated video appearing first.
        compact_q = re.sub(r'[^a-z0-9 ]+', ' ', ql).strip()
        compact_t = re.sub(r'[^a-z0-9 ]+', ' ', title).strip()
        qwords = [w for w in compact_q.split() if len(w) > 1]
        if qwords:
            score += sum(12 for w in qwords if w in compact_t)
            if compact_q and compact_q in compact_t:
                score += 35
        return score

    try:
        results = run_search('ytmsearch')
        if not results:
            results = run_search('ytsearch')
        results.sort(key=score_result, reverse=True)
        return jsonify(results)
    except Exception:
        try:
            results = run_search('ytsearch')
            results.sort(key=score_result, reverse=True)
            return jsonify(results)
        except Exception as ex2:
            return jsonify({'error': str(ex2)}), 500

@app.route('/stream')
def stream():
    # IMPORTANTE: qui arriva esclusivamente l'ID YouTube del video scelto dalla ricerca.
    # Non usiamo più titolo/artista per cercare un altro video e non sostituiamo mai
    # automaticamente un video con remix, cover, slowed/sped-up o altri upload.
    vid = request.args.get('id', '').strip()
    fresh = request.args.get('fresh', '')
    if not vid: return 'Missing id', 400
    if not re.fullmatch(r'[A-Za-z0-9_-]{6,20}', vid): return 'Invalid YouTube id', 400
    if ENGINE_URLS:
        r = _proxy_stream_from_engine(vid, fresh)
        if r is not None: return r
        return 'Motore audio non disponibile', 503

    save_dir = os.path.join(ROOT_DIR, 'brani riprodotti')
    os.makedirs(save_dir, exist_ok=True)

    if fresh:
        old, _ = _find_cached(vid, save_dir)
        if old:
            try: os.remove(old)
            except Exception: pass
    else:
        existing, mime = _find_cached(vid, save_dir)
        if existing:
            return send_file(existing, mimetype=mime)

    out_template = os.path.join(save_dir, vid)
    with _foreground_slots:
        attempts = [
            {
                'quiet': True, 'no_warnings': True,
                'format': 'bestaudio[ext=m4a]/bestaudio[acodec^=mp4a]/bestaudio',
                'outtmpl': out_template + '.%(ext)s', 'noplaylist': True,
                **_cookie_opts()
            },
            {
                'quiet': True, 'no_warnings': True,
                'format': 'bestaudio[ext=m4a]/bestaudio/best',
                'outtmpl': out_template + '.%(ext)s', 'noplaylist': True,
                **_cookie_opts()
            },
        ]
        for i, opts in enumerate(attempts, 1):
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.download([f'https://www.youtube.com/watch?v={vid}'])
                existing, mime = _find_cached(vid, save_dir)
                if existing:
                    print(f'[OK] Stream esatto YouTube ID={vid}, tentativo {i}')
                    return send_file(existing, mimetype=mime)
            except Exception as e:
                print(f'[FALLITO] Stream esatto ID={vid}, tentativo {i}: {e}')

    return "Impossibile riprodurre il video YouTube richiesto senza sostituirlo con un'altra versione", 404

def _try_youtube_music(title, artist, out_template, preferredcodec='mp3', postprocessor_args=None):
    """Prova a trovare e scaricare lo stesso brano passando da YouTube Music invece che dal
    sito normale di YouTube — è la stessa piattaforma sotto, ma passa da un percorso tecnico
    leggermente diverso, quindi a volte il blocco anti-bot si comporta diversamente."""
    query = f"{title} {artist}".strip() if artist else title
    print(f"[TENTATIVO] YouTube Music per: {query}")
    pp = {'key': 'FFmpegExtractAudio', 'preferredcodec': preferredcodec}
    if preferredcodec == 'mp3':
        pp['preferredquality'] = '192'
    ydl_opts = {
        'quiet': True, 'no_warnings': True, 'format': 'bestaudio[ext=m4a]/bestaudio/best',
        'outtmpl': out_template + '.%(ext)s', 'noplaylist': True,
        'postprocessors': [pp],
        **_cookie_opts(),
    }
    if postprocessor_args:
        ydl_opts['postprocessor_args'] = postprocessor_args
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([f'ytmsearch1:{query}'])
        print(f"[OK] YouTube Music ha funzionato per: {query}")
        return True
    except Exception as e:
        print(f"[FALLITO] YouTube Music per '{query}': {e}")
        return False

def _try_alternate_platforms(title, artist, out_template, preferredcodec='mp3', postprocessor_args=None):
    """Cerca lo stesso brano su piattaforme diverse da YouTube (al momento SoundCloud) e lo
    scarica, salvandolo con lo stesso nome/ID già usato per YouTube — così tutto il resto del
    sistema (cache, prefetch, "salva offline", ecc.) continua a funzionare senza modifiche.
    Prova PIÙ varianti della ricerca (con e senza artista, ecc.) e PIÙ risultati in ordine di
    preferenza (prima quelli di durata "vera", poi anche quelli corti come ultima spiaggia),
    saltando quelli che falliscono (protetti, rotti, ecc.) invece di arrendersi al primo
    intoppo — la priorità è che qualcosa parta comunque."""
    primo_artista = artist.split(',')[0].strip() if artist else ''
    varianti_query = []
    if artist:
        varianti_query.append(f"{title} {artist}")
        if primo_artista and primo_artista != artist:
            varianti_query.append(f"{title} {primo_artista}")
    varianti_query.append(title)  # solo il titolo, come ultima variante

    print(f"[TENTATIVO] SoundCloud per: {title} / {artist} (varianti: {varianti_query})")
    search_opts = {'quiet': True, 'no_warnings': True, 'extract_flat': True}
    candidates = []
    visti = set()
    for q in varianti_query:
        try:
            with yt_dlp.YoutubeDL(search_opts) as ydl:
                info = ydl.extract_info(f'scsearch5:{q}', download=False)
                for c in (info.get('entries', []) if info else []):
                    if not c:
                        continue
                    url = c.get('url') or c.get('webpage_url')
                    if url and url not in visti:
                        visti.add(url)
                        candidates.append(c)
        except Exception as e:
            print(f"[FALLITO] Ricerca SoundCloud per '{q}': {e}")
            continue
    print(f"[INFO] SoundCloud ha trovato {len(candidates)} risultati totali per '{title}'")
    if not candidates:
        return False

    # Prova prima i brani di durata "vera" (60s+), poi come ultima spiaggia anche quelli
    # corti — meglio un'anteprima che niente, ma solo se non c'è davvero altro.
    lunghi = [c for c in candidates if (c.get('duration') or 0) >= 60]
    corti = [c for c in candidates if (c.get('duration') or 0) < 60]
    print(f"[INFO] Di cui {len(lunghi)} di durata piena e {len(corti)} brevi")
    ordine_tentativi = lunghi + corti

    ydl_opts = {
        'quiet': True, 'no_warnings': True, 'format': 'bestaudio[ext=m4a]/bestaudio/best',
        'outtmpl': out_template + '.%(ext)s', 'noplaylist': True,
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': preferredcodec, **({'preferredquality': '192'} if preferredcodec == 'mp3' else {})}],
    }
    if postprocessor_args:
        ydl_opts['postprocessor_args'] = postprocessor_args
    for i, c in enumerate(ordine_tentativi):
        url = c.get('url') or c.get('webpage_url')
        if not url:
            continue
        dur = c.get('duration') or 0
        print(f"[TENTATIVO] SoundCloud risultato {i+1}/{len(ordine_tentativi)} (durata {dur}s): {url}")
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            print(f"[OK] SoundCloud ha funzionato: {url}")
            return True  # trovato uno che funziona davvero, ci si ferma qui
        except Exception as e:
            print(f"[FALLITO] SoundCloud risultato '{url}': {e}")
            continue  # questo risultato non ha funzionato (es. protetto), prova il prossimo
    print(f"[INFO] Nessun risultato SoundCloud ha funzionato per: {title}")
    return False



# ══════════ SALVATAGGIO SU DISCO (cartella "canzoni scaricate") ══════════
# A differenza di /download (che rimanda il file al browser per farlo scaricare nella
# cartella Download di sistema), questo endpoint gira SOLO sul PC (dove sta girando questo
# stesso server.py) e scrive il file WAV direttamente dentro una cartella fissa creata
# ACCANTO a server.py (nella stessa cartella melodia_app in cui si trova già server.py,
# non in una nuova sottocartella con lo stesso nome) — niente doppia cartella "melodia_app".
CANZONI_SCARICATE_DIR = os.path.join(ROOT_DIR, 'canzoni scaricate')

def _clean_filename_part(s):
    """Toglie i caratteri non ammessi nei nomi file su Windows, lascia il resto (spazi,
    accenti, punteggiatura normale) così il nome resta leggibile e non diventa lettere a caso."""
    s = (s or '').strip()
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', s)
    s = re.sub(r'\s+', ' ', s).strip(' .')
    return s

def _unique_wav_path(directory, base_name):
    """Se un file con lo stesso nome esiste già, aggiunge (2), (3)... invece di sovrascriverlo."""
    candidate = os.path.join(directory, base_name + '.wav')
    if not os.path.exists(candidate):
        return candidate
    i = 2
    while True:
        candidate = os.path.join(directory, f"{base_name} ({i}).wav")
        if not os.path.exists(candidate):
            return candidate
        i += 1

@app.route('/api/save_wav_to_disk')
def save_wav_to_disk():
    vid = request.args.get('id', '')
    title = request.args.get('title', 'brano')
    artist = request.args.get('artist', '')
    if not vid:
        return jsonify({'ok': False, 'error': 'Missing id'}), 400

    try:
        os.makedirs(CANZONI_SCARICATE_DIR, exist_ok=True)
    except Exception as e:
        return jsonify({'ok': False, 'error': f'Impossibile creare la cartella: {e}'}), 500

    title_clean = _clean_filename_part(title) or 'Brano sconosciuto'
    artist_clean = _clean_filename_part(artist)
    base_name = f"{title_clean} - {artist_clean}" if artist_clean else title_clean
    # Windows limita i percorsi/nomi molto lunghi: teniamo il nome entro una lunghezza sicura.
    base_name = base_name[:150].strip(' -')

    # DUPLICATI: se il file "Titolo - Artista.wav" esiste già (perché scaricato prima, magari
    # da un'altra playlist), non lo riscarichiamo affatto — si salta subito, senza nemmeno
    # contattare YouTube. Così scaricando più playlist con brani in comune il lavoro non si
    # raddoppia mai.
    existing_path = os.path.join(CANZONI_SCARICATE_DIR, base_name + '.wav')
    if os.path.exists(existing_path):
        return jsonify({'ok': True, 'skipped': True, 'filename': os.path.basename(existing_path)})

    tmp = tempfile.mkdtemp()
    out = os.path.join(tmp, 'audio')
    WAV_PP_ARGS = {'FFmpegExtractAudio': ['-ar', '44100', '-ac', '2', '-acodec', 'pcm_s16le']}

    ydl_opts = {
        'quiet': True, 'no_warnings': True, 'format': 'bestaudio[ext=m4a]/bestaudio/best',
        'outtmpl': out + '.%(ext)s', 'noplaylist': True,
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'wav'}],
        # Forza esplicitamente 44.1 kHz, stereo, PCM a 16 bit (il codec 'wav' da solo non
        # garantisce questi parametri: dipende dalla sorgente originale se non specificato).
        'postprocessor_args': WAV_PP_ARGS,
        **_cookie_opts(),
    }

    wav_path = out + '.wav'
    riuscito = False
    ultimo_errore = None

    # TENTATIVO 1: YouTube diretto, con l'id già scelto dalla ricerca in app.
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([f'https://www.youtube.com/watch?v={vid}'])
        if os.path.exists(wav_path):
            riuscito = True
    except Exception as e:
        ultimo_errore = str(e)
        print(f"[FALLITO] Download WAV diretto per '{title}': {e}")

    # TENTATIVO 2: YouTube Music (stesso brano, percorso tecnico diverso — a volte l'anti-bot
    # si comporta diversamente e passa dove il tentativo diretto veniva bloccato).
    if not riuscito:
        if _try_youtube_music(title, artist, out, preferredcodec='wav', postprocessor_args=WAV_PP_ARGS):
            if os.path.exists(wav_path):
                riuscito = True

    # TENTATIVO 3: piattaforme alternative (SoundCloud) — ultima spiaggia se YouTube è del
    # tutto bloccato per questo brano.
    if not riuscito and title:
        if _try_alternate_platforms(title, artist, out, preferredcodec='wav', postprocessor_args=WAV_PP_ARGS):
            if os.path.exists(wav_path):
                riuscito = True

    if not riuscito:
        shutil.rmtree(tmp, ignore_errors=True)
        return jsonify({'ok': False, 'error': ultimo_errore or 'Impossibile scaricare questo brano da nessuna piattaforma disponibile'}), 500

    dest = _unique_wav_path(CANZONI_SCARICATE_DIR, base_name)
    shutil.move(wav_path, dest)
    shutil.rmtree(tmp, ignore_errors=True)
    return jsonify({'ok': True, 'filename': os.path.basename(dest), 'path': dest})


@app.route('/download')
def download():
    vid = request.args.get('id', '')
    title = request.args.get('title', 'brano')
    artist = request.args.get('artist', '')
    if not vid: return 'Missing id', 400
    
    safe = "".join(c for c in title if c.isalnum() or c in ' -_').strip()
    tmp = tempfile.mkdtemp()
    out = os.path.join(tmp, safe)
    
    ydl_opts = {
        'quiet': True, 'no_warnings': True, 'format': 'bestaudio[ext=m4a]/bestaudio/best',
        'outtmpl': out + '.%(ext)s', 'noplaylist': True,
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
        **_cookie_opts(),
    }
    
    file_to_send = None
    download_name = safe + '.mp3'
    mimetype = 'audio/mpeg'
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([f'https://www.youtube.com/watch?v={vid}'])
        mp3 = out + '.mp3'
        if os.path.exists(mp3):
            file_to_send = mp3
    except Exception:
        pass

    # Fallback senza ffmpeg
    if not file_to_send:
        try:
            ydl_opts2 = {'quiet': True, 'no_warnings': True, 'format': 'bestaudio[ext=m4a]/bestaudio/best', 'outtmpl': out + '.%(ext)s', 'noplaylist': True, **_cookie_opts()}
            with yt_dlp.YoutubeDL(ydl_opts2) as ydl:
                info = ydl.extract_info(f'https://www.youtube.com/watch?v={vid}', download=True)
                ext = info.get('ext', 'webm')
                f = out + '.' + ext
                if os.path.exists(f):
                    file_to_send = f
                    download_name = safe + '.' + ext
                    mimetype = f'audio/{ext}'
        except Exception:
            pass

    # Se YouTube è del tutto bloccato, prova lo stesso brano su un'altra piattaforma
    if not file_to_send and title:
        if _try_alternate_platforms(title, artist, out):
            mp3 = out + '.mp3'
            if os.path.exists(mp3):
                file_to_send = mp3

    if not file_to_send:
        shutil.rmtree(tmp, ignore_errors=True)
        return 'Impossibile scaricare questo brano da nessuna piattaforma disponibile', 500

    if file_to_send and os.path.exists(file_to_send):
        # Generatore per inviare il file e poi eliminare in sicurezza la cartella temporanea
        def generate():
            with open(file_to_send, 'rb') as f:
                yield from f
            shutil.rmtree(tmp, ignore_errors=True) # Rimuove tutto il contenuto temporaneo alla fine

        return app.response_class(
            generate(),
            mimetype=mimetype,
            headers={"Content-Disposition": f"attachment; filename={download_name}"}
        )
    
    shutil.rmtree(tmp, ignore_errors=True)
    return 'Errore imprevisto nel download', 500

@app.after_request
def cors(r):
    r.headers['Access-Control-Allow-Origin'] = '*'
    return r

if __name__ == '__main__':
    # Impostando 0.0.0.0 il server accetta sia le connessioni del PC stesso che quelle del telefono.
    # threaded=True è fondamentale: senza, il server (Werkzeug) gestisce UNA richiesta alla volta,
    # quindi mentre scarica/converte un brano su /stream tutto il resto resta bloccato in coda
    # (ricerca, sync, il prefetch del brano successivo...). Con threaded=True le richieste vengono
    # gestite in parallelo, il che rende la riproduzione molto più fluida.
    # Su un host cloud come Northflank la porta viene assegnata tramite la variabile
    # d'ambiente PORT; in locale su PC questa variabile non esiste, quindi si usa 5000
    # come sempre, senza alcun cambiamento per chi lo usa da casa.
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, threaded=True)