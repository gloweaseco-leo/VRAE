"""Map actual browser metrics plus separately written image-reading notes only."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--candidate',required=True)
    parser.add_argument('--memo',required=True)
    args = parser.parse_args()
    run = HERE/'runs'/args.candidate
    out = run/'observations.json'
    assert not out.exists(), 'Preserve actual dossier version'
    raw = json.loads((run/'browser/browser-observations.json').read_text(encoding='utf-8'))
    memo = json.loads(Path(args.memo).read_text(encoding='utf-8'))
    source = json.loads((run/'browser/source.json').read_text(encoding='utf-8'))
    assert raw['candidate_sha'] == memo['candidate_sha'] == source['candidate_sha'] == args.candidate
    assert raw['status'] == 'OBSERVATIONS_CAPTURED_NOT_ACCEPTANCE' and not raw['exceptions']
    assert source['original_quotes_verified'] and source['native_build_load_render_both_python']
    assert memo['reviewer_type'] == 'CODEX1_LOCAL_QA_IMAGE_READING_NOT_CUSTOMER_APPROVAL'
    assert memo['images_actually_inspected'] is True and memo['not_report_approval'] is True
    views = {}
    clicks = []
    for width in (375,1280):
        matches = [v for v in raw['views'] if v['name'] == 'contact-404' and v['width'] == width]
        assert len(matches) == 1
        view = matches[0]
        assert view['html_sha256'] == source['artifacts']['contact-404']['html_sha256']
        assert view['privacy_font_px'] >= 12 and view['body_font_px'] >= 14
        assert view['privacy_above_fold'] and view['scroll_width'] <= view['client_width']+1
        assert not view['external_requests']
        image = run/'browser'/view['screenshot']['file']
        assert hashlib.sha256(image.read_bytes()).hexdigest() == view['screenshot']['sha256']
        views[str(width)] = dict(width=view['width'],external_requests=view['external_requests'],
            screenshot_path=str(image),screenshot_sha256=view['screenshot']['sha256'],
            browser_version=raw['browser']['product'],scroll_width=view['scroll_width'],client_width=view['client_width'],
            body_font_px=view['body_font_px'],main_heading_count=view['main_heading_count'],
            visible_layer_labels=view['visible_layer_labels'],privacy_above_fold=view['privacy_above_fold'],
            privacy_font_px=view['privacy_font_px'])
        for click in view['citation_clicks']:
            assert click['resolved'] and click['quote_matches_companion_document']
            clicks.append(dict(href=click['href'],internal=click['href'].startswith('#'),
                resolved=click['resolved'],correct_quote=click['quote_matches_companion_document'],
                original_source_byte_replay_verified=source['original_quotes_verified']))
    assert clicks
    spec = importlib.util.spec_from_file_location('v2_dossier_immutable_source',HERE/'support.py')
    support = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(support)
    text = ''.join(support.v1.HtmlAudit((run/'browser/contact-404.html').read_bytes()).parts)
    for key in ('reading_memo','scope_memo','value_memo'):
        entry = memo['business_review'][key]
        assert entry['qa_only'] and entry['not_report_approval'] and entry['decision'] == 'QA_OBSERVED_PASS'
        assert entry['observed_quote'] in text and len(entry['reasoning']) >= 80
        assert entry['screenshot_refs']
        for name in entry['screenshot_refs']:
            assert (run/'browser'/name).is_file()
    comp = memo['business_review']['value_memo']['comparison']
    assert comp['one_html_sha256'] == source['artifacts']['contact-404']['html_sha256']
    assert comp['zero_html_sha256'] == source['artifacts']['contact-200']['html_sha256']
    zero_image = Path(comp['zero_screenshot_path'])
    assert hashlib.sha256(zero_image.read_bytes()).hexdigest() == comp['zero_screenshot_sha256']
    result = dict(candidate_sha=args.candidate,html_sha256=source['artifacts']['contact-404']['html_sha256'],
        not_customer_approval=True,capture_tool=raw['capture_tool'],viewports=views,evidence_clicks=clicks,
        business_review=memo['business_review'],raw_browser_sha256=hashlib.sha256((run/'browser/browser-observations.json').read_bytes()).hexdigest(),
        memo_sha256=hashlib.sha256(Path(args.memo).read_bytes()).hexdigest())
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Actual source/image/memo-bound dossier; no native report approval:',args.candidate)


if __name__ == '__main__':
    main()
