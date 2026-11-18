"""S5 mode of the original one-SSR workbench; no second server/Worker."""

import json
import re
from uuid import UUID

from integration.l2_ops.workbench import PreparationWorkbench
from integration.beta_review.codex3.runner import cmd


class Workbench(PreparationWorkbench):
    def ssr_configuration(self):
        cfg = super().ssr_configuration()
        cfg["native"]["s5"] = {"version": "S5_OFFLINE_ONLY_1"}
        return cfg

    def publish_commit(self, job):
        if str(UUID(job)) != job or job not in self.web_tasks:
            raise ValueError("S5_SERVER_TASK_REQUIRED")
        if self.web_tasks[job]["source_ref"] != "l2-industrial-p40-v3":
            return
        with self.r.lab.connect(dbname="vrae_ra4a_p1") as c:
            row = c.execute(
                "SELECT jsonb_build_object('version','S5_SERVER_POST_COMMIT_1',"
                "'task',jsonb_build_object('tenant_id',tenant_id,'request_id',request_id,"
                "'run_id',run_id,'job_id',job_id,'source_ref',source_ref),"
                "'lease_started_at',lease_until-interval '30 seconds',"
                "'lease_expires_at',lease_until,'worker_completed_at',created_at,"
                "'finish_event',finish_event,'signed_result_sha256',report_sha256,"
                "'observed_committed_at',clock_timestamp(),"
                "'completion_clock_basis','VISIBLE_ROW_CREATED_AT_WITH_ORIGINAL_DEFERRED_LEASE_GUARD') "
                "FROM ra4b_p2.m1_results WHERE tenant_id='tenant-test' AND job_id=%s",
                (job,),
            ).fetchone()
        if not row:
            return
        value = row[0]
        assert all(
            value["task"][k] == self.web_tasks[job][k]
            for k in ("request_id", "run_id", "job_id", "source_ref")
        )
        # Actual DB observation through the original trusted local supervisor.
        # Browser/model provide no timestamps, role, deadline, hash or pins.
        program = (
            "from pathlib import Path; import sys,json; "
            "p=Path('/state/l2-native/s5-postcommit')/sys.argv[1]; "
            "p.parent.mkdir(parents=True,exist_ok=True); d=sys.argv[2]; "
            "old=json.loads(p.read_bytes()) if p.exists() else None; "
            "assert old is None or all(old[k]==v for k,v in json.loads(d).items() if k!='observed_committed_at'); "
            "p.write_text(d) if old is None else None; p.chmod(0o600)"
        )
        cmd(
            [
                "docker",
                "exec",
                "--user",
                "10003:10003",
                self.ssr_name,
                "python",
                "-c",
                program,
                job + ".json",
                json.dumps(value, sort_keys=True),
            ]
        )

    def observe(self, method, path, status, raw):
        super().observe(method, path, status, raw)
        if (
            method == "GET"
            and status == 200
            and re.fullmatch(r"/b5a/m2/task/[A-Za-z0-9_-]{43}", path)
        ):
            text = raw.decode()
            if 'data-key="m2-job-state">TEST_ONLY_DONE<' in text:
                match = re.search(r'data-key="m2-job_id">([0-9a-f-]{36})<', text)
                if match:
                    self.publish_commit(match[1])

    def await_job(self, job):
        value = super().await_job(job)
        if self.bridge_process is not None:
            self.publish_commit(job)
        return value


def main(label, minor):
    from integration.beta_review.codex3.m3_workbench import serve

    return serve(Workbench(label, minor))
