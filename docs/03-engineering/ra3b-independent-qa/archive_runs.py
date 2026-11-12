"""Append-only packaging of actual local evidence, never source fixture changes."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent


def main():
    target = HERE/'baseline-raw.zip'
    assert not target.exists(), 'Do not overwrite sealed evidence'
    runs = ('baseline-311', 'baseline-313', 'final-baseline-311', 'final-baseline-313')
    records, summaries = [], {}
    with zipfile.ZipFile(target, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name in runs:
            root = ROOT/'.venv/ra3b-independent'/name
            summary = json.loads((root/'summary.json').read_text())
            assert summary['outcome'] == 'PREREQUISITE_RED_CONFIRMED'
            assert summary['feature_qa_pass'] is False
            assert len(summary['commands']) == 24 and all(c['matches'] for c in summary['commands'])
            assert all(summary['counts'][k]['error'] == 1 and summary['counts'][k]['skipped'] == 0
                       for k in ('qa', 'full'))
            summaries[name] = summary
            for p in sorted(root.iterdir()):
                assert p.is_file()
                raw = p.read_bytes()
                path = name+'/'+p.name
                z.writestr(path, raw)
                records.append(dict(path=path, size=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    with zipfile.ZipFile(target) as z:
        for entry in records:
            raw = z.read(entry['path'])
            assert len(raw) == entry['size'] and hashlib.sha256(raw).hexdigest() == entry['sha256']
    index = dict(archive=target.name, sha256=digest, files=records, runs=summaries,
        feature_pass=False, candidate_execution='PENDING_FINAL_READY_NOTICE')
    (HERE/'evidence-index.json').write_text(json.dumps(index, indent=2)+'\n', encoding='utf-8')
    print('Archived', len(records), 'raw files; SHA256', digest)


if __name__ == '__main__':
    main()
