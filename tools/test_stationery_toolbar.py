import asyncio
import base64
import json
import os
import subprocess
import time
import urllib.request
import websockets

EDGE_EXE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
CHROME_EXE = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
BROWSER_EXE = EDGE_EXE if os.path.exists(EDGE_EXE) else CHROME_EXE
BASE_URL = "http://127.0.0.1:8000"

async def cdp_call(ws, req_id, method, params=None):
    payload = {"id": req_id, "method": method}
    if params:
        payload["params"] = params
    await ws.send(json.dumps(payload))
    while True:
        resp = await ws.recv()
        data = json.loads(resp)
        if data.get("id") == req_id:
            return data

async def evaluate(ws, req_id, expr, await_promise=False):
    res = await cdp_call(ws, req_id, "Runtime.evaluate", {
        "expression": expr,
        "returnByValue": True,
        "awaitPromise": await_promise
    })
    return res.get("result", {}).get("result", {}).get("value")

async def test_stationery():
    temp_dir = os.path.join(os.environ.get("TEMP", "C:\\temp"), f"ink_stat_{int(time.time())}")
    os.makedirs(temp_dir, exist_ok=True)

    print("\n" + "=" * 60)
    print("STARTING TEST FOR STATIONERY TOOLBAR & AUTO-MINIMIZATION")
    print("=" * 60)

    proc = subprocess.Popen([
        BROWSER_EXE,
        "--headless=new",
        "--remote-debugging-port=9232",
        f"--user-data-dir={temp_dir}",
        "--no-first-run",
        "--disable-gpu",
        "--window-size=1280,820",
        f"{BASE_URL}/"
    ])

    try:
        tab_ws = None
        for _ in range(30):
            await asyncio.sleep(0.3)
            try:
                with urllib.request.urlopen("http://127.0.0.1:9232/json", timeout=2) as r:
                    tabs = json.loads(r.read().decode())
                    for t in tabs:
                        if t.get("type") == "page":
                            tab_ws = t.get("webSocketDebuggerUrl")
                            break
                    if tab_ws:
                        break
            except Exception:
                pass

        if not tab_ws:
            print("ERROR: Could not connect to browser CDP")
            return False

        async with websockets.connect(tab_ws, max_size=50_000_000) as ws:
            req_id = 1
            await cdp_call(ws, req_id, "Page.enable"); req_id += 1
            await cdp_call(ws, req_id, "Runtime.enable"); req_id += 1
            await cdp_call(ws, req_id, "Page.navigate", {"url": f"{BASE_URL}/"}); req_id += 1

            for _ in range(50):
                await asyncio.sleep(0.2)
                ready = await evaluate(ws, req_id, "document.readyState === 'complete' && !!document.getElementById('notes')"); req_id += 1
                if ready is True:
                    break

            # Dismiss loader
            await evaluate(ws, req_id, """
            (function() {
                var ls = document.getElementById('loader-screen');
                if (ls) ls.remove();
                document.body.classList.remove('app-loading');
                var app = document.getElementById('app');
                if (app) {
                    app.style.opacity = '1';
                    app.style.filter = 'none';
                    app.style.transform = 'none';
                    app.style.pointerEvents = 'auto';
                }
            })()
            """); req_id += 1
            await asyncio.sleep(0.3)

            # 1. Verify Stationery Tools and Separated AI Actions
            print("\n1. Verifying Stationery Tools and Separated AI Actions Presence...")
            tools_info = await evaluate(ws, req_id, """
            (function() {
                var statTb = document.getElementById('tb-stationery');
                var aiActions = document.getElementById('ai-actions');

                var statToolIds = ['tool-pen', 'tool-fountain', 'tool-pencil', 'tool-highlighter', 'tool-ruler', 'tool-era'];
                var statToolsPresent = statToolIds.every(function(id) {
                    var el = document.getElementById(id);
                    return !!el && statTb.contains(el);
                });

                var aiToolIds = ['tool-circle', 'hint-btn', 'vo', 'solve'];
                var aiToolsPresent = aiToolIds.every(function(id) {
                    var el = document.getElementById(id);
                    return !!el && aiActions.contains(el);
                });

                // Verify circle, hint, solve are NOT inside the stationery toolbar
                var circleInStationery = statTb.contains(document.getElementById('tool-circle'));
                var hintInStationery = statTb.contains(document.getElementById('hint-btn'));
                var solveInStationery = statTb.contains(document.getElementById('solve'));

                return {
                    statToolsPresent: statToolsPresent,
                    aiToolsPresent: aiToolsPresent,
                    circleSeparated: !circleInStationery,
                    hintSeparated: !hintInStationery,
                    solveSeparated: !solveInStationery
                };
            })()
            """); req_id += 1
            print(f"   Architecture Check: {tools_info}")
            assert tools_info.get("statToolsPresent") is True, "Some stationery tools missing from #tb-stationery!"
            assert tools_info.get("aiToolsPresent") is True, "Some AI actions missing from #ai-actions!"
            assert tools_info.get("circleSeparated") is True, "tool-circle should NOT be in stationery toolbar!"
            assert tools_info.get("hintSeparated") is True, "hint-btn should NOT be in stationery toolbar!"
            assert tools_info.get("solveSeparated") is True, "solve should NOT be in stationery toolbar!"
            print("   -> PASS: Stationery and persistent AI Actions cleanly separated!")

            # 2. Test Tool Selection & Badge
            print("\n2. Testing Stationery Selection & Badge State...")
            badge_test = await evaluate(ws, req_id, """
            (function() {
                var fountainBtn = document.getElementById('tool-fountain');
                fountainBtn.click();
                var badgeFountain = document.getElementById('tb-badge-label').textContent;

                var pencilBtn = document.getElementById('tool-pencil');
                pencilBtn.click();
                var badgePencil = document.getElementById('tb-badge-label').textContent;

                return {
                    fountainWorked: badgeFountain.indexOf('Fountain') !== -1,
                    pencilWorked: badgePencil.indexOf('Pencil') !== -1,
                    badgeFountain: badgeFountain,
                    badgePencil: badgePencil,
                    toolVal: typeof tool !== 'undefined' ? tool : ''
                };
            })()
            """); req_id += 1
            print(f"   Badge Test: {badge_test}")
            assert badge_test.get("fountainWorked") is True, f"Fountain badge failed: {badge_test}"
            assert badge_test.get("pencilWorked") is True, f"Pencil badge failed: {badge_test}"
            print("   -> PASS: Tools switch and update badges cleanly!")

            # 3. Test Scale / Ruler Tool & Acrylic Widget
            print("\n3. Testing Scale / Ruler Tool & Acrylic Ruler Widget...")
            ruler_test = await evaluate(ws, req_id, """
            (function() {
                var rulerBtn = document.getElementById('tool-ruler');
                rulerBtn.click();
                var rulerWidget = document.getElementById('acrylic-ruler');
                var isVisible = rulerWidget && rulerWidget.style.display !== 'none';
                return {
                    tool: typeof tool !== 'undefined' ? tool : '',
                    rulerVisible: isVisible
                };
            })()
            """); req_id += 1
            print(f"   Ruler Test: {ruler_test}")
            assert ruler_test.get("tool") == "ruler", f"Expected tool=ruler, got {ruler_test.get('tool')}"
            assert ruler_test.get("rulerVisible") is True, "Acrylic ruler widget is not visible!"
            print("   -> PASS: Scale / Ruler activates and displays physical acrylic scale!")

            # 4. Test Auto-Minimizing Toolbar during Writing & Persistent AI Actions
            print("\n4. Testing Smooth Auto-Minimizing Stationery & Persistent AI Actions...")
            min_test = await evaluate(ws, req_id, """
            (function() {
                var cv = document.getElementById('cv');
                var statTb = document.getElementById('tb-stationery');
                var aiActions = document.getElementById('ai-actions');
                var wasMinimizedBefore = statTb.classList.contains('minimized');

                // Check CSS transition properties on stationery tray
                var tbStyle = window.getComputedStyle(statTb);
                var hasSmoothTransition = tbStyle.transition.indexOf('max-width') !== -1;

                // Simulate pointerdown on canvas to write
                var rect = cv.getBoundingClientRect();
                var downEv = new PointerEvent('pointerdown', {
                    clientX: rect.left + 200,
                    clientY: rect.top + 200,
                    pointerId: 1,
                    pointerType: 'pen',
                    pressure: 0.6,
                    bubbles: true,
                    cancelable: true
                });
                cv.dispatchEvent(downEv);

                var isStatMinimized = statTb.classList.contains('minimized');
                var isAiMinimized = aiActions.classList.contains('minimized');

                // Verify AI actions remain 100% visible and enabled
                var circleVisible = window.getComputedStyle(document.getElementById('tool-circle')).display !== 'none';
                var hintVisible = window.getComputedStyle(document.getElementById('hint-btn')).display !== 'none';
                var solveVisible = window.getComputedStyle(document.getElementById('solve')).display !== 'none';

                // Restore toolbar
                restoreStationeryToolbar();
                var isRestored = !statTb.classList.contains('minimized');

                return {
                    wasMinimizedBefore: wasMinimizedBefore,
                    isStatMinimized: isStatMinimized,
                    isAiMinimized: isAiMinimized,
                    circleVisible: circleVisible,
                    hintVisible: hintVisible,
                    solveVisible: solveVisible,
                    hasSmoothTransition: hasSmoothTransition,
                    isRestored: isRestored
                };
            })()
            """); req_id += 1
            print(f"   Auto-Minimize & Persistence Test: {min_test}")
            assert min_test.get("isStatMinimized") is True, "Stationery toolbar did not minimize on pointerdown!"
            assert min_test.get("isAiMinimized") is False, "AI Actions must NOT minimize!"
            assert min_test.get("circleVisible") is True, "tool-circle must remain visible!"
            assert min_test.get("hintVisible") is True, "hint-btn must remain visible!"
            assert min_test.get("solveVisible") is True, "solve must remain visible!"
            assert min_test.get("hasSmoothTransition") is True, "Stationery toolbar lacks max-width transition!"
            assert min_test.get("isRestored") is True, "Stationery toolbar failed to restore!"
            print("   -> PASS: Stationery toolbar smoothly minimizes while AI Actions (Circle, Hint, Solve) stay permanently visible!")

            # 5. Capture Screenshots
            print("\n5. Capturing Screenshots...")
            # Switch back to fountain pen for screenshot
            await evaluate(ws, req_id, "setTool('fountain');"); req_id += 1
            await asyncio.sleep(0.4)

            # Capture Full Toolbar
            ss1 = await cdp_call(ws, req_id, "Page.captureScreenshot"); req_id += 1
            img1 = ss1.get("result", {}).get("data")
            if img1:
                with open("stationery_full_toolbar.png", "wb") as f:
                    f.write(base64.b64decode(img1))
                print("   -> Saved stationery_full_toolbar.png!")

            # Minimize toolbar and capture full notebook view
            await evaluate(ws, req_id, "minimizeStationeryToolbar();"); req_id += 1
            await asyncio.sleep(0.5)
            ss2 = await cdp_call(ws, req_id, "Page.captureScreenshot"); req_id += 1
            img2 = ss2.get("result", {}).get("data")
            if img2:
                with open("stationery_minimized_notebook.png", "wb") as f:
                    f.write(base64.b64decode(img2))
                print("   -> Saved stationery_minimized_notebook.png!")

            # Restore toolbar back
            await evaluate(ws, req_id, "restoreStationeryToolbar();"); req_id += 1

            print("\n" + "=" * 60)
            print("ALL STATIONERY TOOLBAR & PERSISTENT AI ACTION TESTS PASSED!")
            print("=" * 60)
            return True

    finally:
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except Exception:
            pass

if __name__ == "__main__":
    success = asyncio.run(test_stationery())
    exit(0 if success else 1)
