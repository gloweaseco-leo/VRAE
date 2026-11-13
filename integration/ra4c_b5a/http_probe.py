"""First actual signed-session HTTP -> original Console SSR roundtrip."""

from .support import Runtime


def main():
    r = Runtime("http-probe-311-01")
    try:
        r.start()
        for case in ("404", "200"):
            client = r.client()
            response, _, _ = client.login(r.issuer, "task-" + case)
            assert response[0] == 303, response[0]
            status, raw, _ = client.request("GET", r.review_path(case))
            assert status == 200, status
            assert "Reviewer 原文只读".encode() in raw
            status, raw, _ = client.request("GET", r.review_path(case, "proposal"))
            assert status == 200, status
            assert b"proposal-form" in raw
            assert b"NOT_APPROVED" in raw
        print("B5A_REAL_SIGNED_SESSION_REVIEWER_PG_EXISTING_SSR_PASS")
    finally:
        r.stop()


if __name__ == "__main__":
    main()
