"""Patch an EXISTING migrated three-page Stock Intelligence project in place.

- Uses actual current project code (not an older replacement of Stock Intelligence)
- Copies backups first; validates syntax before writing.
- No GitHub changes made automatically.
"""
from __future__ import annotations
import ast
import datetime as dt
import pprint
import re
import shutil
import sys
import textwrap
from pathlib import Path

ROOT=Path(__file__).resolve().parent
ASSETS=ROOT/'ui_fix_assets'
STOCK=ROOT/'pages'/'0_Stock_Intelligence.py'
NEWS=ROOT/'pages'/'1_News_Screen.py'
SENTIMENT=ROOT/'pages'/'2_News_Sentiment.py'
THEME=ROOT/'dashboard_theme.py'
MAGIC='# si_20261120_repairs_v1'


def ensure(value, label):
    if not value:
        raise ValueError(f'Could not safely find {label}. No project files changed.')


def read(path):
    return path.read_text(encoding='utf-8-sig')


def patch_theme(src):
    # Broad CSS font rule is responsible for raw Material icon ligatures being visible.
    broad='html, body, .stApp, .stApp *, [data-testid="stSidebar"] * {'
    if broad in src:
        src=src.replace(broad,'html, body, .stApp, [data-testid="stSidebar"] {')
    icon_css='''
/* Restore Streamlit's Material Symbols font. A universal font override turns
   icons into raw ligatures like keyboard_double_arrow_left and expand_more. */
[data-testid="stIconMaterial"], [data-testid="stIconMaterial"] *,
.material-symbols-rounded, .material-icons, [class*="material-symbol"] {
  font-family:"Material Symbols Rounded","Material Icons" !important;
  font-weight:normal !important;font-style:normal !important;
  font-feature-settings:"liga" !important;letter-spacing:normal !important;
  white-space:nowrap !important;display:inline-block;
}
'''
    if 'si icon font repair' not in src.lower():
        src=src.replace('</style>', '/* SI icon font repair */'+icon_css+'\n</style>', 1)
    src=src.replace('--si-muted:#A4B6CA','--si-muted:#B9CDE0')
    src=src.replace('color:#8AA9C2','color:#B0C5DA')
    src=src.replace('color:#7593AC','color:#B0C5DA')
    return src


def target_assignment(tree, name, predicate=lambda a:True):
    for node in ast.walk(tree):
        if isinstance(node,(ast.Assign,ast.AnnAssign)):
            targets=node.targets if isinstance(node,ast.Assign) else [node.target]
            if any(isinstance(t,ast.Name) and t.id==name for t in targets) and predicate(node):
                return node
    return None


def replace_line_spans(src, spans):
    lines=src.splitlines(keepends=True)
    for start,end,new in sorted(spans,key=lambda x:x[0],reverse=True):
        lines[start-1:end]=[new+'\n']
    return ''.join(lines)


