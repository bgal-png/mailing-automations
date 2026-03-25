import requests
from html.parser import HTMLParser

LANG_CODES = {
    'cz': 'cs',
    'de': 'de-DE',
    'es': 'es',
    'bg': 'bg',  # LanguageTool doesn't fully support BG, will fall back to auto
    'gr': 'el',
}

LANGUAGETOOL_API = 'https://api.languagetool.org/v2/check'


class HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.result = []
        self.skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.skip = True

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.skip = False

    def handle_data(self, data):
        if not self.skip:
            text = data.strip()
            if text:
                self.result.append(text)

    def get_text(self):
        return ' '.join(self.result)


def extract_text_from_html(html):
    extractor = HTMLTextExtractor()
    extractor.feed(html)
    return extractor.get_text()


def fetch_text_from_url(url):
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    return extract_text_from_html(resp.text)


def spellcheck(text, lang='cz'):
    lt_lang = LANG_CODES.get(lang, 'auto')
    params = {
        'text': text,
        'language': lt_lang,
    }
    # If language might not be supported, use auto-detect
    if lang == 'bg':
        params['language'] = 'auto'

    try:
        resp = requests.post(LANGUAGETOOL_API, data=params, timeout=30)
        resp.raise_for_status()
        result = resp.json()
    except Exception as e:
        return {'error': str(e), 'matches': []}

    matches = []
    for m in result.get('matches', []):
        offset = m['offset']
        length = m['length']
        matches.append({
            'message': m.get('message', ''),
            'short_message': m.get('shortMessage', ''),
            'word': text[offset:offset + length],
            'offset': offset,
            'length': length,
            'replacements': [r['value'] for r in m.get('replacements', [])[:5]],
            'rule': m.get('rule', {}).get('id', ''),
            'category': m.get('rule', {}).get('category', {}).get('name', ''),
        })

    return {
        'language': result.get('language', {}).get('name', lt_lang),
        'matches': matches,
    }
