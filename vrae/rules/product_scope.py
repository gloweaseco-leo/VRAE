"""Conservative static product-region ownership, not verified SKU identity."""
import re

from .universal_static import ancestors, column_fields, parse, usable


def inside(node, region):
    return node is region or any(parent is region for parent in ancestors(node))


def navigation(node):
    return any(n['tag'] in ('nav', 'aside', 'header', 'footer')
        or n['attrs'].get('role') in ('navigation', 'complementary')
        or bool({'nav', 'navigation', 'menu', 'breadcrumb', 'related', 'recommended',
                 'recommendations'} & set(re.split(r'[^a-z0-9]+',
            ((n['attrs'].get('id') or '') + ' ' + (n['attrs'].get('class') or '')).lower())))
        for n in [node, *ancestors(node)])


def owned(node, name, region, nodes):
    if navigation(node) or not inside(node, region):
        return False
    if name['tag'] not in ('h1', 'h2', 'h3', 'h4'):
        # Explicit name cell: only the same first-listed table row context.
        return region['tag'] == 'table'
    # Another heading starts a different/unknown content block. Do not assign
    # its text to the current product, even when it shares a main/page wrapper.
    headings = [n for n in nodes if n['tag'] in ('h1', 'h2', 'h3', 'h4')
                and usable(n) and not navigation(n) and inside(n, region)
                and n['start'] <= node['start']]
    return bool(headings) and headings[-1] is name


def extract(raw, *, excluded_names=()):
    parser = parse(raw)
    if any(n['tag'] == 'base' and 'href' in n['attrs'] for n in parser.nodes):
        raise ValueError('STATIC_PRODUCT_SCOPE_AMBIGUOUS')
    nodes = [n for n in parser.nodes if usable(n) and not navigation(n)]
    fields = field_nodes(nodes)
    names = [n for n in nodes if n['tag'] == 'h1' and n['text'].strip() not in excluded_names]
    if len(names) != 1:
        # A uniquely labelled name in the supported table is stronger than a
        # page/menu heading. It remains seller-stated, not verified identity.
        identities = [(k, v) for k, v in fields if ' '.join(k['text'].split()).casefold()
                      in ('item', 'product', 'product name', 'productname')]
        if len(identities) != 1:
            raise ValueError('STATIC_PRODUCT_SCOPE_AMBIGUOUS')
        name = identities[0][1]
        region = next((a for a in ancestors(name) if a['tag'] == 'table'), None)
        if region is None or region['end'] is None:
            raise ValueError('STATIC_PRODUCT_SCOPE_AMBIGUOUS')
        fields = [(k, v) for k, v in fields if inside(k, region) and inside(v, region)]
        return parser, name, fields, [], region
    name = names[0]
    regions = [n for n in ancestors(name) if n['tag'] in ('div', 'section', 'article', 'main')
               and not navigation(n)]
    # Closest common structural region, rather than all paragraphs in <main>.
    region = next((n for n in regions if any(inside(k, n) and inside(v, n)
                  for k, v in fields)), None)
    if region is None:
        region = next((n for n in regions if any(p['tag'] == 'p' and usable(p)
                      and inside(p, n) and not navigation(p) for p in parser.nodes)), None)
    if region is None or region['end'] is None:
        raise ValueError('STATIC_PRODUCT_SCOPE_AMBIGUOUS')
    fields = [(k, v) for k, v in fields
              if owned(k, name, region, parser.nodes) and owned(v, name, region, parser.nodes)]
    descriptions = [n for n in parser.nodes if n['tag'] == 'p' and usable(n)
        and len(n['text'].strip()) >= 20 and owned(n, name, region, parser.nodes)
        and not any(c['tag'] == 'a' for c in [n, *descendants(n)])]
    return parser, name, fields, descriptions[:2], region


def field_nodes(nodes):
    fields = list(column_fields(nodes))
    for node in nodes:
        cells = [n for n in node['children'] if n['tag'] in ('td', 'th')]
        if (node['tag'] == 'tr' and len(cells) == 2 and all(usable(n) for n in cells)
                and len(cells[0]['text'].strip()) <= 120):
            fields.append((cells[0], cells[1]))
        if node['tag'] == 'dt':
            siblings = node['parent']['children'] if node['parent'] else []
            index = next(i for i, n in enumerate(siblings) if n is node)
            if index + 1 < len(siblings) and siblings[index + 1]['tag'] == 'dd' and usable(siblings[index + 1]):
                fields.append((node, siblings[index + 1]))
        if node['tag'] in ('li', 'p') and node['direct_text'].strip().endswith(':'):
            children = [n for n in node['children'] if usable(n)]
            label = node['direct_text'].strip()
            if len(children) == 1 and len(label) <= 120 and children[0]['tag'] in ('span', 'strong', 'b'):
                fields.append(({**node, 'text': label}, children[0]))
    if len(fields) > 64:
        raise ValueError('STATIC_FIELD_BOUND')
    return fields


def descendants(node):
    for child in node['children']:
        yield child
        yield from descendants(child)
