import re
import pandas as pd

LANG_CONFIG = {
    'cz': {
        'col': 1,
        'domain': 'cocky-online.cz',
        'end_date_template': 'Nabídka končí X.&nbsp;X.&nbsp;2026.',
        'end_date_format': 'Nabídka končí {date}.',
        'cta_placeholder': 'Zobrazit nabídku',
        'template_file': 'cz_template.html',
    },
    'de': {
        'col': 3,
        'domain': 'ihre-kontaktlinsen.de',
        'end_date_template': 'Das Angebot gilt bis zum X.&nbsp;X.&nbsp;2026.\xa0',
        'end_date_format': 'Das Angebot gilt bis zum {date}.',
        'cta_placeholder': 'Angebot anzeigen',
        'template_file': 'de_template.html',
    },
    'es': {
        'col': 4,
        'domain': 'lentes-de-contacto.es',
        'end_date_template': 'Oferta válida hasta el X.&nbsp;X.&nbsp;2026.',
        'end_date_format': 'Oferta válida hasta el {date}.',
        'cta_placeholder': 'Ver oferta',
        'template_file': 'es_template.html',
    },
    'bg': {
        'col': 5,
        'domain': 'leshti.bg',
        'end_date_template': 'Отстъпката е валидна само до X.&nbsp;X.&nbsp;2026.',
        'end_date_format': 'Отстъпката е валидна само до {date}.',
        'cta_placeholder': 'Вижте офертата',
        'template_file': 'bg_template.html',
    },
    'gr': {
        'col': 6,
        'domain': 'mataki.gr',
        'end_date_template': 'Η προσφορά λήγει στις X.&nbsp;X.&nbsp;2026.',
        'end_date_format': 'Η προσφορά λήγει στις {date}.',
        'cta_placeholder': 'Zobrazit nabídku',
        'template_file': 'gr_template.html',
    },
}

BODY_PLACEHOLDER = 'Toto je váš nový textový blok a v něm první odstavec.'


def parse_campaigns(df):
    campaigns = []
    i = 0
    while i < len(df):
        label = str(df.iloc[i, 0]).strip() if pd.notna(df.iloc[i, 0]) else ''
        if label == 'Notes' and (i + 9) < len(df):
            name_cell = df.iloc[i + 1, 1]
            if pd.notna(name_cell):
                full_text = str(name_cell)
                lines = [l.strip() for l in full_text.split('\n') if l.strip()]
                name = lines[0]
                # Extract date range (last line, pattern like "30.4 - 7.5.2026")
                date_range = ''
                code = ''
                for line in lines:
                    if re.search(r'\d+\.?\d*\s*-\s*\d+\.\d+\.\d{4}', line):
                        date_range = line
                    if line.lower().startswith('kód:'):
                        code = line.split(':', 1)[1].strip()
                campaigns.append({
                    'name': name,
                    'start_row': i,
                    'date_range': date_range,
                    'code': code,
                    'display': f'{name}  ({date_range})' if date_range else name,
                })
            i += 10
        else:
            i += 1
    return campaigns


def get_campaign_data(df, start_row):
    data = {}
    rows = {
        'sub': start_row + 2,
        'sub_r': start_row + 3,
        'sub_lc': start_row + 4,
        'text': start_row + 5,
        'text_lc': start_row + 6,
        'banner_text': start_row + 7,
        'button_text': start_row + 8,
        'end_date_text': start_row + 9,
    }
    for key, row_idx in rows.items():
        if row_idx < len(df):
            data[key] = {}
            for lang, cfg in LANG_CONFIG.items():
                val = df.iloc[row_idx, cfg['col']]
                data[key][lang] = str(val) if pd.notna(val) else ''
    return data


def format_date_nbsp(date_obj):
    return f'{date_obj.day}.&nbsp;{date_obj.month}.&nbsp;{date_obj.year}'


