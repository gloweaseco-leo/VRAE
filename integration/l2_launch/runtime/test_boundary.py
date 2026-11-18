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


if __name__ == "__main__":
    unittest.main()
