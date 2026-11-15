"""C3-only passive process/signing observations and one focused native case."""
import base64
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def record(folder,stage,**fields):
    value={"utc":datetime.now(timezone.utc).isoformat(),"monotonic_ns":time.monotonic_ns(),
        "stage":stage,**fields}
    with (Path(folder)/"process-observation.private.jsonl").open("a",encoding="utf-8") as stream:
        stream.write(json.dumps(value,sort_keys=True)+"\n")
    return value


def identity():
    values={"runtime_pid":os.getpid(),"python":sys.version.split()[0]}
    for name,path in (("executable",sys.executable),("base_executable",sys._base_executable)):
        p=Path(path)
        s=p.stat()
        values[name]={"name":p.name,"sha256":hashlib.sha256(p.read_bytes()).hexdigest(),
            "size":s.st_size,"mtime_ns":s.st_mtime_ns,"file_id":s.st_ino,"device":s.st_dev}
    return values


class ObservedIssuer:
    """Return the unchanged fixture signature; metadata is never authority."""
    def __init__(self,issuer,folder):
        self.original,self.folder=issuer,folder
    def __getattr__(self,name):
        return getattr(self.original,name)
    def token(self,*args,**kwargs):
        issued=self.original.token(*args,**kwargs)
        # Only nonsecret correlation from the existing private controller's frame.
        frame=sys._getframe(1)
        try:
            message=frame.f_locals.get("message",{})
            task=frame.f_locals.get("task")
            case=message.get("case") if isinstance(message,dict) else None
            if case not in ("404","200"):
                case=task.removeprefix("task-") if task in ("task-404","task-200") else "UNKNOWN"
        finally:
            del frame
        payload=issued.removeprefix("Bearer ").split(".")[1]
        claims=json.loads(base64.urlsafe_b64decode(payload+"="*((-len(payload))%4)))
        nonce=claims.get("nonce")
        record(self.folder,"TOKEN_ISSUED",case=case,iat=claims.get("iat"),exp=claims.get("exp"),
            nonce_sha256=hashlib.sha256(nonce.encode()).hexdigest() if isinstance(nonce,str) else None)
        return issued


def launched(run):
    record(run.folder,"PARENT_SSR_SPAWN",popen_pid=run.ssr.pid,controller=identity())


def stopped(run,reason):
    before=run.ssr.poll()
    sent=before is None
    record(run.folder,"BEFORE_SSR_CLEANUP",popen_pid=run.ssr.pid,natural_exit=before,
        supervisor_terminate_sent=sent,reason=reason)
    if sent:
        run.ssr.terminate()
    run.ssr.wait(timeout=15)
    record(run.folder,"AFTER_SSR_CLEANUP",popen_pid=run.ssr.pid,returncode=run.ssr.returncode,
        supervisor_terminate_sent=sent,reason=reason)
    if before is not None:
        run.result.setdefault("unexpected_ssr_exits",[]).append({"pid":run.ssr.pid,"returncode":before})
    return before


