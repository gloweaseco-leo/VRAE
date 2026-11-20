"""Regression for an actual live failure; fixture run is not public acceptance."""
from integration.industry_l2.fixture import capture
from integration.authorized_targets.producer import produce_capture


def test_missing_scalar_comparisons_keep_distinct_unknown_findings():
    raw=b"<html><h1>Partial pump</h1><table><tr><th>Product family</th><td>Pump</td></tr><tr><th>Model</th><td>P40</td></tr><tr><th>Material</th><td>Stainless steel</td></tr></table></html>"
    captured,_=capture(overrides={'/products/pump-p40':raw,'/products/duty-selection':b'<html><h1>Unspecified duty</h1></html>'})
    # Route is held in the existing fixture mapping; ensure the partial record
    # is actually observed before accepting this regression.
    task={'tenant_id':captured.manifest['tenant_id'],'run_id':captured.manifest['run_id'],
          'job_id':'missing-comparison-job','request_id':'missing-comparison-request',
          'event_id':'missing-comparison-event','source_ref':'missing-comparison-source'}
    output=produce_capture(captured,task,'regression-fixture-only','2026-11-15T12:00:00+00:00')
    rows=[a for a in output['diagnosis']['assessments'] if a['model']=='P40' and a['observation']['rule_id']=='IND-DUTY']
    unknown=[a for a in rows if a['observation']['result']=='UNKNOWN']
    assert len(unknown)>=2
    assert len({a['observation']['observation_id'] for a in unknown})==len(unknown)
    assert len({a['finding']['finding_id'] for a in unknown})==len(unknown)
    assert all(not a['observation']['evidence_ids'] and not a['finding']['evidence_ids'] for a in unknown)
    assert output['version']['status']=='REVIEW_REQUIRED'
    ids=output['version']['finding_ids'];assert len(ids)==len(set(ids))
    assert output['external_release'] is False
