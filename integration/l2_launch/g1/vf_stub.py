"""Separate synthetic VF server. Only this server holds facade service auth."""

import argparse
import json
import ssl
from integration.l2_launch.g1.http_server import Handler, BoundedServer, TransportError
from integration.l2_launch.g1.client import Client
from contracts.l2_launch.contract import Refused


class VFHandler(Handler):
    def dispatch(self, method):
        try:
            cfg = self.server.cfg
            if (
                self.headers.get("Host") != "127.0.0.1:8767"
                or self.headers.get("Origin") != "https://127.0.0.1:8767"
            ):
                raise Refused("FORBIDDEN_ROLE")
            if (
                not self.path.startswith(("/v1/", "/__synthetic__/"))
                or "?" in self.path
                or "%" in self.path
            ):
                raise Refused("FORBIDDEN_ROLE")
            if any(self.headers.get_all(k) for k in ("Authorization", "X-G1-Fixture-Owner")):
                raise Refused("FORBIDDEN_ROLE")
            value = self.body() if method == "POST" else None
            client = Client(
                8766,
                cfg["ca"],
                cfg["facade_pin"],
                service_token=cfg["service_token"],
                origin="https://127.0.0.1:8767",
            )
            headers = {
                k: self.headers[k]
                for k in ("Accept", "Content-Type", "Cookie", "X-G1-CSRF", "If-Match")
                if k in self.headers
            }
            code, result, response = client.request(method, self.path, value, headers=headers)
            extra = [
                (k, v)
                for k, v in client.last_response_headers
                if k.lower() in ("set-cookie", "x-g1-csrf", "etag", "x-g1-ai-state")
            ]
            return self.send(code, result, extra)
        except TransportError as error:
            self.close_connection = True
            return self.send(error.status, {"transport_error": str(error.status)})
        except Refused as error:
            from contracts.l2_launch.vf_b import safe_error

            value = safe_error(error)
            return self.send(value["http_status"], value)
        except (OSError, ValueError, KeyError):
            return self.send(
                503, {"local_vf_fixture": "UPSTREAM_UNAVAILABLE", "real_vf_receipt": False}
            )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    cfg = json.loads(open(args.config, encoding="utf8").read())
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.minimum_version = ssl.TLSVersion.TLSv1_2
    tls.load_cert_chain(cfg["certificate"], cfg["certificate_key"])
    server = BoundedServer(("127.0.0.1", 8767), VFHandler, tls)
    server.cfg = cfg
    print('{"stage":"G1_VF_SYNTHETIC_SERVER_READY","port":8767}', flush=True)
    server.serve_forever(poll_interval=0.1)


if __name__ == "__main__":
    main()
