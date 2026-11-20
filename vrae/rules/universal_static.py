"""Bounded static text/links; no JavaScript, rendered visibility or absence claims."""
from html.parser import HTMLParser
import re

VOID = {'meta', 'link', 'br', 'hr', 'img', 'input', 'wbr', 'area', 'col', 'embed',
        'param', 'source', 'track'}
EXCLUDED = {'script', 'style', 'template', 'noscript', 'iframe', 'form', 'svg'}


class Static(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.text = text
        self.lines = text.splitlines(keepends=True)
        self.offsets = [0]
        for line in self.lines:
            self.offsets.append(self.offsets[-1] + len(line))
        self.stack: list[dict] = []
        self.nodes: list[dict] = []
        self.ambiguous = False

    def handle_starttag(self, tag, attrs):
        if len(self.nodes) >= 8192 or len(self.stack) >= 64:
            raise ValueError('STATIC_HTML_BOUND')
        duplicate_attributes = len(attrs) != len(dict(attrs))
        attrs = dict(attrs)
        line, column = self.getpos()
        start = self.offsets[line - 1] + column
        parent = self.stack[-1] if self.stack else None
        hidden = (duplicate_attributes or tag in EXCLUDED or any(k in attrs for k in ('hidden', 'inert'))
            or attrs.get('aria-hidden') == 'true'
            or bool(re.search(r'(?:display\s*:\s*none|visibility\s*:\s*hidden)', attrs.get('style') or '', re.I))
            or bool(parent and parent['excluded']))
        node = {'tag': tag, 'attrs': attrs, 'text': '', 'direct_text': '', 'children': [], 'parent': parent,
            'excluded': hidden, 'start': start, 'end': None, 'line': line, 'column': column,
            'start_tag': self.get_starttag_text()}
        self.nodes.append(node)
        if parent is not None:
            parent['children'].append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        index = next((i for i in range(len(self.stack) - 1, -1, -1)
                      if self.stack[i]['tag'] == tag), None)
        if index is None:
            self.ambiguous = True
            return
        # Omitted optional ends are tolerated; crossing arbitrary nodes is not.
        if any(n['tag'] not in {'p', 'li', 'dt', 'dd', 'td', 'th', 'tr'} for n in self.stack[index + 1:]):
            self.ambiguous = True
        line, column = self.getpos()
        start = self.offsets[line - 1] + column
        end = self.text.find('>', start)
        self.stack[index]['end'] = end + 1 if end >= 0 else None
        del self.stack[index:]

    def handle_data(self, data):
        if self.stack and not self.stack[-1]['excluded']:
            self.stack[-1]['direct_text'] += data
            for node in self.stack:
                if not node['excluded']:
                    node['text'] += data


def parse(raw):
    if len(raw) > 500000:
        raise ValueError('STATIC_HTML_BOUND')
    text = raw.decode('utf-8', errors='strict')
    parser = Static(text)
    parser.feed(text)
    parser.close()
    if parser.ambiguous:
        raise ValueError('STATIC_HTML_AMBIGUOUS')
    return parser


def usable(node):
    return (not node['excluded'] and node['end'] is not None
        and node['end'] - node['start'] <= 8192 and 0 < len(node['text'].strip()) <= 2000)


def cite(parser, node):
    raw = parser.text[node['start']:node['end']]
    return {'text': node['text'].strip(), 'element': {
        'path': '/static/' + node['tag'], 'line': node['line'], 'column': node['column'],
        'start_tag': node['start_tag'], 'raw_element': raw}}


def landmark(node):
    return (node['tag'] in ('main', 'article') or node['attrs'].get('role') == 'main'
        or node['attrs'].get('id') in ('main', 'content', 'main-content', 'main_content'))


def product(raw, *, excluded_names=()):
    parser = parse(raw)
    nodes = [n for n in parser.nodes if usable(n)
             and not any(a['tag'] in ('nav', 'header', 'footer', 'aside') for a in ancestors(n))]
    names = [n for n in nodes if n['tag'] == 'h1']
    if len(names) > 1:
        names = [n for n in names if n['text'].strip() not in excluded_names]
    if len(names) != 1:
        raise ValueError('STATIC_PRODUCT_NAME_AMBIGUOUS')
    region = next((a for a in ancestors(names[0]) if landmark(a)), None)
    if region is not None:
        nodes = [n for n in nodes if n is region or any(a is region for a in ancestors(n))]
    fields = []
    for node in nodes:
        cells = [n for n in node['children'] if n['tag'] in ('td', 'th')]
        if node['tag'] == 'tr' and len(cells) == 2 and all(usable(n) for n in cells) and len(cells[0]['text'].strip()) <= 120:
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
    descriptions = [n for n in nodes if n['tag'] == 'p' and len(n['text'].strip()) >= 20
        and ('description' in (n['attrs'].get('itemprop') or '')
             or any(landmark(a) and not a['excluded'] for a in ancestors(n)))]
    return parser, names[0], fields, descriptions[:2]


def ancestors(node):
    parent = node['parent']
    while parent is not None:
        yield parent
        parent = parent['parent']
