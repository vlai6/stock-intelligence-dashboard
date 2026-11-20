"""One-time, idempotent installer: theme existing app.py without replacing it.

Run from the project directory: python apply_blue_theme.py
"""
from __future__ import annotations
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
APP = ROOT / 'app.py'
CONFIG = ROOT / '.streamlit' / 'config.toml'
SNIPPET = ROOT / 'blue_theme.toml'


def patch_app():
    if not APP.exists():
        raise SystemExit('Could not find app.py next to apply_blue_theme.py. Copy installer to the project root first.')
    old = APP.read_text(encoding='utf-8-sig')
    if 'st.title("Stock Intelligence Dashboard")' not in old:
        raise SystemExit('Could not find the expected dashboard title in app.py; no changes made.')
    if 'st.set_page_config(' not in old:
        raise SystemExit('Could not find Streamlit page config in app.py; no changes made.')
    new = old
    if 'from dashboard_theme import apply_dashboard_theme' not in new:
        if 'import plotly.graph_objects as go\n' not in new:
            raise SystemExit('Could not find expected Plotly import; no changes made.')
        new = new.replace(
            'import plotly.graph_objects as go\n',
            'import plotly.graph_objects as go\nfrom dashboard_theme import apply_dashboard_theme, style_blue_figure\n',
            1,
        )
    if '\napply_dashboard_theme()\n' not in new:
        new = new.replace(
            'st.title("Stock Intelligence Dashboard")',
            'apply_dashboard_theme()\n\nst.title("Stock Intelligence Dashboard")', 1,
        )
    # Change displayed Plotly lines to blue, while keeping sentiment colors
    # meaningful (green=positive and pink/red=negative).
    new = new.replace('st.plotly_chart(fig, use_container_width=True)',
                      'st.plotly_chart(style_blue_figure(fig), use_container_width=True)')
    new = new.replace('st.plotly_chart(fig_sentiment, use_container_width=True)',
                      'st.plotly_chart(style_blue_figure(fig_sentiment), use_container_width=True)')
    new = re.sub(r'(st\.plotly_chart\(\s*)comparison(\s*,)',
                 r'\1style_blue_figure(comparison)\2', new)
    # Target the specific legacy gold chart accent without changing semantics.
    new = new.replace('color="#F1B755"', 'color="#71CCFF"')
    # The dashboard's embedded metric table lives in an isolated iframe and
    # needs explicit blue surfaces, unlike normal Streamlit widgets.
    for a,b in {
        '#17191f':'#0E1A29', '#3b414c':'#24435D',
        '#30343d':'#152D43', '#48505d':'#244D6E',
    }.items():
        new = new.replace(a,b)
    if new != old:
        backup = ROOT / 'app.py.before_blue_theme.bak'
        if not backup.exists():
            backup.write_text(old,encoding='utf-8')
        APP.write_text(new,encoding='utf-8')
        print('Updated app.py. Original backed up to app.py.before_blue_theme.bak')
    else:
        print('app.py was already updated; no duplicate changes.')


def patch_config():
    if not SNIPPET.exists():
        raise SystemExit('Missing blue_theme.toml.')
    CONFIG.parent.mkdir(parents=True,exist_ok=True)
    old = CONFIG.read_text(encoding='utf-8') if CONFIG.exists() else ''
    # Remove only existing theme sections, preserving server/browser/etc settings.
    theme_section = re.compile(r'(?ms)^\[theme(?:\.[^\]]+)?\]\s*\n.*?(?=^\[[^\]]+\]\s*$|\Z)')
    retained = theme_section.sub('', old).strip()
    theme = SNIPPET.read_text(encoding='utf-8').strip()
    new = (retained + '\n\n' if retained else '') + theme + '\n'
    if old != new:
        backup = ROOT / '.streamlit' / 'config.toml.before_blue_theme.bak'
        if old and not backup.exists():
            backup.write_text(old,encoding='utf-8')
        CONFIG.write_text(new,encoding='utf-8')
        print('Applied midnight-blue Streamlit theme to .streamlit/config.toml')
    else:
        print('Theme configuration already current.')


if __name__ == '__main__':
    patch_app()
    patch_config()
    print('Done. Restart your Streamlit server to see the blue theme.')
