"""Bounded source values from replayed product citations, never raw page content."""
import re
import unicodedata

from vrae.interpretation import guard

VERSION = 'qwen-product-values-1.0.0'
SCOPED_VERSION = 'qwen-product-values-1.1.0'
ROLES = {'NAME', 'DESCRIPTION', 'SPEC_LABEL', 'SPEC_VALUE'}
PRIVATE = re.compile(
    r'https?\s*:|www\s*\.|@|(?:[a-z0-9-]+\.)+(?:com|net|org|cn|io)\b|'
    r'\b(?:e-?mail|tel(?:ephone)?|mobile|whats?app|wechat|address|contact|'
    r'password|secret|api[ _-]?key|bearer)\b|'
    r'(?:\+?\d[\s().-]*){8,}|[A-Za-z0-9_-]{48,}|'
    r'\b[A-Za-z0-9][\w.+-]*\s*(?:\[at\]|\(at\))\s*\w+|'
    r'邮箱|电话|手机|微信|联系人|地址', re.I)


def value(fact):
    """Withhold the entire field if unsafe; never truncate into a different fact."""
    if fact['rule_id'] != 'INFO-01':
        return None
    citation = fact['source']['citation']
    if citation.get('fact_role') not in ROLES:
        return None
    text = citation.get('text')
    if type(text) is not str:
        return None
    text = unicodedata.normalize('NFKC', text)
    if (any(unicodedata.category(c).startswith('C') and c not in '\n\r\t' for c in text)
            or '<' in text or '>' in text or PRIVATE.search(text)
            or guard._contains_instruction(text)):
        return None
    text = ' '.join(text.split())
    cap = 240 if citation['fact_role'] == 'DESCRIPTION' else 160
    return text if 1 <= len(text) <= cap else None


def choose(rows, entries, *, scoped=False):
    """Keep name/description and complete label-value pairs for at most two pages."""
    selected: list[dict] = []
    pages: list[str] = []
    for row in rows:
        if row['type'] != 'GUARD_LITERAL' or 'source_value' not in row:
            continue
        citation = entries[row['ref']]['fact']['source']['citation']
        page = citation.get('product_scope_ref') if scoped else citation['snapshot_ref']
        if scoped and (type(page) is not str or not re.fullmatch('ps-[0-9a-f]{64}', page)):
            continue
        if page not in pages and len(pages) < 2:
            pages.append(page)
    for page in pages:
        relevant = [r for r in rows if r['type'] == 'GUARD_LITERAL' and 'source_value' in r
                    and entries[r['ref']]['fact']['source']['citation'].get(
                        'product_scope_ref' if scoped else 'snapshot_ref') == page]
        if scoped and not any(r['source_fact_role'] == 'NAME' for r in relevant):
            continue
        for role, limit in (('NAME', 1), ('DESCRIPTION', 2)):
            selected.extend([r for r in relevant if r['source_fact_role'] == role][:limit])
        pairs: dict[int, dict] = {}
        for row in relevant:
            c = entries[row['ref']]['fact']['source']['citation']
            if c['fact_role'] in ('SPEC_LABEL', 'SPEC_VALUE'):
                pairs.setdefault(c['field_index'], {})[c['fact_role']] = row
        for _, pair in sorted(pairs.items())[:4]:
            if set(pair) == {'SPEC_LABEL', 'SPEC_VALUE'}:
                selected.extend([pair['SPEC_LABEL'], pair['SPEC_VALUE']])
    return selected
