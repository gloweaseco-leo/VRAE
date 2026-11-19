"""Actual Windows password reauthentication. Password never becomes a Python str."""
import ctypes
from ctypes import wintypes as w
import os
import time


def _libraries():
    if os.name != "nt":
        raise PermissionError("ACTUAL_WINDOWS_LOGON_REQUIRED")
    return (ctypes.WinDLL("advapi32",use_last_error=True),
            ctypes.WinDLL("kernel32",use_last_error=True))


def token_sid(token):
    adv,kernel=_libraries()
    adv.GetTokenInformation.argtypes=[w.HANDLE,w.DWORD,w.LPVOID,w.DWORD,ctypes.POINTER(w.DWORD)]
    size=w.DWORD()
    adv.GetTokenInformation(token,1,None,0,ctypes.byref(size))
    if not 0<size.value<65536:
        raise PermissionError("WINDOWS_TOKEN_REQUIRED")
    data=ctypes.create_string_buffer(size.value)
    if not adv.GetTokenInformation(token,1,data,size,ctypes.byref(size)):
        raise PermissionError("WINDOWS_TOKEN_REQUIRED")
    sid=ctypes.cast(data,ctypes.POINTER(ctypes.c_void_p))[0]
    out=w.LPWSTR()
    adv.ConvertSidToStringSidW.argtypes=[w.LPVOID,ctypes.POINTER(w.LPWSTR)]
    if not adv.ConvertSidToStringSidW(sid,ctypes.byref(out)):
        raise PermissionError("WINDOWS_SID_REQUIRED")
    try:
        return out.value
    finally:
        kernel.LocalFree.argtypes=[w.LPVOID]
        kernel.LocalFree(ctypes.cast(out,w.LPVOID))


def current_sid():
    adv,kernel=_libraries()
    kernel.GetCurrentProcess.restype=w.HANDLE
    adv.OpenProcessToken.argtypes=[w.HANDLE,w.DWORD,ctypes.POINTER(w.HANDLE)]
    token=w.HANDLE()
    if not adv.OpenProcessToken(kernel.GetCurrentProcess(),8,ctypes.byref(token)):
        raise PermissionError("WINDOWS_PROCESS_IDENTITY_REQUIRED")
    try:
        return token_sid(token)
    finally:
        kernel.CloseHandle(token)


def verify(nonce, expected_sid, parent=None):
    adv,kernel=_libraries()
    credui=ctypes.WinDLL("credui",use_last_error=True)
    ole=ctypes.WinDLL("ole32",use_last_error=True)

    class Info(ctypes.Structure):
        _fields_=[("cbSize",w.DWORD),("hwndParent",w.HWND),("pszMessageText",w.LPCWSTR),
                  ("pszCaptionText",w.LPCWSTR),("hbmBanner",w.HBITMAP)]
    info=Info()
    info.cbSize=ctypes.sizeof(info)
    if parent is not None:
        info.hwndParent=parent
    info.pszCaptionText="VRAE - actual Windows identity verification"
    info.pszMessageText="Re-enter your Windows account PASSWORD for VRAE. This is not a username-only check. The password stays in Windows memory."
    package=w.ULONG()
    auth=w.LPVOID()
    auth_size=w.ULONG()
    save=w.BOOL(False)
    credui.CredUIPromptForWindowsCredentialsW.argtypes=[
        ctypes.POINTER(Info),w.DWORD,ctypes.POINTER(w.ULONG),w.LPVOID,w.ULONG,
        ctypes.POINTER(w.LPVOID),ctypes.POINTER(w.ULONG),ctypes.POINTER(w.BOOL),w.DWORD]
    status=credui.CredUIPromptForWindowsCredentialsW(
        ctypes.byref(info),0,ctypes.byref(package),None,0,ctypes.byref(auth),
        ctypes.byref(auth_size),ctypes.byref(save),1)
    if status!=0:
        raise PermissionError("WINDOWS_CREDENTIAL_UI_CANCELLED_OR_UNAVAILABLE")
    username=ctypes.create_unicode_buffer(4096)
    domain=ctypes.create_unicode_buffer(4096)
    password=ctypes.create_unicode_buffer(4096)
    nuser=w.DWORD(4096)
    ndomain=w.DWORD(4096)
    npassword=w.DWORD(4096)
    token=w.HANDLE()
    try:
        credui.CredUnPackAuthenticationBufferW.argtypes=[
            w.DWORD,w.LPVOID,w.DWORD,w.LPWSTR,ctypes.POINTER(w.DWORD),
            w.LPWSTR,ctypes.POINTER(w.DWORD),w.LPWSTR,ctypes.POINTER(w.DWORD)]
        if not credui.CredUnPackAuthenticationBufferW(
            0,auth,auth_size,username,ctypes.byref(nuser),domain,ctypes.byref(ndomain),
            password,ctypes.byref(npassword)):
            raise PermissionError("WINDOWS_CREDENTIAL_UNPACK_DENIED")
        user,realm=username.value,domain.value
        if "\\" in user:
            realm,user=user.split("\\",1)
        elif "@" in user:
            realm=None
        elif not realm:
            realm="."
        adv.LogonUserW.argtypes=[w.LPCWSTR,w.LPCWSTR,w.LPVOID,w.DWORD,w.DWORD,ctypes.POINTER(w.HANDLE)]
        if not adv.LogonUserW(user,realm,ctypes.cast(password,w.LPVOID),2,0,ctypes.byref(token)):
            raise PermissionError("WINDOWS_PASSWORD_VERIFICATION_FAILED_WIN32_"+str(ctypes.get_last_error()))
        sid=token_sid(token)
        if sid!=expected_sid or sid!=current_sid():
            raise PermissionError("WINDOWS_ACCOUNT_DOES_NOT_MATCH_ENROLLED_OPERATOR")
        size=w.DWORD()
        adv.GetTokenInformation(token,10,None,0,ctypes.byref(size))
        data=ctypes.create_string_buffer(size.value)
        if not adv.GetTokenInformation(token,10,data,size,ctypes.byref(size)):
            raise PermissionError("WINDOWS_AUTHENTICATION_ID_REQUIRED")
        kernel.GetTickCount64.restype=ctypes.c_ulonglong
        boot=int(time.time()-kernel.GetTickCount64()/1000)
        authentication_id=str(boot)+":"+bytes(data)[8:16].hex()
        return {"verifier":"WINDOWS_LOGONUSER_W","sid":sid,"authentication_id":authentication_id,
                "verified_at":int(time.time()),"nonce":nonce}
    finally:
        ctypes.memset(ctypes.addressof(password),0,ctypes.sizeof(password))
        if auth:
            ctypes.memset(auth,0,auth_size.value)
            ole.CoTaskMemFree.argtypes=[w.LPVOID]
            ole.CoTaskMemFree(auth)
        if token:
            kernel.CloseHandle(token)