def generate_email(template_html, lang, email_type, campaign_data, end_date, discount_code, banner_link, countdown_url='', banner_image_url=''):
    html = template_html
    cfg = LANG_CONFIG[lang]

    # 1. Body text
    if email_type == 'reminder':
        # Remove the entire text block for reminder
        html = re.sub(
            r'<p[^>]*>[\s\S]*?' + re.escape(BODY_PLACEHOLDER) + r'[\s\S]*?</p>',
            '',
            html,
            count=1
        )
    else:
        text_key = 'text' if email_type == 'starter' else 'text_lc'
        body_text = campaign_data.get(text_key, {}).get(lang, '')
        body_text_html = body_text.replace('\n', '<br>')
        # Replace placeholder with properly styled text (Helvetica, 16px, not bold)
        new_text_block = (
            f'<span style="font-family: Helvetica, sans-serif; font-size: 16px;">'
            f'{body_text_html}'
            f'</span>'
        )
        # Replace the bold placeholder with non-bold styled text
        html = re.sub(
            r'<strong>\s*' + re.escape(BODY_PLACEHOLDER) + r'\s*</strong>',
            new_text_block,
            html,
            count=1
        )

    # 2. Hero image - add alt text and link wrapper
    banner_text = campaign_data.get('banner_text', {}).get(lang, '')
    banner_link_with_code = _add_dc_code(banner_link, discount_code)

    # Match hero image (the one with width="600")
    hero_pattern = r'(<img[^>]*height="auto"[^>]*)(width="600"[^>]*>)'
    hero_match = re.search(hero_pattern, html)
    if hero_match:
        full_match = hero_match.group(0)
        # Replace banner image src if provided
        if banner_image_url:
            full_match = re.sub(r'src="[^"]*"', f'src="{banner_image_url}"', full_match)
        # Add alt attribute
        if 'alt="' not in full_match:
            new_img = full_match.replace('height="auto"', f'height="auto" alt="{banner_text}"')
        else:
            new_img = re.sub(r'alt="[^"]*"', f'alt="{banner_text}"', full_match)

        # Check if already wrapped in <a>, if not wrap it
        pre_context = html[max(0, hero_match.start() - 100):hero_match.start()]
        if '<a ' not in pre_context.split('>')[-1] and '<a ' not in pre_context[-50:]:
            new_img = f'<a href="{banner_link_with_code}" target="_blank" style="text-decoration:none;">{new_img}</a>'

        html = html[:hero_match.start()] + new_img + html[hero_match.end():]

    # 3. CTA button - replace text and href
    button_text = campaign_data.get('button_text', {}).get(lang, '')
    if button_text:
        html = html.replace(cfg['cta_placeholder'], button_text)

    # Replace CTA href - find the <a> tag with FBA157 button
    cta_patterns = [
        (r'(background:\s*#FBA157[^"]*"[^>]*>[\s\S]*?<a\s+href=")([^"]+)(")', None),
        (r'(<a\s+href=")([^"]+)("[\s\S]*?background:\s*#FBA157)', None),
    ]
    # Simpler approach: replace known CTA hrefs
    known_cta_hrefs = [
        'https://www.cocky-online.cz/',
        'https://www.ihre-kontaktlinsen.de/',
        'https://www.lentes-de-contacto.es/',
        'https://google.com',
    ]
    for old_href in known_cta_hrefs:
        if old_href in html:
            # Only replace in the CTA button context (near FBA157)
            idx = html.find('#FBA157')
            if idx >= 0:
                # Find the href near the button
                search_area = html[idx:idx+1000]
                if f'href="{old_href}"' in search_area:
                    html = html[:idx] + search_area.replace(
                        f'href="{old_href}"',
                        f'href="{banner_link_with_code}"'
                    ) + html[idx+1000:]

    # 4. End date
    date_str = format_date_nbsp(end_date)
    if email_type == 'lastchance':
        lc_date_text = campaign_data.get('end_date_text', {}).get(lang, '')
        if lc_date_text:
            end_date_line = f'{lc_date_text}{date_str}).'
        else:
            end_date_line = cfg['end_date_format'].format(date=date_str)
        # Replace the template end date text
        if cfg['end_date_template'] in html:
            html = html.replace(cfg['end_date_template'], end_date_line)
        else:
            # Fallback: replace just the X.&nbsp;X pattern
            html = html.replace('X.&nbsp;X.&nbsp;2026', f'{end_date.day}.&nbsp;{end_date.month}.&nbsp;{end_date.year}')
    else:
        standard_date_line = cfg['end_date_format'].format(date=date_str)
        if cfg['end_date_template'] in html:
            html = html.replace(cfg['end_date_template'], standard_date_line)
        else:
            html = html.replace('X.&nbsp;X.&nbsp;2026', f'{end_date.day}.&nbsp;{end_date.month}.&nbsp;{end_date.year}')

    # 5. Discount code
    html = re.sub(
        r'(<strong>\s*)CODE(\s*</strong>)',
        rf'\g<1>{discount_code}\g<2>',
        html,
        count=1
    )

    # 6. dc_code on all domain links
    domain = cfg['domain']
    html = html.replace('dc_code=code', f'dc_code={discount_code}')
    # Add dc_code to domain links that don't have it
    def add_dc_code_to_link(match):
        url = match.group(1)
        if 'dc_code=' in url:
            return match.group(0)
        if '?' in url:
            return f'href="{url}&dc_code={discount_code}"'
        return f'href="{url}?dc_code={discount_code}"'

    html = re.sub(
        rf'href="(https?://(?:www\.)?{re.escape(domain)}[^"]*)"',
        add_dc_code_to_link,
        html
    )

    # 7. Countdown timer (Last Chance only)
    if email_type == 'lastchance' and countdown_url:
        countdown_block = (
            f'<p><img style="display: block; margin-left: auto; margin-right: auto;" '
            f'src="{countdown_url}" width="320px"></p>'
        )
        # Insert after the body text block (after the text div)
        # Find the text content area and insert after it
        text_key = 'text_lc'
        body_text = campaign_data.get(text_key, {}).get(lang, '')
        if body_text:
            body_text_html = body_text.replace('\n', '<br>')
            insert_marker = f'{body_text_html}</span>'
            if insert_marker in html:
                html = html.replace(insert_marker, insert_marker + countdown_block)
            else:
                # Fallback: insert before the CTA button area
                idx = html.find('#FBA157')
                if idx >= 0:
                    # Find the start of the button section
                    section_start = html.rfind('<table', max(0, idx - 2000), idx)
                    if section_start > 0:
                        html = html[:section_start] + countdown_block + html[section_start:]

    return html


