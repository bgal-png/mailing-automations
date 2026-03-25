import streamlit as st
import pandas as pd
import zipfile
import io
import os
from datetime import date
from generator import parse_campaigns, get_campaign_data, generate_all, slugify, LANG_CONFIG
from spellcheck import spellcheck, fetch_text_from_url, extract_text_from_html, LANG_SUPPORTED, LANG_ENGINE

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), 'templates')

GOOGLE_SHEET_ID = '1AVuVVTzcHKLmtx4pT7FVlxIWO5_prHBHY27PDzVQcb0'
GOOGLE_SHEET_GID = '542654988'
GOOGLE_SHEET_URL = f'https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}/export?format=xlsx&gid={GOOGLE_SHEET_GID}'

COUNTDOWN_BASE_URL = 'https://countdown-timer-psi-fawn.vercel.app/api/countdown'

st.set_page_config(page_title='Mailing Campaign Generator', layout='wide')
st.title('Mailing Campaign Generator')

# Load templates
@st.cache_data
def load_templates():
    templates = {}
    for lang, cfg in LANG_CONFIG.items():
        path = os.path.join(TEMPLATES_DIR, cfg['template_file'])
        with open(path, 'r', encoding='utf-8') as f:
            templates[lang] = f.read()
    return templates

@st.cache_data(ttl=300)
def load_google_sheet():
    df = pd.read_excel(GOOGLE_SHEET_URL, header=None)
    return df

templates = load_templates()

# --- TABS ---
tab_generator, tab_spellcheck = st.tabs(['Campaign Generator', 'Spell Checker'])

# ============================================================
# TAB 1: Campaign Generator
# ============================================================
with tab_generator:
    st.caption(f'[View Google Sheet](https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}/edit?gid={GOOGLE_SHEET_GID}#gid={GOOGLE_SHEET_GID})')

    try:
        df = load_google_sheet()
    except Exception as e:
        st.error(f'Could not load Google Sheet: {e}')
        st.info('Make sure the sheet is shared as "Anyone with the link can view".')
        st.stop()

    if st.button('Refresh data from Google Sheets'):
        load_google_sheet.clear()
        st.rerun()

    campaigns = parse_campaigns(df)

    if not campaigns:
        st.error('No campaigns found in the spreadsheet.')
        st.stop()

    campaign_displays = [c['display'] for c in campaigns]
    selected_display = st.selectbox('Select campaign', campaign_displays)
    selected = next(c for c in campaigns if c['display'] == selected_display)
    campaign_data = get_campaign_data(df, selected['start_row'])

    with st.expander('Subject lines (for reference)'):
        for label, key in [('Starter', 'sub'), ('Reminder', 'sub_r'), ('Last Chance', 'sub_lc')]:
            st.markdown(f'**{label}:**')
            cols = st.columns(5)
            for i, lang in enumerate(LANG_CONFIG):
                val = campaign_data.get(key, {}).get(lang, '')
                cols[i].caption(lang.upper())
                cols[i].code(val, language=None)

    st.subheader('Campaign settings')

    default_date = date.today()
    if selected.get('date_range'):
        import re as _re
        m = _re.search(r'(\d+)\.(\d+)\.(\d{4})\s*$', selected['date_range'])
        if m:
            try:
                default_date = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            except ValueError:
                pass

    col1, col2 = st.columns(2)
    with col1:
        end_date = st.date_input('Campaign end date', value=default_date)
    with col2:
        discount_code = st.text_input('Discount code', value=selected.get('code', ''), placeholder='e.g. sun20')

    st.subheader('Banner / CTA links (one per language)')
    st.caption('Just paste the slug, e.g. `vybrane-slunecni-bryle` → `https://www.domain.com/vybrane-slunecni-bryle.html`')
    banner_links = {}
    cols = st.columns(5)
    for i, lang in enumerate(LANG_CONFIG):
        domain = LANG_CONFIG[lang]['domain']
        cols[i].markdown(f'[**{lang.upper()} ({domain})**](https://www.{domain}/)')
        path_input = cols[i].text_input(
            f'{lang.upper()} path',
            placeholder=f'your-page-slug',
            key=f'link_{lang}',
            label_visibility='collapsed'
        )
        if path_input:
            slug = path_input.strip().strip('/')
            if slug.endswith('.html'):
                slug = slug[:-5]
            banner_links[lang] = f'https://www.{domain}/{slug}.html'
        else:
            banner_links[lang] = ''

    if st.button('Generate campaign emails', type='primary'):
        if not discount_code:
            st.error('Please enter a discount code.')
            st.stop()

        missing_links = [lang.upper() for lang, link in banner_links.items() if not link]
        if missing_links:
            st.error(f'Missing banner links for: {", ".join(missing_links)}')
            st.stop()

        with st.spinner('Generating 15 email files...'):
            countdown_urls = {}
            for lang in LANG_CONFIG:
                countdown_urls[lang] = f'{COUNTDOWN_BASE_URL}?end={end_date.isoformat()}T23:59:59&lang={lang}'
            files = generate_all(
                templates, campaign_data, end_date,
                discount_code, banner_links, countdown_urls,
                selected['name']
            )

        st.success(f'Generated {len(files)} files!')

        with st.expander('Preview generated files'):
            for filename, content in sorted(files.items()):
                st.markdown(f'**{filename}**')
                has_placeholder = 'Toto je' in content
                has_old_code = '>CODE<' in content or '>CODE\n' in content
                has_old_date = 'X.&nbsp;X' in content
                if has_placeholder or has_old_code or has_old_date:
                    st.warning('Unreplaced placeholders detected!')
                st.text(f'Size: {len(content):,} chars')

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            folder = slugify(selected['name'])
            for filename, content in files.items():
                zf.writestr(f'{folder}/{filename}', content)
        zip_buffer.seek(0)

        st.download_button(
            label='Download ZIP',
            data=zip_buffer,
            file_name=f'{slugify(selected["name"])}.zip',
            mime='application/zip',
        )

