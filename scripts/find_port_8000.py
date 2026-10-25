import subprocess
import os

for pid in [18968, 20332]:
    print(f"Killing PID {pid}")
    res = subprocess.run(f"taskkill /F /PID {pid}", shell=True, capture_output=True, text=True)
    print("res:", res.stdout, res.stderr)
    try:
        os.kill(pid, 9)
        print("os.kill succeeded")
    except Exception as e:
        print("os.kill failed:", e)

res = subprocess.run('netstat -ano | findstr :8000', shell=True, capture_output=True, text=True)
print("Remaining on 8000:", res.stdout)
