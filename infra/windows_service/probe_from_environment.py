"""External CI caller. Temporary client secrets are never artifacts."""
import json
import os
from pathlib import Path
import tempfile
from infra.windows_service.external_probe import run


def main():
    secret=os.environ.pop("VRAE_WINDOWS_PUBLIC_MTLS")
    cfg=json.loads(secret)
    del secret
    if not cfg["host"].endswith(".ts.net"):
        raise ValueError("ACTUAL_FUNNEL_HOST_REQUIRED")
    with tempfile.TemporaryDirectory(prefix="vrae-mtls-") as temp:
        root=Path(temp)
        root.chmod(0o700)
        for field in ("certificate","key","other_certificate","other_key"):
            value=cfg.pop(field+"_pem")
            file=root/(field+".pem")
            fd=os.open(file,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,"w") as f:
                f.write(value)
            cfg[field]=str(file)
        result=run(cfg)
        assert result["external_network"] is True
        print(json.dumps(result))


if __name__=="__main__":
    main()
