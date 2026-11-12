"""Run every unchanged frozen node through the real native adapter, no deselection."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('codex1_exact_source_proof',HERE.parent/'phase-b-initial-6a7a3d3a/attempt.py')
proof = importlib.util.module_from_spec(spec)
spec.loader.exec_module(proof)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tag',choices=('py311','py313'),required=True)
    args = parser.parse_args()
    out = HERE/args.tag
    assert not out.exists(), 'Preserve original real-native run'
    source = proof.verify()
    out.mkdir()
    command = [sys.executable,'-m','pytest','-q',proof.OVERLAYS[0],
        '--junitxml='+str(out/'frozen-64.xml'),'-o','junit_family=legacy']
    env = dict(os.environ,PYTHONPATH=str(proof.CANDIDATE_ROOT),PYTHONUTF8='1',
        PYTHONDONTWRITEBYTECODE='1',VRAE_RA3C_QA_ADAPTER_PATH=str(HERE/'adapter.py'),
        VRAE_RA3C_EXPECTED_CANDIDATE_SHA=proof.CANDIDATE)
    # Never consume the separately captured developer-artifact observation as
    # this suite's own-input visual dossier.
    env.pop('VRAE_RA3C_QA_OBSERVATIONS_PATH',None)
    began = datetime.now(timezone.utc).isoformat()
    with (out/'pytest.log').open('wb') as log:
        result = subprocess.run(command,cwd=proof.CANDIDATE_ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
    root = ET.parse(out/'frozen-64.xml').getroot()
    nodes = []
    for case in root.iter('testcase'):
        problem = case.find('error')
        status = 'error' if problem is not None else 'passed'
        if problem is None:
            problem = case.find('failure')
            if problem is not None:
                status = 'failed'
        skipped = case.find('skipped')
        if skipped is not None:
            status = 'xfail' if skipped.get('type') == 'pytest.xfail' else 'skipped'
        text = '' if problem is None else (problem.get('message','')+'\n'+(problem.text or ''))
        classification = 'ACTUAL_FROZEN_NODE_OUTCOME'
        if 'REPORT_UNSUPPORTED_PROSE' in text:
            classification = 'M02_ADMISSIBLE_INPUT_BOUNDARY_PENDING_OWNER'
        elif 'REPORT_GUARD_NOT_VALIDATED' in text:
            classification = 'M07_NOT_RUN_GUARD_PENDING_OWNER'
        elif 'REPORT_MISSING_OR_AMBIGUOUS_FACT' in text:
            classification = 'M08_MISSING_PER_FINDING_SUPPORT_PENDING_REVIEW'
        elif 'QA_MAPPING_NOT_BOUND' in text:
            classification = 'QA_MAPPING_NOT_BOUND_NOT_PRODUCTION_DEFECT'
        properties = {p.get('name'):p.get('value') for p in case.findall('properties/property')}
        nodes.append(dict(name=case.get('name'),status=status,classification=classification,
            message='' if problem is None else problem.get('message',''),properties=properties))
    counts = {s:sum(n['status'] == s for n in nodes) for s in ('passed','failed','error','skipped','xfail')}
    report = dict(kind='FROZEN_64_REAL_NATIVE_EXECUTION_NOT_OVERALL_PASS',candidate_sha=proof.CANDIDATE,
        frozen_qa_sha=proof.FREEZE,qa_execution_sha=subprocess.check_output(
            ['git','rev-parse','HEAD'],cwd=HERE.parents[3],text=True).strip(),
        python=sys.version,argv=command,cwd=str(proof.CANDIDATE_ROOT),
        started_at=began,finished_at=datetime.now(timezone.utc).isoformat(),returncode=result.returncode,
        counts=counts,nodes=nodes,source_before=source,source_after=proof.verify(),
        source_files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in
            (HERE/'adapter.py',HERE/'request-pins.json',HERE.parent/'adapter-preflight-v1/adapter_draft.py')},
        log_sha256=hashlib.sha256((out/'pytest.log').read_bytes()).hexdigest(),
        junit_sha256=hashlib.sha256((out/'frozen-64.xml').read_bytes()).hexdigest(),
        visual='VISUAL_NOT_VERIFIED_FOR_FROZEN_INPUTS',customer_share='NO_GO')
    (out/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    assert len(nodes) == 64 and not counts['skipped'] and not counts['xfail']
    print(args.tag,counts,'raw pytest exit',result.returncode)


if __name__ == '__main__':
    main()