def assert_no_native_crash(run):
    values=[json.loads(s) for s in (run.folder/"process-observation.private.jsonl").read_text(encoding="utf-8").splitlines()]
    boots=[v for v in values if v['stage']=='SSR_BOOT']
    pids=[v['runtime_pid'] for v in boots]
    assert pids and not run.result.get('unexpected_ssr_exits')
    since=values[0]['utc']
    # Exact own PID attribution, no global WER reset or suppression.
    command="$start=[DateTimeOffset]::Parse('"+since+"').LocalDateTime; try { $rows=Get-WinEvent -FilterHashtable @{LogName='Application';Id=1000;StartTime=$start} -ErrorAction Stop } catch { if ($_.FullyQualifiedErrorId -notmatch 'NoMatchingEventsFound') { throw }; $rows=@() }; @($rows | ForEach-Object { $x=[xml]$_.ToXml(); $d=@{}; foreach($a in $x.Event.EventData.Data){$d[$a.Name]=$a.InnerText}; if($d['ProcessId']) { [pscustomobject]@{pid=[Convert]::ToInt32($d['ProcessId'].Replace('0x',''),16);code=$d['ExceptionCode'];module=$d['ModuleName'];utc=$_.TimeCreated.ToUniversalTime().ToString('o')} } }) | ConvertTo-Json -Compress"
    result=subprocess.run(['powershell','-NoProfile','-Command',command],capture_output=True,timeout=30)
    assert result.returncode==0,'WER_QUERY_FAILED'
    events=json.loads(result.stdout.decode('utf-8-sig') or '[]')
    if isinstance(events,dict):
        events=[events]
    own=[e for e in events if e['pid'] in pids]
    record(run.folder,'OWN_WER_CORRELATION',pids=pids,events=own)
    assert not own,'OWN_SSR_NATIVE_APPCRASH'
    for p in run.folder.glob('*.stacks.private.log'):
        assert b'Windows fatal exception' not in p.read_bytes(),'NATIVE_FATAL_CAPTURE'
    run.result['ssr_native_observation']={'runtime_pids':pids,'own_wer_crashes':0,
        'unexpected_exits':0,'periodic_sampler':False,'passive_fatal_capture':True}


def test_focused_same_process_404_then_200():
    from .runner import Run
    from .b5_consumer import browser_save,read_receipt,receipt_metadata
    run=Run(os.environ['BETA_CODEX3_RUN'],'3.11',b5=True)
    success=False
    try:
        run.case('focused_owned_pg16',run.start_pg)
        run.case('focused_same_b5_ssr',run.start_ssr)
        pid=run.ssr.pid
        before=run.r.roots()
        # Unchanged accepted browser exercises 404 -> 200 on this same child,
        # including its original widths, signatures, assertions and deadlines.
        browser_save(run)
        receipts={}
        for case in ('404','200'):
            record(run.folder,'FOCUSED_RECEIPT_READ',case=case,popen_pid=run.ssr.pid)
            _,_,digest,_=read_receipt(run,case)
            document=receipt_metadata((run.folder/('b5-receipt-'+case+'.private.html')).read_bytes())
            location=run.r.bindings['task-'+case].location
            assert document['report_id']==location.report and document['source_run_id']==location.source_run
            assert document['ref_id']==location.ref_id
            receipts[case]={'receipt_sha256':digest,'intent_sha256':hashlib.sha256(document['intent_id'].encode()).hexdigest(),
                'report_sha256':hashlib.sha256(document['report_id'].encode()).hexdigest(),'version':document['report_version']}
        assert receipts['404']['intent_sha256']!=receipts['200']['intent_sha256']
        assert receipts['404']['receipt_sha256']!=receipts['200']['receipt_sha256']
        counts=run.r.data()
        assert counts['intents']==counts['audit']==counts['outbox']==2 and counts['claims']==9
        assert run.r.roots()==before and run.ssr.pid==pid and run.ssr.poll() is None
        run.result['focused_receipts']=receipts
        run.result['focused_counts']=counts
        assert_no_native_crash(run)
        success=True
    finally:
        if not success and run.started_pg:
            try:
                run.result['focused_failure_pg_counts']=run.r.data()
                run.result['focused_failure_protected_root']=run.r.roots()
            except Exception as exc:
                run.result['focused_failure_pg_snapshot_error']=type(exc).__name__
        record(run.folder,'FOCUSED_END_BEFORE_CLEANUP',popen_pid=run.ssr.pid if run.ssr else None,
            natural_exit=run.ssr.poll() if run.ssr else None)
        try:
            run.case('focused_owned_cleanup',run.cleanup)
        finally:
            run.result['status']='FOCUSED_404_200_PASS' if success and not run.result.get('cleanup_errors') else 'FOCUSED_RED_PRESERVED'
            run.publish()
