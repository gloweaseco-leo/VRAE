"""Read actual Actions job timestamps; never substitute job counts for minutes."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import subprocess


def api(path):
    return json.loads(subprocess.check_output(['gh', 'api', path], text=True, encoding='utf-8'))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('run', type=int)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    prefix = 'repos/gloweaseco-leo/VRAE/actions/runs/' + str(args.run)
    run = api(prefix)
    jobs = []
    page = 1
    while True:
        batch = api(prefix + '/attempts/' + str(run['run_attempt']) + '/jobs?per_page=100&page=' + str(page))['jobs']
        jobs.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    seconds = 0.0
    for job in jobs:
        duration = None
        if job.get('runner_id') and job.get('started_at') and job.get('completed_at'):
            duration = (datetime.fromisoformat(job['completed_at'].replace('Z', '+00:00'))
                        - datetime.fromisoformat(job['started_at'].replace('Z', '+00:00'))).total_seconds()
            seconds += duration
        job['observed_runner_seconds'] = duration
    output = {'run': run, 'jobs': jobs, 'observed_runner_minutes': seconds / 60,
              'measurement': 'Sum of assigned runner job timestamps, including setup/cleanup; not billing or CPU.',
              'complete': run['status'] == 'completed', 'whole_runner_cpu': 'NOT_MEASURED'}
    Path(args.output).write_text(json.dumps(output, ensure_ascii=True, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: output[k] for k in ('complete', 'observed_runner_minutes', 'measurement')}))


if __name__ == '__main__':
    main()
