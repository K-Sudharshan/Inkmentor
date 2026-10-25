import os

for root, _, files in os.walk('.'):
    if any(p in root for p in ['.venv', '.git', '__pycache__', 'fonts', 'node_modules']):
        continue
    for f in files:
        if f.endswith(('.py', '.html', '.md', '.json')):
            path = os.path.join(root, f)
            with open(path, 'r', encoding='utf-8', errors='ignore') as fp:
                for i, line in enumerate(fp):
                    if '.latex' in line or 'step["latex"]' in line or "step['latex']" in line or "st.latex" in line or "step.latex" in line:
                        print(f"{path}:{i+1}: {line.strip()[:100]}")
