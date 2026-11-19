"""Explicit AI consent is not inferred from legacy notice-only consent."""
from infra.windows_service.intake import processing_consent,CONSENT,MODEL_CONSENT


def test_legacy_notice_cannot_enable_provider_processing():
    assert processing_consent(CONSENT,"https://example.org") is None


def test_explicit_model_consent_is_provider_region_and_origin_bound():
    a=processing_consent(MODEL_CONSENT,"https://example.org")
    b=processing_consent(MODEL_CONSENT,"https://other.example.org")
    assert a['consent']=='EXPLICITLY_ACKNOWLEDGED'
    assert a['provider']=='aliyun-bailian-beijing' and a['region']=='cn-beijing'
    assert a['data_scope']=='MINIMIZED_TYPED_EVIDENCE_NO_RAW_HTML_PII'
    assert a['consent_reference']!=b['consent_reference']
