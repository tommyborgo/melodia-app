import re,sys
src=open('/home/claude/hf/out_pot/server.py',encoding='utf-8').read()
def rep(old,new,count=1):
    global src
    n=src.count(old)
    assert n>=1 and (count==0 or n==count),(old,n)
    src=src.replace(old,new)
rep("import pot_ep; pot_ep.init(app, request, jsonify)","import android_glue; android_glue.init(app, request, jsonify, Response)")
rep("BASE_DIR = os.path.dirname(os.path.abspath(__file__))\n","BASE_DIR = os.path.dirname(os.path.abspath(__file__))\nROOT_DIR = os.environ.get('MELODIA_ROOT') or BASE_DIR\nWWW_DIR = os.environ.get('MELODIA_WWW') or BASE_DIR\n")
rep("open('spotify_moto.html', encoding='utf-8')","open(os.path.join(WWW_DIR,'spotify_moto.html'), encoding='utf-8')")
rep("open(os.path.join(BASE_DIR, 'sw.js'), encoding='utf-8')","open(os.path.join(WWW_DIR, 'sw.js'), encoding='utf-8')")
rep("os.path.join(os.path.dirname(os.path.abspath(__file__)), 'canzoni_salvate_v2')","os.path.join(ROOT_DIR, 'brani riprodotti')")
rep("os.path.join(os.path.dirname(os.path.abspath(__file__)), 'canzoni_salvate')","os.path.join(ROOT_DIR, 'brani riprodotti')",2)
rep("os.path.join(os.path.dirname(os.path.abspath(__file__)), 'canzoni scaricate')","os.path.join(ROOT_DIR, 'canzoni scaricate')")
rep("    if not os.path.exists(COOKIES_FILE):\n        return {}","    if not os.path.exists(COOKIES_FILE):\n        return {'extractor_args': {'youtube': {'player_client': ['android_vr', 'default']}}}")
rep("'format': 'bestaudio/best'","'format': 'bestaudio[ext=m4a]/bestaudio/best'",0)
open('app/src/main/python/server.py','w',encoding='utf-8').write(src)
h=open('/home/claude/hf/space/spotify_moto.html',encoding='utf-8').read()
old="  }\n},500);\n// Il telefono verifica"
assert h.count(old)==1
h=h.replace(old,"  }\n},2500);\n// Il telefono verifica")
open('app/src/main/assets/spotify_moto.html','w',encoding='utf-8').write(h)
import shutil; shutil.copy('/home/claude/hf/space/sw.js','app/src/main/assets/sw.js')
print('ok',len(src))