def patch_stock(src):
    if '# si dcf group metrics' in src:
        return src
    tree=ast.parse(src)
    def has_value_group(node):
        try:
            obj=ast.literal_eval(node.value)
            return isinstance(obj,dict) and 'Value' in obj and 'Basic' in obj
        except Exception:
            return False
    group_node=target_assignment(tree,'groups',has_value_group)
    order_node=target_assignment(tree,'strategy_order',lambda n:isinstance(n.value,(ast.List,ast.Tuple)))
    ensure(group_node and order_node,'Financial Metrics group definition')
    mapping=ast.literal_eval(group_node.value)
    added_values=['DCF Bear / Share','DCF Base / Share','DCF Bull / Share','DCF Base Upside',
                  'Market-Implied FCF Growth','Normalized FCF','FCF Stability',
                  'SBC / Revenue','Share Dilution (YoY)']
    added_health=['Current Ratio','Quick Ratio','Net Debt','Net Debt / EBITDA',
                  'Interest Coverage','FCF / Total Debt','Operating Margin',
                  'Revenue Growth','ROIC','Share Dilution (YoY)']
    mapping['Value']=list(dict.fromkeys(list(mapping['Value'])+added_values))
    mapping['Health']=added_health
    replacement='groups = '+pprint.pformat(mapping,sort_dicts=False,width=84)
    group_indent=' '*group_node.col_offset
    replacement=group_indent+replacement.replace('\n','\n'+group_indent)
    desired=['All Metrics','Basic','Conservative','High Returns','Value','Health']
    order_indent=' '*order_node.col_offset
    order_replacement=order_indent+'strategy_order = '+repr(desired)
    src=replace_line_spans(src,[(group_node.lineno,group_node.end_lineno,replacement),
                                (order_node.lineno,order_node.end_lineno,order_replacement)])
    # Newly added metric definitions are evaluated on demand rather than per ticker.
    import_line='from dcf_health_metrics import compute_extra_metrics, EXTRA_EXPLANATIONS, EXTRA_METRIC_NAMES, format_extra_metric'
    if import_line not in src:
        src=src.replace('from metric_explanations import EXPLANATIONS',
                        'from metric_explanations import EXPLANATIONS\n'+import_line,1)
    ensure(import_line in src,'metric import location')

    # Hook the existing calculator where it has all three inputs to the new helper.
    tree=ast.parse(src)
    calls=[]
    for node in ast.walk(tree):
        if isinstance(node,ast.Assign) and isinstance(node.value,ast.Call):
            if isinstance(node.value.func,ast.Name) and node.value.func.id=='calculate_metrics':
                if any(isinstance(t,ast.Subscript) and isinstance(t.value,ast.Name) and t.value.id=='calculated' for t in node.targets):
                    calls.append(node)
    ensure(len(calls)==1,'financial metric calculation hook')
    node=calls[0]
    indent=' '*node.col_offset
    addition='\n'.join([
        indent+'# si dcf group metrics — compute only if any extra is selected',
        indent+'if any(m in EXTRA_METRIC_NAMES for m in selected_metrics):',
        indent+'    latest_for_screen = (history["Close"].iloc[-1]',
        indent+'                         if not history.empty and "Close" in history else None)',
        indent+'    calculated[stock_symbol].update(',
        indent+'        compute_extra_metrics(stock_symbol, stock_info, latest_for_screen)',
        indent+'    )',
    ])
    lines=src.splitlines(keepends=True)
    lines.insert(node.end_lineno,addition+'\n')
    src=''.join(lines)

    # Format money/percent readouts and add their mouseover explanations.
    format_pattern=r'(?m)^(\s+)if name in percent_metrics:'
    ensure(re.search(format_pattern,src),'metric format switch')
    src=re.sub(format_pattern,lambda m:(m.group(1)+'if name in EXTRA_METRIC_NAMES:\n'
                                             +m.group(1)+'    return format_extra_metric(name, value)\n\n'
                                             +m.group(0)),src,count=1)
    # A few older versions use a different line break / indentation.
    src=re.sub(r'EXPLANATIONS\.get\(\s*metric,\s*["\']No explanation available\.["\']\s*\)',
               'EXPLANATIONS.get(metric, EXTRA_EXPLANATIONS.get(metric, "No explanation available."))',src)
    ensure('EXTRA_EXPLANATIONS.get(metric' in src,'financial metrics hover descriptions')
    # Visually distinct amber trend line for both primary and competitor-overlay modes.
    src=src.replace('color="#F1B755"','color="#FFC15A"')
    src=src.replace('color=\'#F1B755\'','color=\'#FFC15A\'')
    # This is called on the single main figure after every trace (including competitors).
    src=re.sub(r'(?m)^(\s*)st\.plotly_chart\(fig, use_container_width=True\)',
               r'\1for _trace in fig.data:\n\1    if "trend line" in str(getattr(_trace, "name", "")).lower():\n\1        _trace.line.color = "#FFC15A"\n\1        _trace.line.dash = "dash"\n\1        _trace.line.width = 3\n\1st.plotly_chart(fig, use_container_width=True)',src,count=1)
    # Explain assumptions for the rough valuation screen (not a full FCFF model).
    marker='''                    st.caption(
                        "Risk metrics use daily adjusted returns against SPY "'''
    if marker in src:
        src=src.replace(marker,'''                    st.caption(
                        "DCF screens use a simplified normalized free-cash-flow proxy: 5-year growth "
                        "-5% / +5% / +15% (Bear / Base / Bull), 10% equity hurdle and 2% terminal growth. "
                        "Known stock-based compensation is deducted without additionally modeling dilution. "
                        "This is NOT a complete FCFF/WACC valuation or a downside floor; missing inputs show N/A."
                    )
'''+marker,1)
    compile(src,str(STOCK),'exec')
    return src


