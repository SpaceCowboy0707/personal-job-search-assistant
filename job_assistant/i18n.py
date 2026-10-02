"""Local UI translations; stored evidence and API output keep their language."""
import json
from functools import lru_cache
from pathlib import Path

import streamlit as st


@lru_cache(maxsize=1)
def catalog():
    return json.loads((Path(__file__).parent / 'locales' / 'zh.json').read_text(encoding='utf-8'))


def t(message, **values):
    translated = catalog().get(message, message) if st.session_state.get('ui_language', 'en') == 'zh' else message
    return translated.format(**values) if values else translated


def toggle_language():
    st.session_state['ui_language'] = 'en' if st.session_state.get('ui_language', 'en') == 'zh' else 'zh'


def option_labels():
    """Bind labels to the rendered language, including later widget serialization."""
    labels = catalog() if st.session_state.get('ui_language', 'en') == 'zh' else {}
    return lambda value: labels.get(value, value)


def language_switch():
    with st.container(key='language_switch'):
        st.button('English' if st.session_state.get('ui_language', 'en') == 'zh' else '\u4e2d\u6587',
                  key='toggle_language', on_click=toggle_language,
                  help=t('Switch interface language. Saved content keeps its original language.'))
