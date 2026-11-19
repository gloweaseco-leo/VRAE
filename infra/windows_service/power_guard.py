"""Process-scoped wake request for the authorized temporary local service.

No power-plan, display, VPN, proxy, DNS or routing changes. Manual sleep remains
the user's decision. Stop by creating the declared stop file or ending this PID.
"""
import argparse
import ctypes
from datetime import datetime, UTC
import json
import os
from pathlib import Path
import time


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--until',required=True)
    p.add_argument('--receipt',required=True)
    p.add_argument('--stop-file',required=True)
    a=p.parse_args()
    if os.name!='nt':raise RuntimeError('ACTUAL_WINDOWS_REQUIRED')
    until=datetime.fromisoformat(a.until).timestamp()
    if not time.time()<until<=time.time()+86400:
        raise ValueError('BOUNDED_FUTURE_WAKE_WINDOW_REQUIRED')
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.SetThreadExecutionState.argtypes=[ctypes.c_uint32]
    kernel.SetThreadExecutionState.restype=ctypes.c_uint32
    stop=Path(a.stop_file);receipt=Path(a.receipt)
    try:
        if not kernel.SetThreadExecutionState(0x80000001):
            raise ctypes.WinError(ctypes.get_last_error())
        while time.time()<until and not stop.exists():
            receipt.write_text(json.dumps({'state':'ACTIVE_PROCESS_SCOPED_WAKE_REQUEST',
                'pid':os.getpid(),'until':a.until,'checked_at':datetime.now(UTC).isoformat(),
                'power_plan_changed':False,'display_required':False,
                'manual_sleep_prevented':False}),encoding='utf8')
            time.sleep(min(15,max(0.1,until-time.time())))
    finally:
        kernel.SetThreadExecutionState(0x80000000)
        receipt.write_text(json.dumps({'state':'WAKE_REQUEST_RELEASED','pid':os.getpid()}),encoding='utf8')


if __name__=='__main__':main()
