"""Observed target facts only; no runtime pin, dependency or deployment mutation."""
from importlib.metadata import PackageNotFoundError, version
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys


def tool(name, arguments):
    binary = shutil.which(name)
    if binary is None:
        return {'status': 'NOT_INSTALLED_IN_THIS_HOST'}
    result = subprocess.run([binary, *arguments], capture_output=True, text=True, timeout=30)
    return {'exit_code': result.returncode, 'stdout': result.stdout.strip()[:1024],
            'stderr': result.stderr.strip()[:1024]}


def main():
    dependencies = {}
    for name in ('h11', 'dnspython', 'jsonschema', 'psycopg', 'cryptography'):
        try:
            dependencies[name] = version(name)
        except PackageNotFoundError:
            dependencies[name] = 'NOT_INSTALLED_IN_THIS_HOST'
    data = {'status': 'PYTHON313_CANDIDATE_NOT_PRODUCTION_LOCKED', 'python': sys.version,
        'platform': platform.platform(), 'dependencies': dependencies,
        'node': tool('node', ['--version']), 'chrome': tool('google-chrome', ['--version']),
        'worker_image_pins': json.loads(Path('integration/ra4b/python-images.json').read_text()),
        'postgres_image_pin': Path('infra/ra4a/image.txt').read_text().strip(),
        'developer_python_hint': Path('.python-version').read_text().strip(),
        'remaining_limit': 'Original isolated HTTP/browser lab images still pin 3.11; host and container patch versions are not asserted identical. No production lock or deploy.'}
    out = Path('ci/.runtime')
    out.mkdir(parents=True, exist_ok=True)
    (out / 'environment.json').write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(data))


if __name__ == '__main__':
    main()
