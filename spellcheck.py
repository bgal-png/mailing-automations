import re
import requests
from html.parser import HTMLParser

LANG_CODES = {
    'cz': 'sk-SK',  # Czech not supported by LanguageTool, Slovak is closest
    'de': 'de-DE',
    'es': 'es-ES',
    'bg': 'auto',  # Bulgarian not supported, use auto-detect
    'gr': 'el-GR',
}

LANG_SUPPORTED = {
    'cz': False,
    'de': True,
    'es': True,
    'bg': False,
    'gr': True,
}

# LanguageTool free API limit is ~20KB
MAX_TEXT_LENGTH = 20000

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
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    }
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    return extract_text_from_html(resp.text)


def clean_text(text):
    """Clean pasted text: remove HTML entities, excessive whitespace, non-printable chars."""
    # Decode common HTML entities
    text = text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    # Remove any remaining HTML tags that might have been pasted
    text = re.sub(r'<[^>]+>', ' ', text)
    # Remove URLs (spell checkers choke on these)
    text = re.sub(r'https?://\S+', '', text)
    # Remove email addresses
    text = re.sub(r'\S+@\S+\.\S+', '', text)
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def spellcheck(text, lang='cz'):
    lt_lang = LANG_CODES.get(lang, 'auto')

    # Clean the text first
    text = clean_text(text)

    if not text.strip():
        return {'error': 'No text to check after cleaning.', 'matches': []}

    # Truncate if too long for free API
    truncated = False
    if len(text) > MAX_TEXT_LENGTH:
        text = text[:MAX_TEXT_LENGTH]
        truncated = True

    # Force the language — never fall back to auto (except BG)
    # LanguageTool auto-detect confuses Czech with Slovak
    params = {
        'text': text,
        'language': lt_lang,
        'disabledRules': 'WHITESPACE_RULE',
    }

    try:
        resp = requests.post(LANGUAGETOOL_API, data=params, timeout=30)
        if resp.status_code == 400:
            # Return the actual error for debugging
            try:
                error_detail = resp.json().get('message', resp.text[:200])
            except Exception:
                error_detail = resp.text[:200]
            return {'error': f'API rejected request: {error_detail}', 'matches': []}
        resp.raise_for_status()
        result = resp.json()
    except requests.exceptions.HTTPError as e:
        return {'error': str(e), 'matches': []}
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

    lang_info = result.get('language', {})
    detected_name = lang_info.get('name', lt_lang)
    detected_code = lang_info.get('detectedLanguage', {}).get('code', lang_info.get('code', ''))
    requested_lang = lt_lang

    return {
        'language': detected_name,
        'detected_code': detected_code,
        'requested_lang': requested_lang,
        'matches': matches,
        'truncated': truncated,
    }