# ============================================================
# TAB 2: Spell Checker
# ============================================================
with tab_spellcheck:
    st.subheader('Campaign Spell Checker')
    st.caption('CZ & BG use Hunspell (spelling) · DE, ES & GR use LanguageTool (spelling + grammar)')

    LANG_LABELS = {'cz': 'Czech', 'de': 'German', 'es': 'Spanish', 'bg': 'Bulgarian', 'gr': 'Greek'}

    check_lang = st.selectbox(
        'Language',
        options=list(LANG_LABELS.keys()),
        format_func=lambda x: f'{x.upper()} — {LANG_LABELS[x]} ({LANG_ENGINE[x]})',
        key='spellcheck_lang'
    )

    st.info('**How to use:** Open the rendered email in your browser → select all text (Ctrl+A) → copy (Ctrl+C) → paste below (Ctrl+V)')

    text_to_check = st.text_area(
        'Paste email text here',
        height=250,
        placeholder='Select all text from your rendered email and paste it here...',
        key='spellcheck_text'
    )

    if st.button('Check spelling', type='primary', key='spellcheck_btn'):
        if not text_to_check.strip():
            st.error('Please enter some text to check.')
        else:
            with st.spinner('Checking spelling and grammar...'):
                result = spellcheck(text_to_check, check_lang)

            if 'error' in result:
                st.error(f'Spell check error: {result["error"]}')
            else:
                matches = result['matches']
                detected_lang = result.get('language', '')
                engine = result.get('engine', '')
                if result.get('truncated'):
                    st.info('Text was truncated to 20,000 characters (free API limit).')

                st.caption(f'Engine: **{engine}** | Checked as: **{detected_lang}**')

                if not matches:
                    st.success(f'No issues found!')
                else:
                    st.warning(f'Found **{len(matches)}** issue(s)')

                    for i, m in enumerate(matches):
                        with st.container():
                            severity_icon = '🔴' if m['category'] == 'TYPOS' else '🟡'
                            st.markdown(f'{severity_icon} **Issue {i+1}:** `{m["word"]}`')

                            col_a, col_b = st.columns([2, 3])
                            with col_a:
                                st.markdown(f'**Category:** {m["category"]}')
                                if m['replacements']:
                                    suggestions = ', '.join(f'`{r}`' for r in m['replacements'])
                                    st.markdown(f'**Suggestions:** {suggestions}')
                            with col_b:
                                st.markdown(f'**Message:** {m["message"]}')

                            # Show context
                            offset = m['offset']
                            length = m['length']
                            start = max(0, offset - 40)
                            end = min(len(text_to_check), offset + length + 40)
                            context = text_to_check[start:end]
                            word_start = offset - start
                            word_end = word_start + length
                            highlighted = (
                                context[:word_start]
                                + '**→' + context[word_start:word_end] + '←**'
                                + context[word_end:]
                            )
                            st.markdown(f'**Context:** ...{highlighted}...')
                            st.divider()
