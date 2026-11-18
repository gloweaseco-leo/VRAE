"""No live API: verify untrusted local configuration cannot enable capabilities."""

from dataclasses import replace
import time
import unittest

from integration.l2_launch.runtime.adapter import Denied, LocalPolicy, PrivateAdapter
from vrae.application.ra4b_p2.m1.consumer import AppEndpoint, ConsumerDenied, TaskClient


class Boundary(unittest.TestCase):
    def test_capability_configuration_is_closed(self):
        base = LocalPolicy("tenant-test", time.time() + 60)
        for changes in (
            {"tenant": "customer-real"},
            {"expires": float("nan")},
            {"expires": float("inf")},
            {"expires": True},
            {"expires": 0},
            {"expires": "tomorrow"},
            {"bind": "0.0.0.0"},
            {"public": True},
            {"model": "PAID"},
            {"mode": "LIVE"},
        ):
            with self.subTest(changes=changes), self.assertRaises(Denied):
                replace(base, **changes).require("tenant-test")

    def test_policy_cannot_route_another_tenant(self):
        with self.assertRaises(Denied):
            LocalPolicy("tenant-test", time.time() + 60).require("tenant-beta")

    def test_missing_app_secret_uses_original_rejection(self):
        with self.assertRaises(ConsumerDenied):
            AppEndpoint("", "tenant-test", frozenset(("accepted-404",)))

    def test_no_dto_substitutes_for_original_client(self):
        with self.assertRaises(Denied):
            PrivateAdapter(object(), LocalPolicy("tenant-test", time.time() + 60))

    def test_no_url_identity_or_model_fields_enter_original_client(self):
        client = TaskClient(AppEndpoint("x" * 40, "tenant-test", frozenset(("accepted-404",))))
        adapter = PrivateAdapter(client, LocalPolicy("tenant-test", time.time() + 60))
        for body in (
            {"url": "https://example.org"},
            {"source_ref": "accepted-404", "tenant_id": "tenant-beta"},
            {"source_ref": "accepted-404", "model": "PAID"},
        ):
            with self.subTest(body=body), self.assertRaises(Denied):
                adapter.submit("tenant-test", body, "boundary-test-0001")


class ReturnProposalBoundary(unittest.TestCase):
    """Explicit offline mock PG responses; full lab separately uses actual PG/API."""

    def setUp(self):
        from unittest.mock import Mock
        from uuid import uuid4
        from vrae.application.ra4b_p2.m1.consumer import TaskHandle
        from integration.l2_launch.runtime.resume import ResumeProposal

        self.client = TaskClient(AppEndpoint("x" * 40, "tenant-test", frozenset(("accepted-404",))))
        self.client.status = Mock(return_value={"job_state": "PENDING", "attempts": 0})
        self.adapter = PrivateAdapter(self.client, LocalPolicy("tenant-test", time.time() + 60))
        self.gate = ResumeProposal(self.adapter)
        self.task = TaskHandle("tenant-test", "accepted-404", *(str(uuid4()) for _ in range(4)))

    def cookie(self):
        invitation = self.gate.issue_controlled("tenant-test", self.task)
        cookie, headers = self.gate.exchange("tenant-test", invitation)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertIn("HttpOnly; Secure; SameSite=Strict", cookie)
        return invitation, cookie.split(";", 1)[0]

    def test_single_use_and_wrong_scope_are_uniform(self):
        invitation, cookie = self.cookie()
        for action in (
            lambda: self.gate.exchange("tenant-test", invitation),
            lambda: self.gate.status("tenant-beta", cookie),
            lambda: self.gate.status(
                "tenant-test", cookie, query="audit_id=" + self.task.request_id
            ),
            lambda: self.gate.status("tenant-test", "__Host-vrae-return=" + self.task.request_id),
            lambda: self.gate.status("tenant-test", "__Host-vrae-return=" + "\ud800" * 43),
        ):
            with self.assertRaises(Denied) as caught:
                action()
            self.assertEqual(caught.exception.code, "RETURN_ACCESS_ENDED")

    def test_actual_short_ttl_expires(self):
        invitation = self.gate.issue_controlled("tenant-test", self.task, ttl=0.001)
        time.sleep(0.01)
        with self.assertRaises(Denied):
            self.gate.exchange("tenant-test", invitation)

    def test_each_read_rechecks_current_original_client(self):
        _, cookie = self.cookie()
        self.assertFalse(self.gate.status("tenant-test", cookie)[0]["report_available"])
        self.client.status.side_effect = ConsumerDenied()
        with self.assertRaises(Denied) as caught:
            self.gate.status("tenant-test", cookie)
        self.assertEqual(caught.exception.code, "RETURN_ACCESS_ENDED")

    def test_revoke_and_restart_end_prior_cookie(self):
        from integration.l2_launch.runtime.resume import ResumeProposal

        _, cookie = self.cookie()
        self.gate.revoke_all()
        for gate in (self.gate, ResumeProposal(self.adapter)):
            with self.assertRaises(Denied):
                gate.status("tenant-test", cookie)


if __name__ == "__main__":
    unittest.main()
