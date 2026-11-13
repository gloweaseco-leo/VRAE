"""Inspect retained hosted ZIPs without modifying their RED evidence."""
import hashlib
import json
from pathlib import Path
import zipfile

OWN = Path(__file__).resolve().parent
BASE = OWN / 'evidence/local-repair-hosted'
for version, artifact in [('311', 14012547321), ('313', 14012707751)]:
    archive = BASE / f'artifact-{artifact}.zip'
    if not zipfile.is_zipfile(archive):
        continue
    out = BASE / version
    out.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        sources = [n for n in z.namelist() if n == f'hosted-3.{version[1:]}/source.json']
        source = json.loads(z.read(sources[0]))
        current = []
        for name in z.namelist():
            if name.endswith('/receipt.json') and '/browser-' not in name and name.startswith('browser-'):
                receipt = json.loads(z.read(name))
                if receipt.get('sourceHead') == source['actual_head']:
                    current.append((name.rsplit('/', 1)[0], receipt))
        assert len(current) == 1, [x[0] for x in current]
        browser, receipt = current[0]
        selected = [n for n in z.namelist() if n.startswith(browser + '/') and '/profile-' not in n]
        for name in selected:
            (out / Path(name).name).write_bytes(z.read(name))
        rows = json.loads(z.read(browser + '/assertions.json'))
        cdp = json.loads(z.read(browser + '/raw-cdp.json'))
        summary = {'artifact': artifact, 'zip_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
                   'checkout': source['actual_head'], 'browser': browser,
                   'passed': receipt['passed'], 'assertions': receipt['assertions'],
                   'failed': [r for r in rows if not r['pass']],
                   'last_commands': cdp['commands'][-12:], 'exceptions': cdp['exceptions'],
                   'last_documents': [r for r in cdp['responses'] if r['type'] == 'Document'][-3:],
                   'available_html': [Path(n).name for n in selected if n.endswith('.html')]}
        (out / 'inspection.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
        print(json.dumps({k: v for k, v in summary.items() if k not in ('last_commands', 'last_documents')}, indent=2))
