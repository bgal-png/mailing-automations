import streamlit as st
import pandas as pd
import zipfile
import io
import os
from datetime import date
from generator import parse_campaigns, get_campaign_data, generate_all, LANG_CONFIG

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), 'templates')

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

templates = load_templates()

# Step 1: Upload Excel
uploaded_file = st.file_uploader('Upload Translations Excel file', type=['xlsx'])

if uploaded_file:
    df = pd.read_excel(uploaded_file, sheet_name='New campaigns', header=None)
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
                cols[i].text_input(f'{lang.upper()}', val, key=f'sub_{key}_{lang}', disabled=True)

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
    banner_links = {}
    cols = st.columns(5)
    for i, lang in enumerate(LANG_CONFIG):
        domain = LANG_CONFIG[lang]['domain']
        banner_links[lang] = cols[i].text_input(
            f'{lang.upper()} ({domain})',
            placeholder=f'https://www.{domain}/...',
            key=f'link_{lang}'
        )

    countdown_url = st.text_input(
        'Countdown timer image URL (for Last Chance)',
        placeholder='https://your-countdown.vercel.app/api/countdown?end=...',
    )

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
            files = generate_all(
                templates, campaign_data, end_date,
                discount_code, banner_links, countdown_url,
                selected_name
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
            from generator import slugify
            folder = slugify(selected_name)
            for filename, content in files.items():
                zf.writestr(f'{folder}/{filename}', content)
        zip_buffer.seek(0)

        from generator import slugify
        st.download_button(
            label='Download ZIP',
            data=zip_buffer,
            file_name=f'{slugify(selected_name)}.zip',
            mime='application/zip',
        )