NEWS_EVENT_CSS='''
/* Small, inline AI group filters directly below the company name */
.ns-card {min-height:425px;}
.ns-event-box {margin:3px 0 7px;font-size:10px;color:#B9CEE0;}
.ns-event-box summary {cursor:pointer;color:#77CFFF;font-weight:650;font-size:10px;
  text-overflow:ellipsis;white-space:nowrap;overflow:hidden;max-width:215px;}
.ns-event-choices {display:flex;gap:4px;flex-wrap:wrap;margin:5px 0 2px;}
.ns-event-choices label {cursor:pointer;border:1px solid #214766;background:#0B1C30;
  color:#B9CEE0;border-radius:10px;padding:3px 6px;font-size:10px;max-width:100%;}
.ns-event-choices label:has(input:checked) {border-color:#60BFFC;color:#F3FAFF;background:#153F62;}
.ns-event-choices input {margin-right:3px;accent-color:#4BA9F2;vertical-align:middle;}
'''+''.join(f'.ns-card:has(.ns-filter-{i}:checked) .ns-article:not(.ns-event-{i}) {{display:none;}}\n' for i in range(5))

MINI_HELPERS='''
# --- Compact Gemini event filters for each stock's 7-day, name-matched headlines ---
def compact_event_ui(symbol, events_df, group_articles):
    from news_ai_shared import article_event_assignments
    labels, assignments=article_event_assignments(events_df,group_articles)
    if not labels or not assignments:
        return '<div class="ns-event-box">AI groups unavailable</div>', {}
    sizes={key:sum(1 for eid in assignments.values() if eid==key) for key in labels}
    ordered=[key for key in sorted(labels,key=lambda k:-sizes[k]) if sizes[key]>0][:4]
    if not ordered:
        return '<div class="ns-event-box">AI groups unavailable</div>', {}
    number_for={key:i for i,key in enumerate(ordered)}
    classes={title:number_for[key] for title,key in assignments.items() if key in number_for}
    safe_name=html.escape(symbol,quote=True)
    rows=[f'<label><input type="radio" name="ns_ai_{safe_name}" checked>All</label>']
    for key in ordered:
        idx=number_for[key]
        label=html.escape(labels[key][:28])
        rows.append(f'<label><input type="radio" class="ns-filter-{idx}" name="ns_ai_{safe_name}">{label} ({sizes[key]})</label>')
    controls=(f'<details class="ns-event-box"><summary>AI groups · {len(ordered)} topics</summary>'
              +'<div class="ns-event-choices">'+''.join(rows)+'</div></details>')
    return controls, classes


def automatic_stock_scan(symbol, records):
    from news_ai_shared import score_titles
    titles=tuple(str(item['title']) for item in records)
    if not titles:
        return {'status':'empty'}
    try:
        scores=score_titles(titles)
        counts={label:sum(1 for item in scores if item[0].lower()==label)
                for label in ('positive','neutral','negative')}
        status=('positive' if counts['positive']>counts['negative']
                else 'negative' if counts['negative']>counts['positive'] else 'mixed')
        return {'status':status,'counts':counts}
    except Exception:
        return {'status':'unavailable'}


def automatic_stock_groups(symbol, records):
    from news_ai_shared import scored_frame, group_company_news
    try:
        if len(records)<2:
            return None
        scored=scored_frame(records)
        events, rows, problem=group_company_news(symbol,scored)
        if problem:
            return None
        return (events, rows)
    except Exception:
        return None

'''