def _add_dc_code(url, code):
    if not url:
        return url
    if 'dc_code=' in url:
        return re.sub(r'dc_code=[^&]*', f'dc_code={code}', url)
    if '?' in url:
        return f'{url}&dc_code={code}'
    return f'{url}?dc_code={code}'


def slugify(name):
    name = name.lower().strip()
    name = re.sub(r'[^a-z0-9]+', '_', name)
    name = name.strip('_')
    return name


def generate_all(templates, campaign_data, end_date, discount_code, banner_links, countdown_urls, campaign_name, banner_image_urls=None):
    files = {}
    slug = slugify(campaign_name)
    if banner_image_urls is None:
        banner_image_urls = {}
    for lang in LANG_CONFIG:
        template_html = templates[lang]
        link = banner_links.get(lang, '')
        lang_countdown = countdown_urls.get(lang, '') if isinstance(countdown_urls, dict) else countdown_urls
        lang_banner_img = banner_image_urls.get(lang, '')
        for email_type in ['starter', 'reminder', 'lastchance']:
            filename = f'{lang}_{slug}_{email_type}.html'
            html = generate_email(
                template_html, lang, email_type,
                campaign_data, end_date, discount_code,
                link, lang_countdown if email_type == 'lastchance' else '',
                banner_image_url=lang_banner_img
            )
            files[filename] = html
    return files
