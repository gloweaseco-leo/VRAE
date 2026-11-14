"""Classify text identifiers without publishing their raw values."""
import json
from privacy_inventory import PRIVATE, baseline_files, sha


def main():
    report = json.loads((PRIVATE / "semantic-review.json").read_bytes())
    emails = report["email_values_require_review"]
    rows = []
    baseline = baseline_files()
    for email, count in emails.items():
        domain = email.rsplit("@", 1)[1].lower().strip(".")
        reserved = domain in {"example.com", "example.org", "example.net"} or domain.endswith((".test", ".invalid", ".example", ".localhost"))
        rows.append({"value_sha256": sha(email.encode()), "occurrences": count, "domain_class": "RESERVED_SYNTHETIC" if reserved else "REQUIRES_REVIEW",
                     "safe_reserved_domain": domain if reserved else None, "domain_sha256": sha(domain.encode()), "paths": []})
    for entry in report["inventory"]:
        if entry["path_class"] == ".dump":
            continue
        raw = baseline[entry["path"]]
        text = raw.decode("utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8")
        for email, row in zip(emails, rows):
            if email in text:
                row["paths"].append(entry["path"])
    (PRIVATE / "identifier-review.json").write_text(json.dumps({"rows": rows,
        "fixture_source_hosts": report["fixture_source_hosts"], "operational_hostname_counts": report["operational_junit_hostname_counts"]}, indent=2))
    print(json.dumps({"rows": [{k: v for k, v in row.items() if k != "paths"} | {"files": len(row["paths"]), "examples": row["paths"][:2]} for row in rows],
                      "fixture_source_hosts": report["fixture_source_hosts"]}))


if __name__ == "__main__":
    main()