def patch_news(src):
    if '# si named lists and automatic scan' in src:
        return src
    # Add shared, cached AI helpers.
    anchor='def make_status(scan: dict | None) -> tuple[str, str]:'
    ensure(anchor in src,'News Screen status function')
    src=src.replace(anchor,MINI_HELPERS+'\n'+anchor,1)
    # Make card optionally accept and render group filters, without changing quote data.
    old='def make_card(symbol: str, quote: dict, items: list[dict], scan: dict | None, first: bool = False) -> str:'
    new='def make_card(symbol: str, quote: dict, items: list[dict], scan: dict | None, first: bool = False, grouping=None) -> str:'
    ensure(old in src,'News Screen card renderer')
    src=src.replace(old,new,1)
    src=src.replace('    article_rows: list[str] = []\n    for item in items:',
                    '''    event_html, article_groups=compact_event_ui(symbol, *(grouping or (None,None)))
    article_rows: list[str] = []
    for item in items:''',1)
    src=src.replace('        published = item["date"].strftime("%d %b") if item.get("date") else "—"',
                    '''        event_group=article_groups.get(str(item.get('title','')).strip().casefold())
        event_class=f' ns-event-{event_group}' if event_group is not None else ''
        published = item["date"].strftime("%d %b") if item.get("date") else "—"''',1)
    src=src.replace("f'<a class=\"ns-article\" href=\"{html.escape(link, quote=True)}\" '",
                    "f'<a class=\"ns-article{event_class}\" href=\"{html.escape(link, quote=True)}\" '",1)
    src=src.replace("article_rows.append(f'<div class=\"ns-article\">{inside}</div>')",
                    "article_rows.append(f'<div class=\"ns-article{event_class}\">{inside}</div>')",1)
    src=src.replace('f\'<div><div class="ns-symbol">{safe_symbol}</div><div class="ns-company">{name}</div></div>\'',
                    'f\'<div><div class="ns-symbol">{safe_symbol}</div><div class="ns-company">{name}</div>{event_html}</div>\'',1)
    ensure('ns-event-{' in src and '{event_html}' in src,'inline group renderer')
    src=src.replace('</style>',NEWS_EVENT_CSS+'\n</style>',1)

    # Replace browser-local single list with named multiple-list storage and migration.
    start=src.find('# --- Persistent watchlist (browser-local; per user and per website) ---------')
    finish=src.find('render_page_header(\n',start)
    ensure(start>=0 and finish>start,'News Screen watchlist persistence block')
    fragment=read(ASSETS/'watchlist_upgrade.pyfrag')
    src=src[:start]+'# si named lists and automatic scan\n'+fragment+'\n'+src[finish:]
    # Remove scan button from header, leaving the existing links intact.
    old_pattern=r"scan_left, scan_right = st\.columns\(\[4, 1\], vertical_alignment='center'\)\nwith scan_right:\n    scan_clicked = st\.button\('Scan headlines', type='primary',\n                             use_container_width=True, key='ns_scan_button'\)\n"
    ensure(re.search(old_pattern,src),'manual scan button')
    src=re.sub(old_pattern,'',src,count=1)
    # Insert watchlist chooser and manage popover above the ticker chips.
    marker='st.markdown(\'<div class="ns-toprule"></div>\', unsafe_allow_html=True)'
    ensure(marker in src,'watchlist controls placement')
    src=src.replace(marker,read(ASSETS/'list_controls.pyfrag')+'\n'+marker,1)
    # Auto scan every render, but model work is cached per unique headline snapshot.
    scan_block='''if scan_clicked:
    st.session_state["ns_scans"].update(scan_sentiment(watchlist, news_by_symbol))
    st.session_state["ns_scanned_at"] = datetime.now(MARKET_TZ).strftime("%d %b %Y, %I:%M %p ET")
'''
    ensure(scan_block in src,'manual scan execution block')
    auto_block='''# Automatic FinBERT labels on each loaded headline snapshot (cached; no scan button).
for _symbol in watchlist:
    st.session_state['ns_scans'][_symbol] = automatic_stock_scan(_symbol, news_by_symbol.get(_symbol,[]))

# Only grouped, already-filtered company headlines are sent to Gemini.
# The AI helper has a 6-hour cache to avoid repeating API requests on reruns.
stock_groups={_symbol:automatic_stock_groups(_symbol,news_by_symbol.get(_symbol,[]))
              for _symbol in watchlist}
st.session_state['ns_scanned_at']=datetime.now(MARKET_TZ).strftime('%d %b %Y, %I:%M %p ET')
'''
    src=src.replace(scan_block,auto_block,1)
    ensure('stock_groups={' in src,'per-card automatic grouping')
    src=src.replace('        first=(i == 0),\n',
                    '        first=(i == 0),\n        grouping=stock_groups.get(symbol),\n',1)
    src=src.replace("else \"Select 'Scan headlines' for FinBERT sentiment per ticker. \"",
                    "else 'FinBERT scores are calculated automatically. '")
    # In the footer: keep if the prior replacement hit, but no manual-scan text should remain.
    src=src.replace("Select 'Scan headlines' for FinBERT sentiment per ticker.",
                    "FinBERT sentiment is calculated automatically.")
    # Changed watchlist actions must synchronize the selected named list on save.
    compile(src,str(NEWS),'exec')
    return src


