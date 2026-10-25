import asyncio
import json
import urllib.request
import websockets
import subprocess
import time
import base64

async def check():
    proc = subprocess.Popen([
        r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
        '--headless=new',
        '--remote-debugging-port=9233',
        '--disable-gpu',
        '--window-size=1200,800',
        'http://127.0.0.1:8000/'
    ])
    try:
        time.sleep(2.0)
        with urllib.request.urlopen('http://127.0.0.1:9233/json') as r:
            tabs = json.loads(r.read().decode())
            ws_url = [t['webSocketDebuggerUrl'] for t in tabs if t.get('type') == 'page'][0]
        async with websockets.connect(ws_url) as ws:
            async def call(method, params=None):
                mid = int(time.time() * 1000) % 1000000 + 1
                await ws.send(json.dumps({'id': mid, 'method': method, 'params': params or {}}))
                while True:
                    m = json.loads(await ws.recv())
                    if m.get('id') == mid:
                        return m.get('result')

            await call('DOM.enable')
            await call('CSS.enable')
            await call('Page.enable')
            await call('Runtime.enable')
            await asyncio.sleep(1.0)
            
            res = await call('Runtime.evaluate', {
                'expression': 'JSON.stringify({ check: document.fonts.check("46px Caveat"), fam: window.AI_FONT })',
                'returnByValue': True
            })
            print('FONT CHECK:', res['result']['value'])
            
            doc = await call('DOM.getDocument')
            node = await call('DOM.querySelector', {'nodeId': doc['root']['nodeId'], 'selector': '.ai-reenie-line'})
            pf = await call('CSS.getPlatformFontsForNode', {'nodeId': node['nodeId']})
            print('PLATFORM FONTS:', json.dumps(pf['fonts'], indent=2))
            
            ss = await call('Page.captureScreenshot', {'format': 'png'})
            with open('tools/caveat_render_live.png', 'wb') as f:
                f.write(base64.b64decode(ss['data']))
            print('SCREENSHOT SAVED to tools/caveat_render_live.png')
    finally:
        proc.kill()

if __name__ == '__main__':
    asyncio.run(check())
