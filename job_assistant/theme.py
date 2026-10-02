"""Session-scoped appearance controls without changing server configuration."""
import streamlit as st
from .i18n import t


def toggle_theme():
    st.session_state['dark_mode'] = not st.session_state.get('dark_mode', False)


def theme_switch():
    dark = st.session_state.get('dark_mode', False)
    with st.container(key='theme_switch'):
        st.button(t('Light mode') if dark else t('Dark mode'),
                  icon=':material/light_mode:' if dark else ':material/dark_mode:',
                  key='toggle_theme', on_click=toggle_theme)
    st.markdown('''<style>
    .st-key-theme_switch {position: fixed; top: .5rem; right: 14.5rem; width: auto; z-index: 1000000;}
    @media (max-width: 600px) {
      .st-key-theme_switch {right: 8rem; top: 3.3rem;}
      .st-key-language_switch {right: 2rem; top: 3.3rem;}
      .block-container {padding-top: 7rem;}
    }
    </style>''', unsafe_allow_html=True)
    if not dark:
        return
    st.markdown('''<style>
    :root {color-scheme: dark; --job-bg: #10171f; --job-panel: #18232e;
           --job-raised: #202f3d; --job-text: #e7eef5; --job-muted: #aabcc9; --job-line: #354858;}
    .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"],
    [data-testid="stHeader"] {background: var(--job-bg); color: var(--job-text);}
    [data-testid="stSidebar"] {background: #141e28; border-color: var(--job-line);}
    .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp p, .stApp label,
    .stApp [data-testid="stText"], .stApp [data-testid="stWidgetLabel"],
    .stApp [data-testid="stMetricValue"], .stApp summary {color: var(--job-text);}
    .stApp [data-testid="stText"] span {color: var(--job-text) !important;}
    .stApp [data-testid="stCaptionContainer"] p {color: var(--job-muted);}
    .stApp a {color: #70d9c7;}
    .stApp [data-testid="stMetric"], .st-key-job_detail,
    .stApp [data-testid="stExpander"], .stApp [data-testid="stForm"],
    [class*="st-key-job_card_idle_"] {background: var(--job-panel); border-color: var(--job-line) !important;}
    [class*="st-key-job_card_active_"] {background: #163b3c !important; border-color: #65d6c1 !important;}
    [class*="st-key-job_card_idle_"]:hover {border-color: #65d6c1 !important;}
    .stApp input, .stApp textarea, .stApp [data-baseweb="input"],
    .stApp [data-baseweb="base-input"], .stApp [data-baseweb="textarea"],
    .stApp [data-baseweb="select"] > div {background: var(--job-raised) !important;
      color: var(--job-text) !important; -webkit-text-fill-color: var(--job-text); border-color: var(--job-line);}
    .stApp input::placeholder, .stApp textarea::placeholder {color: var(--job-muted) !important; opacity: 1; -webkit-text-fill-color: var(--job-muted);}
    .stApp input:disabled, .stApp textarea:disabled {opacity: 1;}
    .stApp button, .stApp [data-testid="stLinkButton"] a {background: var(--job-raised); color: var(--job-text); border-color: var(--job-line);}
    .stApp button:hover {border-color: #65d6c1; color: #91e7d7;}
    .stApp button[kind="primary"], .stApp button[kind="primaryFormSubmit"] {background: #16796e; border-color: #299b8e; color: #fff;}
    .stApp button[kind="tertiary"] {background: transparent;}
    .stApp button:disabled {opacity: .55;}
    .stApp button:focus-visible, .stApp a:focus-visible {outline: 2px solid #65d6c1; outline-offset: 3px;}
    .stApp [data-baseweb="tab-list"] {background: transparent; border-color: var(--job-line);}
    .stApp [data-baseweb="tab"] {background: transparent; color: var(--job-muted);}
    .stApp [data-baseweb="tab"][aria-selected="true"] {color: #70d9c7;}
    .stApp [data-testid="stAlert"] {background: #323021; border: 1px solid #6f6036; color: #f2e2b6;}
    .stApp [data-testid="stAlert"] p {color: #f2e2b6;}
    .stApp [data-testid="stFileUploaderDropzone"], .stApp pre,
    .stApp [data-testid="stJson"] {background: var(--job-raised); color: var(--job-text);}
    .stApp hr {border-color: var(--job-line);}
    [data-baseweb="popover"] [role="listbox"], [data-baseweb="popover"] [role="option"],
    [data-baseweb="menu"], [role="tooltip"] {background: #202f3d !important; color: #e7eef5 !important;}
    [role="option"][aria-selected="true"] {background: #164a46 !important;}
    </style>''', unsafe_allow_html=True)