def run():
    required=[STOCK,NEWS,SENTIMENT,THEME,ASSETS/'news_shared.py',
              ASSETS/'news_ai_shared.py',ASSETS/'dcf_health_metrics.py',
              ASSETS/'2_News_Sentiment.py']
    ensure(all(p.exists() for p in required),
           'existing three-page structure or the ui_fix_assets package')
    if MAGIC in read(STOCK):
        print('Already applied. No changes written.')
        return
    src_stock=patch_stock(read(STOCK))+'\n'+MAGIC+'\n'
    src_news=patch_news(read(NEWS))
    src_theme=patch_theme(read(THEME))
    src_sentiment=read(ASSETS/'2_News_Sentiment.py')
    dest={STOCK:src_stock,NEWS:src_news,THEME:src_theme,SENTIMENT:src_sentiment}
    for name in ('news_shared.py','news_ai_shared.py','dcf_health_metrics.py'):
        dest[ROOT/name]=read(ASSETS/name)
    for path,body in dest.items():
        compile(body,str(path),'exec')
    stamp=dt.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup=ROOT/'.ui_fix_backups'/stamp
    backup.mkdir(parents=True,exist_ok=False)
    for path in dest:
        if path.exists():
            target=backup/path.relative_to(ROOT)
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(path,target)
    print(f'Backup: {backup}')
    for path,body in dest.items():
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(body,encoding='utf-8')
        print('Updated:',path.relative_to(ROOT))
    ignore=ROOT/'.gitignore'
    if ignore.is_file():
        rules=read(ignore)
        if '/.ui_fix_backups/' not in rules:
            ignore.write_text(rules.rstrip()+'\n/.ui_fix_backups/\n',encoding='utf-8')
    print('Success. Restart with: python -m streamlit run app.py')
    print('Check locally before committing/pushing. Backups are excluded from Git.')

if __name__=='__main__':
    try:
        run()
    except Exception as exc:
        print('NOT INSTALLED:',type(exc).__name__,str(exc),file=sys.stderr)
        sys.exit(1)
