"""Interactive actual enrollment. No password, TOTP or seed enters a shell arg/log."""
import argparse
import json
import os
from pathlib import Path
import subprocess
from infra.windows_service.private_host import invoke
from infra.windows_service.windows_credentials import current_sid, verify


def dialog(value):
    result=subprocess.run(["powershell.exe","-NoProfile","-STA","-ExecutionPolicy","Bypass",
        "-File",str(Path(__file__).with_name("otp_dialog.ps1"))],
        input=json.dumps(value).encode(),capture_output=True,check=True)
    data=json.loads(result.stdout.decode("utf-8-sig"))
    if data.get("cancelled") or data.get("invalid_code"):
        raise PermissionError("LOCAL_MFA_CANCELLED_OR_INVALID")
    return data


def action(image,name,operation,data):
    raw=invoke(image,name,"python","-B","-m","infra.windows_service.mfa",operation,
               data=json.dumps(data).encode())
    return json.loads(raw)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--operator-image",required=True)
    p.add_argument("--name",default="vrae-windows")
    p.add_argument("--receipt",required=True)
    a=p.parse_args()
    target=Path(a.receipt)
    target.parent.mkdir(parents=True,exist_ok=True)
    def progress(state,**extra):
        target.write_text(json.dumps({"state":state,**extra}),encoding="utf8")
    try:
        if os.name!="nt":
            raise PermissionError("ACTUAL_WINDOWS_OPERATOR_REQUIRED")
        sid=current_sid()
        pair=action(a.operator_image,a.name,"begin-pair",{"sid":sid})
        progress("WAITING_PHONE_PAIRING")
        dialog({"mode":"pairing","seed":pair["seed"]})
        del pair["seed"]
        progress("WAITING_ACTUAL_WINDOWS_PASSWORD")
        primary=verify(pair["nonce"],sid)
        progress("WAITING_ACTUAL_PHONE_CODE")
        code=dialog({"mode":"otp"})["code"]
        result=action(a.operator_image,a.name,"finish-pair",{"primary":primary,"code":code})
        del code,primary
        progress("ACTUAL_WINDOWS_PASSWORD_AND_TOTP_ENROLLED",**result)
    except Exception as error:
        progress("NOT_ENROLLED",error_type=type(error).__name__,
                 reason=str(error)[:400] if isinstance(error,PermissionError) else "PRIVATE_OPERATION_FAILED")
        raise


if __name__=="__main__":
    main()
