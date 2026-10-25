import asyncio
import base64
import json
import os
import struct
import subprocess
import time
import urllib.request
import websockets
import zlib

PORT = 9245
SERVER_URL = "http://127.0.0.1:8000/"
BROWSER_EXE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
FRAMES_DIR = os.path.join(OUT_DIR, "frames")
os.makedirs(FRAMES_DIR, exist_ok=True)

def decode_png(png_bytes):
    if png_bytes[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("Invalid PNG signature")
    idx = 8
    width = height = None
    color_type = None
    idat_chunks = []
    while idx < len(png_bytes):
        length = struct.unpack(">I", png_bytes[idx:idx+4])[0]
        ctype = png_bytes[idx+4:idx+8]
        data = png_bytes[idx+8:idx+8+length]
        idx += 12 + length
        if ctype == b"IHDR":
            width, height, bit_depth, color_type, _, _, _ = struct.unpack(">IIBBBBB", data[:13])
        elif ctype == b"IDAT":
            idat_chunks.append(data)
        elif ctype == b"IEND":
            break

    raw = zlib.decompress(b"".join(idat_chunks))
    bpp = 4 if color_type == 6 else (3 if color_type == 2 else 1)
    stride = width * bpp
    pixels = bytearray(width * height * 4)

    prev_row = bytearray(stride)
    raw_idx = 0
    out_idx = 0

    for r in range(height):
        filter_type = raw[raw_idx]
        raw_idx += 1
        curr_row = bytearray(raw[raw_idx:raw_idx+stride])
        raw_idx += stride

        if filter_type == 0:
            pass
        elif filter_type == 1:
            for c in range(bpp, stride):
                curr_row[c] = (curr_row[c] + curr_row[c - bpp]) & 0xFF
        elif filter_type == 2:
            for c in range(stride):
                curr_row[c] = (curr_row[c] + prev_row[c]) & 0xFF
        elif filter_type == 3:
            for c in range(stride):
                left = curr_row[c - bpp] if c >= bpp else 0
                curr_row[c] = (curr_row[c] + ((left + prev_row[c]) >> 1)) & 0xFF
        elif filter_type == 4:
            for c in range(stride):
                a = curr_row[c - bpp] if c >= bpp else 0
                b = prev_row[c]
                c_val = prev_row[c - bpp] if c >= bpp else 0
                p = a + b - c_val
                pa = abs(p - a)
                pb = abs(p - b)
                pc = abs(p - c_val)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c_val)
                curr_row[c] = (curr_row[c] + pr) & 0xFF

        prev_row = curr_row

        if bpp == 4:
            pixels[out_idx:out_idx+stride] = curr_row
            out_idx += stride
        elif bpp == 3:
            for x in range(width):
                pixels[out_idx] = curr_row[x*3]
                pixels[out_idx+1] = curr_row[x*3+1]
                pixels[out_idx+2] = curr_row[x*3+2]
                pixels[out_idx+3] = 255
                out_idx += 4

    return width, height, pixels

def count_ink_pixels(width, height, pixels, rect, exclude_rect=None):
    # rect: (rx, ry, rw, rh)
    rx, ry, rw, rh = [int(v) for v in rect]
    rx = max(0, min(width - 1, rx))
    ry = max(0, min(height - 1, ry))
    rw = max(1, min(width - rx, rw))
    rh = max(1, min(height - ry, rh))

    ex_x0 = ex_y0 = ex_x1 = ex_y1 = -1
    if exclude_rect and len(exclude_rect) >= 4 and exclude_rect[2] > 0 and exclude_rect[3] > 0:
        ex_x0 = int(exclude_rect[0])
        ex_y0 = int(exclude_rect[1])
        ex_x1 = ex_x0 + int(exclude_rect[2])
        ex_y1 = ex_y0 + int(exclude_rect[3])

    count = 0
    for y in range(ry, ry + rh):
        row_offset = y * width * 4
        for x in range(rx, rx + rw):
            if ex_x0 != -1 and (ex_x0 <= x <= ex_x1 and ex_y0 <= y <= ex_y1):
                continue
            idx = row_offset + x * 4
            r = pixels[idx]
            g = pixels[idx + 1]
            b = pixels[idx + 2]
            # Amber to coral ink: Red is strong, R >= 190 and R - B >= 35
            # Non-background: background is ~(242, 242, 247) where R - B = -5
            if r >= 190 and (r - b) >= 35:
                count += 1
    return count

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
    if "error" in res:
        print("EVAL ERROR:", res["error"])
        return None
    res_val = res.get("result", {})
    if "exceptionDetails" in res_val:
        print("EXCEPTION DETAILS:", res_val["exceptionDetails"])
        return None
    return res_val.get("result", {}).get("value")

