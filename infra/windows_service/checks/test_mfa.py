"""Cryptographic TOTP/replay tests; never substituted for live Windows password verification."""
import base64
import pytest
from infra.windows_service.mfa import Store,totp


def primary(sid,nonce,now,identifier):
    return {"verifier":"WINDOWS_LOGONUSER_W","sid":sid,"authentication_id":identifier,
            "verified_at":int(now),"nonce":nonce}


def test_rfc6238_known_time_vector():
    seed=base64.b32encode(b"12345678901234567890").decode()
    assert totp(seed,59//30)=="287082"


def test_actual_primary_evidence_required_and_totp_is_not_sufficient(tmp_path):
    tmp_path.chmod(0o700)
    state=Store(tmp_path/"mfa.sqlite",lambda:600)
    begin=state.begin("S-1-5-test",True)
    value=primary("S-1-5-test",begin["nonce"],600,"one")
    for bad in ({**value,"verifier":"USERNAME_ONLY"},{**value,"verified_at":0},{**value,"sid":"other"}):
        with pytest.raises(PermissionError):
            state.finish(bad,totp(begin["seed"],20),True)
    assert state.path.stat().st_mode&0o077==0


def test_pairing_primary_and_time_step_replay_survive_restart(tmp_path):
    tmp_path.chmod(0o700)
    clock=[600]
    path=tmp_path/"mfa.sqlite"
    state=Store(path,lambda:clock[0])
    begin=state.begin("S-1-5-test",True)
    code=totp(begin["seed"],20)
    first=primary("S-1-5-test",begin["nonce"],600,"auth-1")
    assert state.finish(first,code,True)["sid_sha256"]
    with pytest.raises(PermissionError,match="REPLAY"):
        state.finish(first,code,True)
    next_login=state.begin("S-1-5-test")
    with pytest.raises(PermissionError,match="PRIMARY_AUTHENTICATION_REPLAY"):
        state.finish(primary("S-1-5-test",next_login["nonce"],600,"auth-1"),code)
    with pytest.raises(PermissionError,match="TIME_STEP_REPLAY"):
        state.finish(primary("S-1-5-test",next_login["nonce"],600,"auth-2"),code)
    clock[0]=630
    state=Store(path,lambda:clock[0])
    login=state.begin("S-1-5-test")
    assert state.finish(primary("S-1-5-test",login["nonce"],630,"auth-3"),
                        totp(begin["seed"],21),report_nonces=["actual-report-nonce-123456"])["verified_at"]==630
    again=state.begin("S-1-5-test")
    with pytest.raises(PermissionError,match="TIME_STEP_REPLAY"):
        Store(path,lambda:clock[0]).finish(primary("S-1-5-test",again["nonce"],630,"auth-4"),
                                          totp(begin["seed"],21))


def test_repeated_bad_phone_codes_lock_the_local_operator(tmp_path):
    tmp_path.chmod(0o700)
    state=Store(tmp_path/"mfa.sqlite",lambda:600)
    begin=state.begin("S-1-5-test",True)
    actual=totp(begin["seed"],20)
    bad="111111" if actual!="111111" else "222222"
    p=primary("S-1-5-test",begin["nonce"],600,"primary")
    for _ in range(5):
        with pytest.raises(PermissionError,match="TOTP_VERIFICATION_FAILED"):
            state.finish(p,bad,True)
    with pytest.raises(PermissionError,match="RATE_LIMITED"):
        state.finish(p,actual,True)


def test_pairing_retry_keeps_pending_phone_key_but_invalidates_old_challenge(tmp_path):
    tmp_path.chmod(0o700)
    state=Store(tmp_path/"mfa.sqlite",lambda:600)
    first=state.begin("S-1-5-test",True)
    retry=state.begin("S-1-5-test",True)
    assert first["seed"]==retry["seed"] and first["nonce"]!=retry["nonce"]
    with pytest.raises(PermissionError,match="REPLAY_OR_EXPIRY"):
        state.finish(primary("S-1-5-test",first["nonce"],600,"primary-1"),totp(first["seed"],20),True)
    state.finish(primary("S-1-5-test",retry["nonce"],600,"primary-2"),totp(retry["seed"],20),True)
    with pytest.raises(PermissionError,match="MUST_NOT_BE_REPLACED"):
        state.begin("S-1-5-test",True)
