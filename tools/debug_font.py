import asyncio
import json
import urllib.request
import websockets
import subprocess
import time

async def check():
    proc = subprocess.Popen([
        r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
        '--headless=new',
        '--remote-debugging-port=9225',
        '--disable-gpu',
        'http://127.0.0.1:8000/'
    ])
    try:
        time.sleep(1.5)
        with urllib.request.urlopen('http://127.0.0.1:9225/json') as r:
            tabs = json.loads(r.read().decode())
            ws_url = [t['webSocketDebuggerUrl'] for t in tabs if t.get('type') == 'page'][0]
        async with websockets.connect(ws_url) as ws:
            await ws.send(json.dumps({'id': 1, 'method': 'Runtime.enable'}))
            await asyncio.sleep(0.5)
            expr = """
            (function() {
                var notes = document.getElementById('notes');
                var cs = window.getComputedStyle(notes);
                var reenie = document.querySelector('.ai-reenie-line');
                var rcs = reenie ? window.getComputedStyle(reenie) : null;
                var fontFaces = [];
                document.fonts.forEach(function(f) {
                    fontFaces.push({family: f.family, status: f.status, loaded: f.loaded});
                });
                return {
                    notesFontFamily: cs.fontFamily,
                    notesFontSize: cs.fontSize,
                    notesLineHeight: cs.lineHeight,
                    reenieFontFamily: rcs ? rcs.fontFamily : null,
                    fontCheckCaveat: document.fonts.check('46px Caveat'),
                    fontFaces: fontFaces,
                    pageCur: window.cur,
                    aiOutput: window.pageAiOutput[window.cur]
                };
            })()
            """
            await ws.send(json.dumps({
                'id': 2,
                'method': 'Runtime.evaluate',
                'params': {'expression': expr, 'returnByValue': True}
            }))
            while True:
                msg = json.loads(await ws.recv())
                if msg.get('id') == 2:
                    print('CHECK RESULT:', json.dumps(msg['result']['result']['value'], indent=2))
                    break
    finally:
        proc.kill()

if __name__ == '__main__':
    asyncio.run(check())
