"""Real Chromium sandbox gate. Never disables sandbox and never visits a website."""
import json
import os
from pathlib import Path
import subprocess
import sys

command = ["chromium", "--headless", "--disable-gpu", "--no-first-run",
           "--disable-background-networking", "--user-data-dir=/tmp/profile",
           "--allow-chrome-scheme-url", "--dump-dom", "chrome://sandbox"]
print(json.dumps({"uid": os.getuid(), "argv": command,
    "status": Path('/proc/self/status').read_text(),
    "interfaces": os.listdir('/sys/class/net')}), flush=True)
result = subprocess.run(command, capture_output=True, text=True, timeout=25)
print(result.stdout, result.stderr, flush=True)
print('CHROMIUM_EXIT_CODE=' + str(result.returncode), flush=True)
if result.returncode or 'Seccomp-BPF' not in result.stdout or 'PID namespaces' not in result.stdout:
    print('SECURITY_BLOCKED: sandbox attestation unavailable', flush=True)
    sys.exit(1)
# Require the internal diagnostic, not merely a running process or inherited container seccomp.
from html.parser import HTMLParser

class Cells(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = []
    def handle_data(self, data):
        if data.strip():
            self.text.append(data.strip())

cells = Cells()
cells.feed(result.stdout)
for label, expected in (('Layer 1 Sandbox', 'Namespace'), ('PID namespaces', 'Yes'),
                        ('Network namespaces', 'Yes'), ('Seccomp-BPF sandbox', 'Yes')):
    if label not in cells.text or cells.text[cells.text.index(label) + 1] != expected:
        print('SECURITY_BLOCKED: ' + label, flush=True)
        sys.exit(1)
print('SANDBOX_PREFLIGHT_PASS', flush=True)
