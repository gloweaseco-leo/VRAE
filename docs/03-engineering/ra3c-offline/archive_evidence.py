"""Archive own pre-release revisions and completed local raw logs, without deleting originals."""
import hashlib
import json
from pathlib import Path
import zipfile

OUT = Path(__file__).resolve().parent


def archive(name, paths, base=OUT):
    entries = []
    with zipfile.ZipFile(OUT / name, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(paths):
            assert p.resolve().is_relative_to(base)
            raw = p.read_bytes()
            key = p.relative_to(base).as_posix()
            z.writestr(key, raw)
            entries.append({'path': key, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
    with zipfile.ZipFile(OUT / name) as z:
        assert z.testzip() is None
        for e in entries:
            assert hashlib.sha256(z.read(e['path'])).hexdigest() == e['sha256']
    return {'archive': name, 'base': str(base),
            'sha256': hashlib.sha256((OUT / name).read_bytes()).hexdigest(), 'entries': entries}


if __name__ == '__main__':
    old = [p for folder in [*OUT.glob('preview-initial'), *OUT.glob('preview-print-red*'),
                             *OUT.glob('ui-initial')] for p in folder.rglob('*') if p.is_file()]
    records = [archive('layout-history.zip', old)]
    records.append(archive('current-artifacts-raw.zip', [p for name in ('preview', 'ui', 'local')
                    for p in (OUT / name).rglob('*') if p.is_file()]))
    root = OUT.parents[2]
    fixtures = root / 'tests/reporting/fixtures'
    records.append(archive('source-fixtures-raw.zip', list(fixtures.glob('*.json')), root))
    records.append(archive('development-reporting-raw.zip',
                          list((OUT / '.checks').glob('reporting*.xml'))))
    ci = OUT / '.checks' / 'ci-43152015757'
    if (ci / 'security-proof.json').exists():
        records.append(archive('functional-ci-raw.zip', [p for p in ci.iterdir() if p.is_file()]))
        visible = OUT / 'ci-functional'
        visible.mkdir(exist_ok=True)
        for name in ('proof.json', 'security-proof.json'):
            (visible / name).write_bytes((ci / name).read_bytes())
    for name in ('python311', 'python311-final', 'python313-final',
                 'python311-utf8-final', 'python313-utf8-final'):
        folder = OUT / '.checks' / name
        if (folder / 'summary.json').exists():
            paths = [p for p in folder.iterdir() if p.is_file()]
            records.append(archive(name + '-raw.zip', paths))
    (OUT / 'archive-index.json').write_text(json.dumps(records, indent=2) + '\n', encoding='utf-8')
