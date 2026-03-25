import streamlit as st
import pandas as pd
import zipfile
import io
import os
from datetime import date
from generator import parse_campaigns, get_campaign_data, generate_all, slugify, LANG_CONFIG

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), 'templates')

GOOGLE_SHEET_ID = '1AVuVVTzcHKLmtx4pT7FVlxIWO5_prHBHY27PDzVQcb0'
GOOGLE_SHEET_GID = '542654988'
GOOGLE_SHEET_URL = f'https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}/export?format=xlsx&gid={GOOGLE_SHEET_GID}'

COUNTDOWN_BASE_URL = 'https://countdown-timer-psi-fawn.vercel.app/api/countdown'

st.set_page_config(page_title='Mailing Campaign Generator', layout='wide')
st.title('📧 Mailing Campaign Generator')

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

# Step 1: Load data from Google Sheets
st.caption(f'[View Google Sheet](https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}/edit?gid={GOOGLE_SHEET_GID}#gid={GOOGLE_SHEET_GID})')

try:
    df = load_google_sheet()
except Exception as e:
    st.error(f'Could not load Google Sheet: {e}')
    st.info('Make sure the sheet is shared as "Anyone with the link can view".')
    st.stop()

if st.button('🔄 Refresh data from Google Sheets'):
    load_google_sheet.clear()
    st.rerun()

campaigns = parse_campaigns(df)

if not campaigns:
    st.error('No campaigns found in the spreadsheet.')
    st.stop()

# Step 2: Select campaign
campaign_displays = [c['display'] for c in campaigns]
selected_display = st.selectbox('Select campaign', campaign_displays)
selected = next(c for c in campaigns if c['display'] == selected_display)
campaign_data = get_campaign_data(df, selected['start_row'])

# Show subject lines for reference
with st.expander('Subject lines (for reference)'):
    for label, key in [('Starter', 'sub'), ('Reminder', 'sub_r'), ('Last Chance', 'sub_lc')]:
        st.markdown(f'**{label}:**')
        cols = st.columns(5)
        for i, lang in enumerate(LANG_CONFIG):
            val = campaign_data.get(key, {}).get(lang, '')
            cols[i].code(val, language=None)

# Step 3: Input fields — auto-fill end date and code from spreadsheet
st.subheader('Campaign settings')

# Parse end date from date_range (e.g. "31.3 - 7.4.2026")
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

# Step 4: Generate
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

    # Preview
    with st.expander('Preview generated files'):
        for filename, content in sorted(files.items()):
            st.markdown(f'**{filename}**')
            has_placeholder = 'Toto je' in content
            has_old_code = '>CODE<' in content or '>CODE\n' in content
            has_old_date = 'X.&nbsp;X' in content
            if has_placeholder or has_old_code or has_old_date:
                st.warning('Unreplaced placeholders detected!')
            st.text(f'Size: {len(content):,} chars')

    # Download ZIP
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        folder = slugify(selected['name'])
        for filename, content in files.items():
            zf.writestr(f'{folder}/{filename}', content)
    zip_buffer.seek(0)

    st.download_button(
        label='📥 Download ZIP',
        data=zip_buffer,
        file_name=f'{slugify(selected["name"])}.zip',
        mime='application/zip',
    )
