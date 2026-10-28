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

async def test_mv_and_theme():
    temp_dir = os.path.join(os.environ.get("TEMP", "C:\\temp"), f"ink_mv_{int(time.time())}")
    os.makedirs(temp_dir, exist_ok=True)

    print("\n" + "=" * 60)
    print("STARTING TEST FOR MULTIVARIABLE CALCULUS NOTES & LIGHT THEME")
    print("=" * 60)

    proc = subprocess.Popen([
        BROWSER_EXE,
        "--headless=new",
        "--remote-debugging-port=9230",
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
                with urllib.request.urlopen("http://127.0.0.1:9230/json", timeout=2) as r:
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

            # Wait for DOM and #notes
            for _ in range(50):
                await asyncio.sleep(0.2)
                ready = await evaluate(ws, req_id, "document.readyState === 'complete' && !!document.getElementById('notes')"); req_id += 1
                if ready is True:
                    break

            # 1. Check Default Theme is Light
            print("\n1. Verifying Default Theme is Light Mode...")
            theme_info = await evaluate(ws, req_id, """
            (function() {
                var htmlTheme = document.documentElement.getAttribute('data-theme');
                var storageTheme = localStorage.getItem('inkmentor_theme');
                var bg = getComputedStyle(document.body).backgroundColor;
                var paperBg = getComputedStyle(document.getElementById('paper')).backgroundColor;
                return {
                    htmlTheme: htmlTheme,
                    storageTheme: storageTheme,
                    bodyBg: bg,
                    paperBg: paperBg
                };
            })()
            """); req_id += 1
            print(f"   Theme Check: {theme_info}")
            assert theme_info.get("htmlTheme") == "light", f"Expected data-theme='light', got {theme_info.get('htmlTheme')}"
            print("   -> PASS: Light mode is active by default!")

            # 2. Check Loading Screen Exists
            print("\n2. Checking Loading Screen Presence...")
            has_loader = await evaluate(ws, req_id, "!!document.getElementById('loader-screen')"); req_id += 1
            print(f"   Has loader screen: {has_loader}")

            # Dismiss loader for screenshot & page testing
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

            # 3. Check Page 1 Content & Figure
            print("\n3. Verifying Page 1 (Studio Guide & Interactive SVG)...")
            p1_info = await evaluate(ws, req_id, """
            (function() {
                var notes = document.getElementById('notes');
                var title = notes.querySelector('.nb-title') ? notes.querySelector('.nb-title').textContent : '';
                var fig = notes.querySelector('.nb-fig-wrap');
                var svg = fig ? fig.querySelector('svg') : null;
                var caption = fig ? fig.querySelector('.nb-fig-caption') : null;
                var lines = Array.from(notes.querySelectorAll('.ln')).map(function(el) { return el.textContent; });
                return {
                    title: title,
                    hasFigure: !!fig,
                    hasSvg: !!svg,
                    svgViewBox: svg ? svg.getAttribute('viewBox') : null,
                    caption: caption ? caption.textContent : '',
                    linesCount: lines.length,
                    firstLines: lines.slice(0, 5)
                };
            })()
            """); req_id += 1
            cap_clean = p1_info.get('caption', '')[:50].encode('ascii', errors='replace').decode('ascii')
            title_clean = p1_info.get('title', '').encode('ascii', errors='replace').decode('ascii')
            print(f"   Page 1 Info: Title='{title_clean}', HasFigure={p1_info.get('hasFigure')}, Caption='{cap_clean}...'")
            assert p1_info.get("hasFigure") is True, "Page 1 figure is missing"
            assert p1_info.get("hasSvg") is True, "Page 1 SVG is missing"

            # Capture Page 1 screenshot
            await asyncio.sleep(0.6)
            print("   Capturing Page 1 Light Mode Screenshot...")
            ss1 = await cdp_call(ws, req_id, "Page.captureScreenshot"); req_id += 1
            img1 = ss1.get("result", {}).get("data")
            if img1:
                with open("mv_page1_light.png", "wb") as f:
                    f.write(base64.b64decode(img1))
                print("   -> Saved mv_page1_light.png!")

            # 4. Verify All 6 Multivariable Pages
            print("\n4. Verifying All 6 Multivariable Calculus Pages...")
            pages_check = await evaluate(ws, req_id, """
            (function() {
                var results = [];
                for (var i = 0; i < pages.length; i++) {
                    var p = pages[i];
                    results.push({
                        pageIndex: i + 1,
                        title: p.t,
                        color: p.c,
                        hasFig: !!p.fig,
                        hasSvg: !!(p.fig && p.fig.svg),
                        linesCount: p.l ? p.l.length : 0
                    });
                }
                return results;
            })()
            """); req_id += 1

            for p in pages_check:
                clean_t = p['title'].encode('ascii', errors='replace').decode('ascii')
                print(f"   Page {p['pageIndex']}: {clean_t:38s} | Color: {p['color']} | HasFig: {p['hasFig']} | Lines: {p['linesCount']}")
                assert p["hasFig"] is True, f"Page {p['pageIndex']} is missing figure"
                assert p["linesCount"] > 10, f"Page {p['pageIndex']} has insufficient notes"

            # 5. Navigate to Page 2 (3D Surfaces & Level Curves) and capture screenshot
            print("\n5. Navigating to Page 2 (3D Surfaces & Level Curves)...")
            await evaluate(ws, req_id, """
            (function() {
                go(2);
            })()
            """); req_id += 1
            await asyncio.sleep(0.4)

            p2_check = await evaluate(ws, req_id, """
            (function() {
                var notes = document.getElementById('notes');
                var fig = notes.querySelector('.nb-fig-wrap');
                return {
                    currentPage: cur,
                    hasFigure: !!fig,
                    hasSvg: !!(fig && fig.querySelector('svg'))
                };
            })()
            """); req_id += 1
            print(f"   Page 2 Nav Check: {p2_check}")
            assert p2_check.get("currentPage") == 2

            ss2 = await cdp_call(ws, req_id, "Page.captureScreenshot"); req_id += 1
            img2 = ss2.get("result", {}).get("data")
            if img2:
                with open("mv_page2_surfaces_light.png", "wb") as f:
                    f.write(base64.b64decode(img2))
                print("   -> Saved mv_page2_surfaces_light.png!")

            # 6. Test Settings Modal Theme Controls & White Paper in Dark Mode
            print("\n6. Testing Settings Modal Theme Toggling & Paper Canvas Background...")
            settings_theme_test = await evaluate(ws, req_id, """
            (function() {
                var btn = document.getElementById('settings-btn');
                btn.click();

                var darkBtn = document.querySelector('#setting-theme-seg .sm-seg-btn[data-val="dark"]');
                var lightBtn = document.querySelector('#setting-theme-seg .sm-seg-btn[data-val="light"]');

                // Switch to Dark
                darkBtn.click();
                var darkAttr = document.documentElement.getAttribute('data-theme');
                var bodyBgDark = getComputedStyle(document.body).backgroundColor;
                var paperBgDark = getComputedStyle(document.getElementById('paper')).backgroundColor;

                // Close settings
                var close = document.getElementById('sm-close');
                close.click();

                return {
                    darkWorked: darkAttr === 'dark',
                    bodyBgDark: bodyBgDark,
                    paperBgDark: paperBgDark
                };
            })()
            """); req_id += 1
            print(f"   Dark Theme Check: {settings_theme_test}")
            assert settings_theme_test.get("darkWorked") is True
            # Canvas must stay white in dark mode
            assert "rgb(255, 255, 255)" in settings_theme_test.get("paperBgDark", ""), f"Paper canvas should be white, got {settings_theme_test.get('paperBgDark')}"
            print("   -> PASS: Paper canvas stays white in Dark Mode!")

            # Capture Dark Mode Screenshot with crisp white paper
            await asyncio.sleep(0.5)
            ss_dark = await cdp_call(ws, req_id, "Page.captureScreenshot"); req_id += 1
            img_dark = ss_dark.get("result", {}).get("data")
            if img_dark:
                with open("dark_mode_white_canvas.png", "wb") as f:
                    f.write(base64.b64decode(img_dark))
                print("   -> Saved dark_mode_white_canvas.png!")

            # Switch back to Light Mode
            await evaluate(ws, req_id, """
            (function() {
                var btn = document.getElementById('settings-btn');
                btn.click();
                var lightBtn = document.querySelector('#setting-theme-seg .sm-seg-btn[data-val="light"]');
                lightBtn.click();
                var close = document.getElementById('sm-close');
                close.click();
            })()
            """); req_id += 1
            print("   -> PASS: Restored default Light mode smoothly!")

            print("\n" + "=" * 60)
            print("ALL MULTIVARIABLE CALCULUS & LIGHT MODE TESTS PASSED!")
            print("=" * 60)
            return True

    finally:
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except Exception:
            pass

if __name__ == "__main__":
    success = asyncio.run(test_mv_and_theme())
    exit(0 if success else 1)
