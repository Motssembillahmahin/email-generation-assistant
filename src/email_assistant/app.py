"""Streamlit demo UI — a thin visual wrapper over ``EmailGenerator``.

Mirrors the CLI (``make generate``) so a reviewer can try the assistant interactively
instead of by command line. All generation logic lives in ``generator.py``; this module
only collects the three inputs, calls the generator, and renders the result.

Run with::

    make app          # uv run --extra demo streamlit run src/email_assistant/app.py
"""

from __future__ import annotations

import streamlit as st

from email_assistant.generator import EmailGenerator
from email_assistant.models import MODELS

st.set_page_config(page_title="Email Generation Assistant", page_icon="✉️")
st.title("✉️ Email Generation Assistant")
st.caption("Turn Intent · Key Facts · Tone into a professional email. Same engine as the CLI.")

model_key = st.selectbox(
    "Model",
    options=list(MODELS),
    format_func=lambda k: MODELS[k].label,
)
intent = st.text_input("Intent", placeholder="Follow up after a product demo")
facts_raw = st.text_area("Key facts (one per line)", placeholder="Demo was on Tuesday\nOffering a 14-day trial")
tone = st.text_input("Tone", placeholder="professional and warm")

if st.button("Generate", type="primary"):
    key_facts = [line.strip() for line in facts_raw.splitlines() if line.strip()]
    if not intent.strip() or not tone.strip():
        st.warning("Intent and Tone are required.")
    else:
        try:
            with st.spinner(f"Generating with {MODELS[model_key].label}…"):
                result = EmailGenerator(model_key).generate(intent, key_facts, tone)
        except RuntimeError as exc:  # missing API key — the only expected runtime failure
            st.error(str(exc))
        else:
            st.text_area("Generated email", value=result.email_text, height=320)