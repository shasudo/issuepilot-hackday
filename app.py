"""IssuePilot Hack Day UI shell (M0). The Analyze view lands in M2."""

import streamlit as st

st.set_page_config(page_title="IssuePilot", layout="wide")

st.title("IssuePilot")
st.caption("Paste any GitHub link, get a personalized triage card.")
st.text_input("GitHub link", placeholder="https://github.com/owner/repo/issues/123", disabled=True)
st.info("UI shell only — the Analyze view lands in M2.")
