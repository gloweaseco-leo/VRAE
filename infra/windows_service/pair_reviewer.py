"""Interactive actual enrollment. No password, TOTP or seed enters a shell arg/log."""
import argparse
import json
import os
from pathlib import Path
import subprocess
from infra.windows_service.private_host import invoke
from infra.windows_service.windows_credentials import current_sid, current_account_name, verify


def dialog(value):
    result=subprocess.run(["powershell.exe","-NoProfile","-STA","-ExecutionPolicy","Bypass",
        "-File",str(Path(__file__).with_name("otp_dialog.ps1"))],
        input=json.dumps(value).encode(),capture_output=True,check=True)
    data=json.loads(result.stdout.decode("utf-8-sig"))
    if data.get("cancelled") or data.get("invalid_code"):
        raise PermissionError("LOCAL_MFA_CANCELLED_OR_INVALID")
    return data


def action(image,name,operation,data):
    try:
        raw=invoke(image,name,"python","-B","-m","infra.windows_service.mfa",operation,
                   data=json.dumps(data).encode())
    except subprocess.CalledProcessError as error:
        import re
        match=re.search(rb"PermissionError: ([A-Z0-9_]+)\r?\n?$",error.stderr or b"")
        if match:
            raise PermissionError(match[1].decode()) from None
        raise
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
        # A visible owner window and a user click establish the foreground
        # window for the native credential provider, even with a hidden launcher.
        import tkinter as tk
        window=tk.Tk()
        window.title("VRAE - Windows identity verification")
        window.geometry("620x210")
        window.attributes("-topmost",True)
        result={}
        tk.Label(window,text="Account: "+current_account_name()+"\nVerify this account using its PASSWORD.\n"
            "The native Windows dialog opens when you click below.\n"
            "Use the account password, not a Windows Hello PIN.\n"
            "Do not send the password or phone code in chat.",pady=20).pack()
        def authenticate():
            button.configure(state="disabled")
            window.update()
            try:
                result["primary"]=verify(pair["nonce"],sid,window.winfo_id())
            except Exception as error:
                from tkinter import messagebox
                messagebox.showerror("VRAE Windows verification",str(error)+"\nNo identity has been issued. Check the account password, not a PIN.",parent=window)
                button.configure(state="normal")
                return
            window.destroy()
        button=tk.Button(window,text="Open Windows password verification",command=authenticate)
        button.pack()
        window.lift()
        window.focus_force()
        window.mainloop()
        if "error" in result:
            raise result["error"]
        if "primary" not in result:
            raise PermissionError("WINDOWS_VERIFICATION_WINDOW_CLOSED")
        primary=result["primary"]
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
