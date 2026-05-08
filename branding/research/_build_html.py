"""Build the final landscape HTML with all data pre-rendered as DOM (no client JS)."""
import json, html
from pathlib import Path

ROOT = Path("/sessions/wonderful-sleepy-carson/mnt/prophet/branding/research")
data = json.loads((ROOT / "data.json").read_text())

CATEGORY_ORDER = ['odds', 'publication', 'consumer', 'avoid']
TAG_LABEL = {
    'odds': 'Odds / aggregator',
    'publication': 'Publication',
    'consumer': 'Consumer product',
    'avoid': 'AVOID · gambling-promo',
}
BUCKET_LABEL = {
    'odds': 'Odds',
    'publication': 'Pub.',
    'consumer': 'Consumer',
    'avoid': 'Avoid',
}

def esc(s): return html.escape(str(s))

# --- Build cards (sorted by category) ---
sorted_sites = sorted(data['sites'], key=lambda s: (CATEGORY_ORDER.index(s['category']), s['name']))
cards_html = []
for s in sorted_sites:
    swatch_html = ''.join(f'<div class="swatch" style="background:{c};"></div>' for c in s['palette'])
    cards_html.append(f'''
    <div class="card {s['category']}">
      <div class="name">{esc(s['name'])}</div>
      <div class="tag">{esc(TAG_LABEL[s['category']])}</div>
      <div class="swatches">{swatch_html}</div>
      <div class="vibe">{esc(s['vibe'])}</div>
      <div class="footer">
        <span class="reg">REG {s['register']}/4</span>
        <span>{'◑ dark' if s['mode']=='dark' else '◐ light'}</span>
      </div>
    </div>''')
cards_html = '\n'.join(cards_html)


# --- Build cluster map points ---
points_html = []
for s in data['sites']:
    x_pct = ((s['x'] + 1) / 2) * 100
    y_pct = ((-s['y'] + 1) / 2) * 100
    label = s['name'].replace(' (AVOID)','').replace(' (sub for Smarkets)','').replace(' (sub for Tifo)','')
    points_html.append(f'''
    <div class="point {s['category']}" style="left:{x_pct:.1f}%; top:{y_pct:.1f}%;">
      <div class="marker"></div>
      <div class="lbl">{esc(label)}</div>
    </div>''')
points_html = '\n'.join(points_html)


# --- Build receipts table ---
rows_html = []
for s in data['sites']:
    swatches = ''.join(f'<span class="ms" style="background:{c};"></span>' for c in s['palette'])
    hexline = ' '.join(s['palette'])
    cls = ' class="avoid-row"' if s['category'] == 'avoid' else ''
    domain = s['url'].replace('https://', '').replace('http://', '').replace('www.', '').rstrip('/')
    rows_html.append(f'''
    <tr{cls}>
      <td><strong>{esc(s['name'])}</strong><br><span class="mono" style="font-size:6.5px; color:var(--muted);">{esc(domain)}</span></td>
      <td>{BUCKET_LABEL[s['category']]}</td>
      <td class="swatchcell">{swatches}<br><span style="font-family: ui-monospace, Menlo, monospace; font-size:6.2px; color:var(--muted); letter-spacing:0.2px;">{esc(hexline)}</span></td>
      <td><strong>{s['register']}</strong>/4</td>
      <td>{esc(s['type'])}</td>
      <td>{s['mode']}</td>
      <td>{esc(s['audience'])}</td>
      <td>{esc(s['vibe'])}</td>
    </tr>''')
rows_html = '\n'.join(rows_html)


# Read template & substitute
template = (ROOT / "landscape.html").read_text()

# We'll replace the entire <script> section with empty, and inject pre-rendered DOM into placeholders.
# First, locate and remove the <script>...</script> block
import re
template = re.sub(r'<script>.*?</script>', '', template, flags=re.DOTALL)

# Now inject content. The grid: insert into <div class="grid" id="grid"></div>
template = template.replace('<div class="grid" id="grid"></div>',
                            f'<div class="grid" id="grid">{cards_html}</div>')

# Cluster map: replace contents of <div class="map-grid" id="mapgrid"></div>
empty_zone = '''
<div class="empty-zone" style="left:5%; right:60%; top:7%; height:46%;"></div>
<div class="quad-label" style="left:6%; top:8%; color:var(--signal); font-weight:700;">White space — bold publication / dark-mode editorial</div>
'''
template = template.replace('<div class="map-grid" id="mapgrid"></div>',
                            f'<div class="map-grid" id="mapgrid">{empty_zone}{points_html}</div>')

# Receipts: replace empty <tbody>
template = template.replace('<tbody></tbody>', f'<tbody>{rows_html}</tbody>')

(ROOT / "landscape_filled.html").write_text(template)
print('built', len(template))
