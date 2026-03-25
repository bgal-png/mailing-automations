import os
import re
import requests
from html.parser import HTMLParser

# LanguageTool config (DE, ES, GR)
LANG_CODES_LT = {
    'de': 'de-DE',
    'es': 'es-ES',
    'gr': 'el-GR',
}

# Hunspell config (CZ, BG)
LANG_CODES_HUNSPELL = {
    'cz': 'cs_CZ',
    'bg': 'bg_BG',
}

LANG_SUPPORTED = {
    'cz': True,
    'de': True,
    'es': True,
    'bg': True,
    'gr': True,
}

LANG_ENGINE = {
    'cz': 'Hunspell',
    'de': 'LanguageTool',
    'es': 'LanguageTool',
    'bg': 'Hunspell',
    'gr': 'LanguageTool',
}

MAX_TEXT_LENGTH = 20000
LANGUAGETOOL_API = 'https://api.languagetool.org/v2/check'
DICTIONARIES_DIR = os.path.join(os.path.dirname(__file__), 'dictionaries')

# Cache loaded dictionaries
_hunspell_dicts = {}


def _get_hunspell_dict(lang):
    if lang not in _hunspell_dicts:
        from spylls.hunspell import Dictionary
        dict_code = LANG_CODES_HUNSPELL[lang]
        path = os.path.join(DICTIONARIES_DIR, dict_code)
        _hunspell_dicts[lang] = Dictionary.from_files(path)
    return _hunspell_dicts[lang]


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
    }
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    return extract_text_from_html(resp.text)


def clean_text(text):
    text = text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'\S+@\S+\.\S+', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _spellcheck_hunspell(text, lang):
    """Spell check using Hunspell (for CZ and BG)."""
    d = _get_hunspell_dict(lang)

    # Split into words, keeping track of positions
    matches = []
    # Find all word tokens with their positions
    for m in re.finditer(r'[^\s\.,;:!?\(\)\[\]\{\}"\'«»„"…–—/\d]+', text):
        word = m.group()
        offset = m.start()

        # Skip very short words, numbers, codes
        if len(word) <= 1:
            continue
        # Skip words that look like codes or abbreviations (all caps, mixed with digits)
        if word.isupper() and len(word) <= 5:
            continue

        if not d.lookup(word):
            # Get suggestions (limit to avoid slowness)
            suggestions = []
            try:
                for i, s in enumerate(d.suggest(word)):
                    suggestions.append(s)
                    if i >= 4:
                        break
            except Exception:
                pass

            matches.append({
                'message': f'Possible spelling mistake: "{word}"',
                'short_message': 'Spelling',
                'word': word,
                'offset': offset,
                'length': len(word),
                'replacements': suggestions,
                'rule': 'HUNSPELL_SPELL',
                'category': 'TYPOS',
            })

    return {
        'language': f'{"Czech" if lang == "cz" else "Bulgarian"} (Hunspell)',
        'detected_code': LANG_CODES_HUNSPELL[lang],
        'requested_lang': LANG_CODES_HUNSPELL[lang],
        'engine': 'Hunspell',
        'matches': matches,
        'truncated': False,
    }


def _spellcheck_languagetool(text, lang):
    """Spell check using LanguageTool API (for DE, ES, GR)."""
    lt_lang = LANG_CODES_LT.get(lang, 'auto')

    truncated = False
    if len(text) > MAX_TEXT_LENGTH:
        text = text[:MAX_TEXT_LENGTH]
        truncated = True

    params = {
        'text': text,
        'language': lt_lang,
        'disabledRules': 'WHITESPACE_RULE',
    }

    try:
        resp = requests.post(LANGUAGETOOL_API, data=params, timeout=30)
        if resp.status_code == 400:
            try:
                error_detail = resp.json().get('message', resp.text[:200])
            except Exception:
                error_detail = resp.text[:200]
            return {'error': f'API rejected request: {error_detail}', 'matches': []}
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

    lang_info = result.get('language', {})
    detected_name = lang_info.get('name', lt_lang)
    detected_code = lang_info.get('detectedLanguage', {}).get('code', lang_info.get('code', ''))

    return {
        'language': detected_name,
        'detected_code': detected_code,
        'requested_lang': lt_lang,
        'engine': 'LanguageTool',
        'matches': matches,
        'truncated': truncated,
    }


def spellcheck(text, lang='cz'):
    text = clean_text(text)

    if not text.strip():
        return {'error': 'No text to check after cleaning.', 'matches': []}

    if lang in LANG_CODES_HUNSPELL:
        return _spellcheck_hunspell(text, lang)
    else:
        return _spellcheck_languagetool(text, lang)
