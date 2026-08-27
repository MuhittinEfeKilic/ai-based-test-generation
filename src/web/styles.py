"""The application's single stylesheet.

Kept in one place so the visual system can be reasoned about as a whole. The
selectors deliberately lean on Streamlit's stable `data-testid` attributes and
on our own class names rather than on generated class hashes, which change
between Streamlit releases.
"""

import streamlit as st

CSS = """
<style>
:root {
  --bg:            #0d1117;
  --surface:       #121820;
  --surface-2:     #161d26;
  --surface-3:     #1b2430;
  --border:        #232c39;
  --border-strong: #303c4d;

  --text:          #e6edf3;
  --text-muted:    #8b98a9;
  --text-faint:    #64707f;

  --accent:        #4c8bf5;
  --accent-dim:    #2a4a80;
  --success:       #3fb950;
  --warning:       #d29922;
  --error:         #f85149;

  --radius:        6px;
  --mono: ui-monospace, "SF Mono", "JetBrains Mono", "Cascadia Code", Menlo, Consolas, monospace;
}

/* ---- shell -------------------------------------------------------------- */
.stApp { background: var(--bg); }

.block-container {
  padding-top: 1rem;
  padding-bottom: 3rem;
  max-width: 1500px;
}

/* Streamlit chrome we do not need in an app toolbar layout. */
#MainMenu, footer, header[data-testid="stHeader"] { display: none; }

h1, h2, h3, h4 { color: var(--text); letter-spacing: -0.01em; }

/* ---- application header ------------------------------------------------- */
.tg-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.65rem 1rem;
  margin-bottom: 1rem;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
}

.tg-brand { display: flex; align-items: baseline; gap: 0.6rem; min-width: 0; }

.tg-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px; height: 26px;
  border-radius: var(--radius);
  background: var(--accent-dim);
  color: var(--text);
  font-family: var(--mono);
  font-size: 0.85rem;
  font-weight: 600;
  align-self: center;
}

.tg-name {
  font-size: 1rem;
  font-weight: 600;
  color: var(--text);
  letter-spacing: -0.01em;
}

.tg-tagline {
  font-size: 0.78rem;
  color: var(--text-faint);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.tg-header-right { display: flex; align-items: center; gap: 0.5rem; flex-shrink: 0; }

.tg-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.2rem 0.55rem;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: var(--surface-2);
  color: var(--text-muted);
  font-size: 0.72rem;
  font-family: var(--mono);
  white-space: nowrap;
}

.tg-pill a { color: var(--text-muted); text-decoration: none; }
.tg-pill a:hover { color: var(--text); }

.tg-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--text-faint); }
.tg-dot.ok    { background: var(--success); }
.tg-dot.warn  { background: var(--warning); }
.tg-dot.idle  { background: var(--text-faint); }

/* ---- workflow steps ----------------------------------------------------- */
.tg-steps {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  flex-wrap: wrap;
  margin: 0 0 1.1rem 0;
  font-size: 0.74rem;
  font-family: var(--mono);
  color: var(--text-faint);
}

.tg-step { display: inline-flex; align-items: center; gap: 0.35rem; }
.tg-step .tg-dot { width: 5px; height: 5px; }
.tg-step.done { color: var(--text-muted); }
.tg-step.done .tg-dot { background: var(--success); }
.tg-step.active { color: var(--accent); }
.tg-step.active .tg-dot { background: var(--accent); }
.tg-sep { color: var(--border-strong); }

/* ---- panels ------------------------------------------------------------- */
.tg-panel-title {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.75rem;
  margin: 0 0 0.6rem 0;
}

.tg-panel-title h3 {
  margin: 0;
  font-size: 0.82rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: var(--text-muted);
}

.tg-panel-note {
  font-size: 0.74rem;
  color: var(--text-faint);
  font-family: var(--mono);
}

/* ---- metric cards ------------------------------------------------------- */
.tg-metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(96px, 1fr));
  gap: 0.5rem;
  margin-bottom: 0.9rem;
}

.tg-metric {
  padding: 0.55rem 0.65rem;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
}

.tg-metric-value {
  font-family: var(--mono);
  font-size: 1.25rem;
  font-weight: 600;
  line-height: 1.2;
  color: var(--text);
}

.tg-metric-label {
  margin-top: 0.15rem;
  font-size: 0.68rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-faint);
}

.tg-metric.accent .tg-metric-value  { color: var(--accent); }
.tg-metric.success .tg-metric-value { color: var(--success); }
.tg-metric.warning .tg-metric-value { color: var(--warning); }
.tg-metric.error .tg-metric-value   { color: var(--error); }

/* ---- coverage ----------------------------------------------------------- */
.tg-coverage {
  padding: 1rem 1.1rem;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  margin-bottom: 0.75rem;
}

.tg-coverage-head { display: flex; align-items: baseline; gap: 0.7rem; }

.tg-coverage-value {
  font-family: var(--mono);
  font-size: 2.6rem;
  font-weight: 600;
  line-height: 1;
  letter-spacing: -0.02em;
}

.tg-coverage-label { font-size: 0.8rem; color: var(--text-muted); }

.tg-badge {
  margin-left: auto;
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  font-size: 0.7rem;
  font-family: var(--mono);
  border: 1px solid var(--border-strong);
  color: var(--text-muted);
}

.tg-bar {
  margin-top: 0.85rem;
  height: 6px;
  border-radius: 999px;
  background: var(--surface-3);
  overflow: hidden;
}

.tg-bar-fill { height: 100%; border-radius: 999px; }

.tg-coverage-sub {
  margin-top: 0.6rem;
  font-family: var(--mono);
  font-size: 0.74rem;
  color: var(--text-faint);
}

/* ---- structure table ---------------------------------------------------- */
.tg-table-wrap { overflow-x: auto; }

table.tg-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.78rem;
  font-family: var(--mono);
}

table.tg-table th {
  text-align: left;
  padding: 0.4rem 0.6rem;
  color: var(--text-faint);
  font-weight: 500;
  font-size: 0.68rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
}

table.tg-table td {
  padding: 0.4rem 0.6rem;
  color: var(--text-muted);
  border-bottom: 1px solid var(--surface-3);
  white-space: nowrap;
}

table.tg-table td.name { color: var(--text); }
table.tg-table tr:last-child td { border-bottom: none; }

.tg-tag {
  display: inline-block;
  padding: 0.05rem 0.35rem;
  margin-right: 0.2rem;
  border-radius: 3px;
  font-size: 0.68rem;
  background: var(--surface-3);
  color: var(--text-muted);
}
.tg-tag.async  { color: var(--accent); }
.tg-tag.raises { color: var(--warning); }

.tg-empty {
  padding: 1.1rem;
  border: 1px dashed var(--border-strong);
  border-radius: var(--radius);
  color: var(--text-faint);
  font-size: 0.82rem;
  text-align: center;
}

/* ---- Streamlit widget restyling ---------------------------------------- */
.stButton > button, .stDownloadButton > button {
  border-radius: var(--radius);
  border: 1px solid var(--border-strong);
  background: var(--surface-2);
  color: var(--text);
  font-size: 0.82rem;
  font-weight: 500;
  padding: 0.4rem 0.85rem;
  transition: background 120ms ease, border-color 120ms ease;
}

.stButton > button:hover, .stDownloadButton > button:hover {
  background: var(--surface-3);
  border-color: var(--accent-dim);
  color: var(--text);
}

.stButton > button[kind="primary"] {
  background: var(--accent);
  border-color: var(--accent);
  color: #ffffff;
  font-weight: 600;
}
.stButton > button[kind="primary"]:hover {
  background: #5c97f7;
  border-color: #5c97f7;
}
.stButton > button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

div[data-testid="stTextInput"] input,
div[data-testid="stNumberInput"] input,
div[data-testid="stTextArea"] textarea {
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  color: var(--text);
  font-size: 0.85rem;
}

div[data-testid="stTextArea"] textarea { font-family: var(--mono); }

div[data-baseweb="select"] > div {
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  font-size: 0.85rem;
}

div[data-testid="stFileUploaderDropzone"] {
  background: var(--surface-2);
  border: 1px dashed var(--border-strong);
  border-radius: var(--radius);
  padding: 0.6rem 0.9rem;
}

div[data-testid="stExpander"] {
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface);
}
div[data-testid="stExpander"] summary { font-size: 0.8rem; color: var(--text-muted); }

div[data-testid="stAlertContainer"] {
  border-radius: var(--radius);
  font-size: 0.83rem;
}

.stTabs [data-baseweb="tab-list"] {
  gap: 0.2rem;
  border-bottom: 1px solid var(--border);
}
.stTabs [data-baseweb="tab"] {
  height: 34px;
  padding: 0 0.8rem;
  font-size: 0.82rem;
  color: var(--text-muted);
}
.stTabs [aria-selected="true"] { color: var(--text); }

div[data-testid="stCode"] { border-radius: var(--radius); }
div[data-testid="stCode"] pre {
  background: var(--surface) !important;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  font-size: 0.78rem;
  max-height: 460px;
  overflow: auto;
}

hr { border-color: var(--border); margin: 1rem 0; }

/* ---- narrow viewports --------------------------------------------------- */
@media (max-width: 900px) {
  .tg-header { flex-direction: column; align-items: flex-start; }
  .tg-coverage-value { font-size: 2rem; }
  .tg-metrics { grid-template-columns: repeat(auto-fit, minmax(84px, 1fr)); }
}
</style>
"""


def inject() -> None:
    """Apply the stylesheet once per page render."""
    st.markdown(CSS, unsafe_allow_html=True)