def generate_video_player(frame_files, output_html_path):
    # Generates a self-contained HTML5 video player for the captured screencast frames
    frames_json = json.dumps([os.path.basename(f) for f in frame_files])
    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>InkMentor Writing Animation Screencast</title>
<style>
body {{ font-family: -apple-system, sans-serif; background: #111; color: #eee; margin: 0; padding: 20px; display: flex; flex-direction: column; align-items: center; }}
#player-container {{ background: #000; border-radius: 8px; overflow: hidden; box-shadow: 0 8px 32px rgba(0,0,0,0.5); }}
#screen {{ display: block; max-width: 900px; height: auto; }}
#controls {{ margin-top: 15px; display: flex; align-items: center; gap: 12px; width: 900px; }}
button {{ padding: 8px 16px; background: #6b4ef0; color: #fff; border: none; border-radius: 4px; cursor: pointer; font-weight: 600; }}
button:hover {{ background: #573bd8; }}
input[type=range] {{ flex: 1; }}
#status {{ font-variant-numeric: tabular-nums; }}
</style>
</head>
<body>
<h2>InkMentor Live Solve Screencast Video</h2>
<div id="player-container">
  <img id="screen" src="frames/{os.path.basename(frame_files[0]) if frame_files else ''}">
</div>
<div id="controls">
  <button id="play-btn">Play</button>
  <input type="range" id="scrubber" min="0" max="{max(0, len(frame_files)-1)}" value="0">
  <span id="status">Frame 0 / {len(frame_files)}</span>
</div>
<script>
var frames = {frames_json};
var idx = 0;
var playing = false;
var timer = null;
var screen = document.getElementById('screen');
var scrubber = document.getElementById('scrubber');
var status = document.getElementById('status');
var playBtn = document.getElementById('play-btn');

function show(i) {{
  idx = Math.max(0, Math.min(frames.length - 1, i));
  screen.src = 'frames/' + frames[idx];
  scrubber.value = idx;
  status.textContent = 'Frame ' + (idx + 1) + ' / ' + frames.length;
}}

function toggle() {{
  if (playing) {{
    playing = false;
    clearInterval(timer);
    playBtn.textContent = 'Play';
  }} else {{
    playing = true;
    playBtn.textContent = 'Pause';
    timer = setInterval(function() {{
      if (idx >= frames.length - 1) {{
        idx = 0;
      }} else {{
        idx++;
      }}
      show(idx);
    }}, 100);
  }}
}}

playBtn.onclick = toggle;
scrubber.oninput = function() {{
  if (playing) toggle();
  show(parseInt(scrubber.value));
}};
</script>
</body>
</html>"""
    with open(output_html_path, "w", encoding="utf-8") as f:
        f.write(html)

async def run_pixel_suite():
    temp_dir = os.path.join(os.environ.get("TEMP", "C:\\temp"), "inkmentor_pixel_test")
    os.makedirs(temp_dir, exist_ok=True)

    print(f"Starting Edge on port {PORT}...")
    browser_proc = subprocess.Popen([
        BROWSER_EXE,
        "--headless=new",
        f"--remote-debugging-port={PORT}",
        f"--user-data-dir={temp_dir}",
        "--no-first-run",
        "--disable-gpu",
        SERVER_URL
    ])

    results = {}
    try:
        tab_ws_url = None
        for _ in range(30):
            time.sleep(0.4)
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json", timeout=2) as r:
                    tabs = json.loads(r.read().decode())
                    for t in tabs:
                        if t.get("type") == "page" and "8000" in t.get("url", ""):
                            tab_ws_url = t.get("webSocketDebuggerUrl")
                            break
                    if tab_ws_url:
                        break
            except Exception:
                pass

        if not tab_ws_url:
            raise RuntimeError("Could not connect to browser via CDP.")

        async with websockets.connect(tab_ws_url, max_size=50*1024*1024) as ws:
            req_id = 1
            await cdp_call(ws, req_id, "Runtime.enable"); req_id += 1
            await cdp_call(ws, req_id, "Page.enable"); req_id += 1
            await cdp_call(ws, req_id, "DOM.enable"); req_id += 1
            await cdp_call(ws, req_id, "Emulation.setDeviceMetricsOverride", {
                "width": 1280,
                "height": 900,
                "deviceScaleFactor": 1,
                "mobile": False
            }); req_id += 1

            # Navigate to http://localhost:8000/
            await cdp_call(ws, req_id, "Page.navigate", {"url": "http://localhost:8000/"}); req_id += 1

            # Wait for page and scripts to be fully loaded
            for _ in range(40):
                await asyncio.sleep(0.3)
                ready = await evaluate(ws, req_id, "typeof window.ensureFontLoaded === 'function' && !!document.getElementById('notes')")
                req_id += 1
                if ready:
                    break

            await evaluate(ws, req_id, "window.ensureFontLoaded()", await_promise=True)
            req_id += 1

            # =========================================================================
            # PIXEL TEST 1: Solve "x^2 + 6x + 6"
            # =========================================================================
            print("\n=======================================================")
            print(">>> Running Pixel Test 1: Solve 'x^2 + 6x + 6'")
            print("=======================================================")
            await evaluate(ws, req_id, "window.go(8)"); req_id += 1
            await asyncio.sleep(0.5)

            # Pre-solve check on initial page
            # Start solve
            solve_start_time = time.time()
            await evaluate(ws, req_id, "window.runSolvePipeline('x^2 + 6x + 6', null)"); req_id += 1

            captured_frames = []
            frame_records = []
            screencast_files = []

            # Sample every ~100ms until solve completes
            frame_idx = 0
            while True:
                t_rel = time.time() - solve_start_time
                ss_res = await cdp_call(ws, req_id, "Page.captureScreenshot", {"format": "png"})
                req_id += 1
                png_bytes = base64.b64decode(ss_res["result"]["data"])

                # Save frame image
                frame_filename = f"frame_{frame_idx:04d}.png"
                frame_filepath = os.path.join(FRAMES_DIR, frame_filename)
                with open(frame_filepath, "wb") as f:
                    f.write(png_bytes)
                screencast_files.append(frame_filepath)

                # Query DOM state at this frame
                state = await evaluate(ws, req_id, """
                (function() {
                  var notes = document.getElementById('notes');
                  var steps = Array.from(notes.querySelectorAll('.ln.ai[id^="step-"]'));
                  var mk = document.getElementById('mk');
                  var chip = document.getElementById('chip');
                  var cr = chip ? chip.getBoundingClientRect() : null;
                  var chipRect = (chip && chip.classList.contains('on')) ? [cr.left, cr.top, cr.width, cr.height] : null;
                  var info = steps.map(function(s) {
                    var lineContainer = s.querySelector('.ai-line-container') || s;
                    var r = lineContainer.getBoundingClientRect();
                    var line = s.querySelector('.ai-reenie-line');
                    var dot = s.querySelector('.ai-pen-tip-dot');
                    return {
                      id: s.id,
                      stepIdx: parseInt(s.dataset.stepIdx || s.id.replace('step-', '')),
                      clip: line ? (line.style.clipPath || '') : '',
                      dotVisible: dot ? (window.getComputedStyle(dot).display !== 'none') : false,
                      rect: [r.left, r.top, r.width, r.height]
                    };
                  });
                  return {
                    busy: window.busy,
                    stepCount: steps.length,
                    mkInDom: !!mk,
                    mkShown: mk ? mk.classList.contains('show') : false,
                    chipRect: chipRect,
                    steps: info
                  };
                })()
                """)
                req_id += 1

                captured_frames.append({
                    "frame_idx": frame_idx,
                    "time_ms": int(t_rel * 1000),
                    "png_bytes": png_bytes,
                    "state": state
                })

                frame_idx += 1

                # If solve finished (busy is false and has steps) or timeout > 35s
                if not state["busy"] and state["stepCount"] >= 3:
                    # Capture one final frame and exit
                    await asyncio.sleep(0.5)
                    break
                if t_rel > 40:
                    break

                await asyncio.sleep(0.1)

            print(f"Captured {len(captured_frames)} frames across {t_rel:.1f}s.")

            # Generate video player HTML
            video_html_path = os.path.join(OUT_DIR, "screencast.html")
            generate_video_player(screencast_files, video_html_path)
            print(f"Screencast video player saved to: {video_html_path}")

            # Get final slot rectangles from final frame state
            final_state = captured_frames[-1]["state"]
            final_steps = final_state["steps"]
            num_steps = len(final_steps)
            print(f"Final step count: {num_steps}")

            slot_rects = {}
            for s in final_steps:
                slot_rects[s["stepIdx"]] = s["rect"]

            # Analyze ink pixels frame-by-frame
            # Table headers
            print("\n------------------------- FRAME PIXEL ANALYSIS TABLE -------------------------")
            slot_headers = " | ".join([f"Slot {k} Ink" for k in range(num_steps)])
            print(f"{'Time (ms)':>9} | {'Writing':>7} | {'DOM Steps':>9} | {slot_headers} | Status")
            print("-" * (40 + num_steps * 14))

            t1_failures = []
            previous_finished_ink = {k: 0 for k in range(num_steps)}

            for fr in captured_frames:
                w, h, pix = decode_png(fr["png_bytes"])
                st = fr["state"]

                # Find which step is currently writing
                # Step i is writing if its dot is visible or its clip is not 'none' and not 'inset(-16px 100%...'
                writing_idx = None
                dom_step_indices = set()
                for s in st["steps"]:
                    dom_step_indices.add(s["stepIdx"])
                    if s["dotVisible"] or (s["clip"] and "100%" not in s["clip"] and s["clip"] != "none"):
                        writing_idx = s["stepIdx"]

                if writing_idx is None:
                    # Check if all in DOM are finished
                    if len(st["steps"]) == 0:
                        writing_idx = -1
                    elif all(s["clip"] == "none" or s["clip"] == "" for s in st["steps"]):
                        writing_idx = len(st["steps"]) - 1

                # Count ink pixels in each final slot rectangle
                slot_ink = {}
                for k in range(num_steps):
                    r = slot_rects.get(k)
                    if r and r[2] > 0 and r[3] > 0:
                        slot_ink[k] = count_ink_pixels(w, h, pix, r, exclude_rect=st.get("chipRect"))
                    else:
                        slot_ink[k] = 0

                # ASSERTION 1: No line element in #notes exceeds lines written so far + 1
                if writing_idx >= 0 and st["stepCount"] > writing_idx + 1:
                    t1_failures.append(f"Frame {fr['frame_idx']} ({fr['time_ms']}ms): DOM step count {st['stepCount']} > current writing idx {writing_idx} + 1")

                # ASSERTION 2: No two elements contain the same step index
                if len(dom_step_indices) != st["stepCount"]:
                    t1_failures.append(f"Frame {fr['frame_idx']} ({fr['time_ms']}ms): Duplicate step indices in DOM: {st['steps']}")

                # ASSERTION 3: Every slot AFTER the currently written line has ZERO ink pixels
                frame_pass = True
                for future_k in range(writing_idx + 1, num_steps):
                    ink = slot_ink.get(future_k, 0)
                    if ink > 0:
                        frame_pass = False
                        t1_failures.append(f"Frame {fr['frame_idx']} ({fr['time_ms']}ms): Future slot {future_k} has {ink} ink pixels while writing step {writing_idx}!")

                # ASSERTION 4: No previously finished line ever loses its ink
                for past_k in range(0, max(0, writing_idx)):
                    ink = slot_ink.get(past_k, 0)
                    if past_k in dom_step_indices:
                        if ink == 0 and previous_finished_ink[past_k] > 0:
                            frame_pass = False
                            t1_failures.append(f"Frame {fr['frame_idx']} ({fr['time_ms']}ms): Finished slot {past_k} lost its ink! ({ink} pixels)")
                    previous_finished_ink[past_k] = max(previous_finished_ink[past_k], ink)

                slot_vals = " | ".join([f"{slot_ink.get(k, 0):>10}" for k in range(num_steps)])
                status_str = "PASS" if frame_pass else "FAIL"
                if fr["frame_idx"] % 3 == 0 or not frame_pass or fr["frame_idx"] == len(captured_frames)-1:
                    print(f"{fr['time_ms']:>9} | {str(writing_idx):>7} | {st['stepCount']:>9} | {slot_vals} | {status_str}")

            print("------------------------------------------------------------------------------")

            t1_ok = len(t1_failures) == 0 and num_steps >= 3
            results["Pixel Test 1: Solve x^2 + 6x + 6"] = {
                "status": "PASS" if t1_ok else "FAIL",
                "failures": t1_failures[:5],
                "total_frames": len(captured_frames),
                "num_steps": num_steps,
                "video_path": video_html_path
            }
            print(f"Test 1 Result: {'PASS' if t1_ok else 'FAIL'}")
            if t1_failures:
                print("Failures (first 3):", t1_failures[:3])

            # =========================================================================
            # PIXEL TEST 2: Solve "Differentiate y = sin(3x^2)"
            # =========================================================================
            print("\n=======================================================")
            print(">>> Running Pixel Test 2: Solve 'Differentiate y = sin(3x^2)'")
            print("=======================================================")
            await evaluate(ws, req_id, "window.go(8)"); req_id += 1
            await asyncio.sleep(0.5)

            solve2_start = time.time()
            await evaluate(ws, req_id, "window.runSolvePipeline('Differentiate y = sin(3x^2)', null)"); req_id += 1

            t2_frames = []
            f_idx = 0
            while True:
                t_rel = time.time() - solve2_start
                ss = await cdp_call(ws, req_id, "Page.captureScreenshot", {"format": "png"})
                req_id += 1
                png_bytes = base64.b64decode(ss["result"]["data"])

                st = await evaluate(ws, req_id, """
                (function() {
                  var notes = document.getElementById('notes');
                  var steps = Array.from(notes.querySelectorAll('.ln.ai[id^="step-"]'));
                  var mk = document.getElementById('mk');
                  var chip = document.getElementById('chip');
                  var cr = chip ? chip.getBoundingClientRect() : null;
                  var chipRect = (chip && chip.classList.contains('on')) ? [cr.left, cr.top, cr.width, cr.height] : null;
                  var info = steps.map(function(s) {
                    var lineContainer = s.querySelector('.ai-line-container') || s;
                    var r = lineContainer.getBoundingClientRect();
                    var line = s.querySelector('.ai-reenie-line');
                    var dot = s.querySelector('.ai-pen-tip-dot');
                    return {
                      id: s.id,
                      stepIdx: parseInt(s.dataset.stepIdx || s.id.replace('step-', '')),
                      clip: line ? (line.style.clipPath || '') : '',
                      dotVisible: dot ? (window.getComputedStyle(dot).display !== 'none') : false,
                      rect: [r.left, r.top, r.width, r.height]
                    };
                  });
                  return {
                    busy: window.busy,
                    stepCount: steps.length,
                    chipRect: chipRect,
                    steps: info
                  };
                })()
                """)
                req_id += 1

                t2_frames.append({
                    "frame_idx": f_idx,
                    "time_ms": int(t_rel * 1000),
                    "png_bytes": png_bytes,
                    "state": st
                })
                f_idx += 1

                if not st["busy"] and st["stepCount"] >= 2:
                    await asyncio.sleep(0.5)
                    break
                if t_rel > 30:
                    break
                await asyncio.sleep(0.1)

            t2_final = t2_frames[-1]["state"]["steps"]
            t2_slots = {s["stepIdx"]: s["rect"] for s in t2_final}
            t2_num_steps = len(t2_final)
            t2_failures = []
            t2_prev_ink = {k: 0 for k in range(t2_num_steps)}

            print("\n------------------------- TEST 2 PIXEL ANALYSIS TABLE -------------------------")
            t2_headers = " | ".join([f"Slot {k} Ink" for k in range(t2_num_steps)])
            print(f"{'Time (ms)':>9} | {'Writing':>7} | {'DOM Steps':>9} | {t2_headers} | Status")
            print("-" * (40 + t2_num_steps * 14))

            for fr in t2_frames:
                w, h, pix = decode_png(fr["png_bytes"])
                st = fr["state"]
                writing_idx = None
                dom_steps = set()
                for s in st["steps"]:
                    dom_steps.add(s["stepIdx"])
                    if s["dotVisible"] or (s["clip"] and "100%" not in s["clip"] and s["clip"] != "none"):
                        writing_idx = s["stepIdx"]

                if writing_idx is None:
                    if len(st["steps"]) == 0:
                        writing_idx = -1
                    elif all(s["clip"] == "none" or s["clip"] == "" for s in st["steps"]):
                        writing_idx = len(st["steps"]) - 1

                t2_slot_ink = {}
                for k in range(t2_num_steps):
                    r = t2_slots.get(k)
                    if r and r[2] > 0 and r[3] > 0:
                        t2_slot_ink[k] = count_ink_pixels(w, h, pix, r, exclude_rect=st.get("chipRect"))
                    else:
                        t2_slot_ink[k] = 0

                fr_pass = True
                for future_k in range(writing_idx + 1, t2_num_steps):
                    ink = t2_slot_ink.get(future_k, 0)
                    if ink > 0:
                        fr_pass = False
                        t2_failures.append(f"Frame {fr['frame_idx']} ({fr['time_ms']}ms): Future slot {future_k} has {ink} ink pixels while writing step {writing_idx}!")

                for past_k in range(0, max(0, writing_idx)):
                    ink = t2_slot_ink.get(past_k, 0)
                    if past_k in dom_steps:
                        if ink == 0 and t2_prev_ink[past_k] > 0:
                            fr_pass = False
                            t2_failures.append(f"Frame {fr['frame_idx']} ({fr['time_ms']}ms): Finished slot {past_k} lost its ink! ({ink} pixels)")
                    t2_prev_ink[past_k] = max(t2_prev_ink[past_k], ink)

                slot_vals = " | ".join([f"{t2_slot_ink.get(k, 0):>10}" for k in range(t2_num_steps)])
                status_str = "PASS" if fr_pass else "FAIL"
                if fr["frame_idx"] % 3 == 0 or not fr_pass or fr["frame_idx"] == len(t2_frames)-1:
                    print(f"{fr['time_ms']:>9} | {str(writing_idx):>7} | {st['stepCount']:>9} | {slot_vals} | {status_str}")

            print("------------------------------------------------------------------------------")

            t2_ok = len(t2_failures) == 0 and t2_num_steps >= 2
            results["Pixel Test 2: Solve Differentiate y = sin(3x^2)"] = {
                "status": "PASS" if t2_ok else "FAIL",
                "failures": t2_failures[:5],
                "total_frames": len(t2_frames),
                "num_steps": t2_num_steps
            }
            print(f"Test 2 Result: {'PASS' if t2_ok else 'FAIL'} (Failures: {len(t2_failures)})")

            # =========================================================================
            # TEST 3: Reload / Page Switch instant path (all lines painted first frame)
            # =========================================================================
            print("\n>>> Running Test 3: Reload & Switch Page instant path")
            t3_eval = await evaluate(ws, req_id, """
            (async function() {
              window.go(8);
              // Render instant path
              var t0 = performance.now();
              window.render({ animate: false });
              var t1 = performance.now();
              var steps = Array.from(document.querySelectorAll('.ln.ai[id^="step-"]'));
              var clips = steps.map(function(s) {
                var l = s.querySelector('.ai-reenie-line');
                return l ? (l.style.clipPath || 'none') : 'none';
              });
              var dots = steps.map(function(s) {
                var d = s.querySelector('.ai-pen-tip-dot');
                return d ? window.getComputedStyle(d).display : 'none';
              });
              return {
                durationMs: t1 - t0,
                stepCount: steps.length,
                allNone: clips.every(function(c) { return c === 'none' || c === ''; }),
                allDotsHidden: dots.every(function(d) { return d === 'none'; })
              };
            })()
            """, await_promise=True)
            req_id += 1

            t3_pass = (
                t3_eval["durationMs"] < 100 and
                t3_eval["stepCount"] >= 2 and
                t3_eval["allNone"] is True and
                t3_eval["allDotsHidden"] is True
            )
            results["Test 3: Reload & Switch Page instant path"] = {
                "status": "PASS" if t3_pass else "FAIL",
                "details": t3_eval
            }
            print("Test 3 Result:", "PASS" if t3_pass else "FAIL", t3_eval)

            # =========================================================================
            # TEST 4: Solve again mid-animation & page switch mid-animation
            # =========================================================================
            print("\n>>> Running Test 4: Interruption mid-animation (solve again & page switch)")
            t4_eval = await evaluate(ws, req_id, """
            (async function() {
              window.go(8);
              // Start solve 1
              window.runSolvePipeline('x^2 + 6x + 6', null);
              await new Promise(function(r) { setTimeout(r, 800); });

              // Start solve 2 mid-animation
              window.runSolvePipeline('Differentiate y = sin(3x^2)', null);
              await new Promise(function(r) { setTimeout(r, 600); });

              // Switch to Page 1 mid-animation
              window.go(1);
              var p1Text = document.getElementById('notes').textContent;

              // Switch back to Page 8
              window.go(8);
              var steps = Array.from(document.querySelectorAll('.ln.ai[id^="step-"]'));
              var ids = steps.map(function(s){ return s.id; });
              var hasDuplicates = new Set(ids).size !== ids.length;

              return {
                p1Ok: p1Text.indexOf('Chain rule') !== -1,
                hasDuplicates: hasDuplicates,
                stepCount: steps.length,
                busy: window.busy
              };
            })()
            """, await_promise=True)
            req_id += 1

            t4_pass = (
                t4_eval["p1Ok"] is True and
                t4_eval["hasDuplicates"] is False and
                t4_eval["stepCount"] >= 2
            )
            results["Test 4: Interruption mid-animation"] = {
                "status": "PASS" if t4_pass else "FAIL",
                "details": t4_eval
            }
            print("Test 4 Result:", "PASS" if t4_pass else "FAIL", t4_eval)

            # =========================================================================
            # TEST 5: Part C Square Root Symbol verification ("sqrt(3)" and "sqrt(x^2 + 1)")
            # =========================================================================
            print("\n>>> Running Test 5: Part C Square Root Symbol verification")
            t5_eval = await evaluate(ws, req_id, """
            (function() {
              var frag1 = window.buildLineSvg("y = sqrt(3)");
              var frag2 = window.buildLineSvg("f(x) = sqrt(x^2 + 1)");

              var testDiv = document.createElement('div');
              testDiv.id = 'sqrt-test-container';
              testDiv.style.position = 'absolute';
              testDiv.style.left = '50px';
              testDiv.style.top = '100px';
              testDiv.appendChild(frag1.el);
              testDiv.appendChild(frag2.el);
              document.body.appendChild(testDiv);

              var wraps = testDiv.querySelectorAll('.math-sqrt-wrap');
              var svgs = testDiv.querySelectorAll('.math-sqrt');
              var paths = testDiv.querySelectorAll('.math-sqrt path');

              var res = {
                wrapCount: wraps.length,
                svgCount: svgs.length,
                pathD1: paths[0] ? paths[0].getAttribute('d') : '',
                pathD2: paths[1] ? paths[1].getAttribute('d') : '',
                hasTick: paths[0] ? paths[0].getAttribute('d').indexOf('M 1 20 L 4 23') !== -1 : false,
                hasDownstroke: paths[0] ? paths[0].getAttribute('d').indexOf('L 9 34') !== -1 : false,
                hasRising: paths[0] ? paths[0].getAttribute('d').indexOf('L 16 5') !== -1 : false,
                w1: wraps[0] ? wraps[0].getBoundingClientRect().width : 0,
                w2: wraps[1] ? wraps[1].getBoundingClientRect().width : 0
              };
              testDiv.remove();
              return res;
            })()
            """)
            req_id += 1

            t5_pass = (
                t5_eval["wrapCount"] == 2 and
                t5_eval["hasTick"] is True and
                t5_eval["hasDownstroke"] is True and
                t5_eval["hasRising"] is True and
                t5_eval["w2"] > t5_eval["w1"] # Longer argument has wider radical bar!
            )
            results["Test 5: Part C Square Root Symbol"] = {
                "status": "PASS" if t5_pass else "FAIL",
                "details": t5_eval
            }
            print("Test 5 Result:", "PASS" if t5_pass else "FAIL", t5_eval)

    finally:
        browser_proc.kill()

    print("\n================== FINAL TEST SUMMARY ==================")
    all_ok = True
    for name, r in results.items():
        st = r["status"]
        if st != "PASS": all_ok = False
        print(f"[{st}] {name}")
    print("========================================================")
    return all_ok

if __name__ == "__main__":
    ok = asyncio.run(run_pixel_suite())
    exit(0 if ok else 1)
