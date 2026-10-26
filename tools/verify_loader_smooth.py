import asyncio
import json
import urllib.request
import websockets
import subprocess
import time
import base64
import os

async def verify_loader():
    out_dir = 'tools/out_loader'
    os.makedirs(out_dir, exist_ok=True)
    
    port = 9244
    proc = subprocess.Popen([
        r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
        '--headless=new',
        f'--remote-debugging-port={port}',
        '--disable-gpu',
        '--window-size=1200,800',
        'http://127.0.0.1:8000/'
    ])
    try:
        time.sleep(1.2)
        with urllib.request.urlopen(f'http://127.0.0.1:{port}/json') as r:
            tabs = json.loads(r.read().decode())
            ws_url = [t['webSocketDebuggerUrl'] for t in tabs if t.get('type') == 'page'][0]
            
        async with websockets.connect(ws_url) as ws:
            mid = 1
            async def call(method, params=None):
                nonlocal mid
                mid += 1
                cur_id = mid
                await ws.send(json.dumps({'id': cur_id, 'method': method, 'params': params or {}}))
                while True:
                    m = json.loads(await ws.recv())
                    if m.get('id') == cur_id:
                        return m.get('result')

            await call('Page.enable')
            await call('Runtime.enable')
            
            # Check loader state at intervals
            points = []
            start = time.time()
            
            timestamps_to_snap = [1.5, 3.5, 4.4, 5.2, 6.2, 7.6]
            next_snap_idx = 0
            
            while time.time() - start < 8.0:
                elapsed = time.time() - start
                
                # Sample mover coordinates and classes
                res = await call('Runtime.evaluate', {
                    'expression': '''(function() {
                        var l = document.getElementById('loader-screen');
                        var m = document.getElementById('loader-nib-mover');
                        var b = document.getElementById('loader-bar-fill');
                        var app = document.getElementById('app');
                        return {
                            hasLoader: !!l,
                            isUnveiling: l ? l.classList.contains('unveil') : false,
                            bodyLoading: document.body.classList.contains('app-loading'),
                            moverTransform: m ? m.getAttribute('transform') : null,
                            barWidth: b ? b.style.width : null,
                            appFilter: app ? getComputedStyle(app).filter : null,
                            appOpacity: app ? getComputedStyle(app).opacity : null
                        };
                    })()''',
                    'returnByValue': True
                })
                val = res['result']['value']
                points.append((round(elapsed, 2), val))
                
                if next_snap_idx < len(timestamps_to_snap) and elapsed >= timestamps_to_snap[next_snap_idx]:
                    snap_t = timestamps_to_snap[next_snap_idx]
                    ss = await call('Page.captureScreenshot', {'format': 'png'})
                    filename = f'{out_dir}/snap_{snap_t}s.png'
                    with open(filename, 'wb') as f:
                        f.write(base64.b64decode(ss['data']))
                    print(f'Captured screenshot at T={snap_t}s -> {filename}')
                    next_snap_idx += 1
                
                await asyncio.sleep(0.1)

            # Summarize observations
            print('\n=== SAMPLES SUMMARY ===')
            for t, v in points[::4]:
                print(f'T={t:4.1f}s | unveil={v["isUnveiling"]} | bodyLoading={v["bodyLoading"]} | bar={v["barWidth"]} | mover={v["moverTransform"]} | appFilter={v["appFilter"]}')
            
            # Validation assertions
            unveil_times = [t for t, v in points if v['isUnveiling']]
            assert len(unveil_times) > 0, "Loader never unveiled!"
            first_unveil = unveil_times[0]
            print(f'\nFirst unveil detected at T={first_unveil}s (Target: ~5.5s)')
            assert 5.0 <= first_unveil <= 6.0, f"Unveil timing {first_unveil}s outside 5.0-6.0s target window!"
            
            end_state = points[-1][1]
            print('Final state at T=8s:', end_state)
            assert not end_state['hasLoader'] or end_state['isUnveiling'], "Loader should be dismissed or removed!"
            print('\nALL VERIFICATION CHECKS PASSED!')
    finally:
        proc.kill()

if __name__ == '__main__':
    asyncio.run(verify_loader())
