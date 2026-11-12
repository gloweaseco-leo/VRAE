"""Archive own pre-release revisions and completed local raw logs, without deleting originals."""
import hashlib
import json
from pathlib import Path
import zipfile

OUT = Path(__file__).resolve().parent


def archive(name, paths):
    entries = []
    with zipfile.ZipFile(OUT / name, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(paths):
            assert p.resolve().is_relative_to(OUT)
            raw = p.read_bytes()
            key = p.relative_to(OUT).as_posix()
            z.writestr(key, raw)
            entries.append({'path': key, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
    with zipfile.ZipFile(OUT / name) as z:
        assert z.testzip() is None
        for e in entries:
            assert hashlib.sha256(z.read(e['path'])).hexdigest() == e['sha256']
    return {'archive': name, 'sha256': hashlib.sha256((OUT / name).read_bytes()).hexdigest(), 'entries': entries}


if __name__ == '__main__':
    old = [p for folder in [*OUT.glob('preview-initial'), *OUT.glob('preview-print-red*'),
                             *OUT.glob('ui-initial')] for p in folder.rglob('*') if p.is_file()]
    records = [archive('layout-history.zip', old)]
    for name in ('python311-final', 'python313-final'):
        folder = OUT / '.checks' / name
        if (folder / 'summary.json').exists():
            paths = [p for p in folder.iterdir() if p.is_file()]
            records.append(archive(name + '-raw.zip', paths))
    (OUT / 'archive-index.json').write_text(json.dumps(records, indent=2) + '\n', encoding='utf-8')
