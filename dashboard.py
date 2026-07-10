"""
dashboard.py
Phase 6: visualizes a run's trace -- per-node/tool-call timeline, latency,
retry loop, and the final verdict. Reads JSON trace files written by
agent/tracing.py::save_trace() to traces/.
"""
import glob
import json
import os

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Agentic Research Copilot -- Trace Dashboard", page_icon="🔍", layout="wide")
st.title("Agentic Research Copilot -- Trace Dashboard")

trace_files = sorted(glob.glob("traces/run-*.json"), reverse=True)
if not trace_files:
    st.warning("No traces yet. Run `python -m agent.graph \"<question>\"` first.")
    st.stop()

labels = [os.path.basename(f) for f in trace_files]
selected = st.selectbox("Run", labels)
with open(os.path.join("traces", selected)) as f:
    run = json.load(f)

col1, col2, col3 = st.columns(3)
col1.metric("Critic verdict", run["critic_verdict"] or "n/a")
col2.metric("Retries used", run["retry_count"])
col3.metric("Total latency (s)", round(sum(e["latency_sec"] for e in run["trace"]), 2))

st.subheader("Question")
st.write(run["question"])

st.subheader("Final output")
st.write(run["final_output"])

st.subheader("Timeline")
if run["trace"]:
    df = pd.DataFrame(run["trace"])
    t0 = df["start_ts"].min()
    df["start_offset"] = df["start_ts"] - t0
    df["end_offset"] = df["end_ts"] - t0
    # A run's own index disambiguates repeated node names across retry loops
    # (e.g. "planner" appearing twice) so the chart doesn't collapse them.
    df["label"] = [f"{i}: {row.node}" for i, row in enumerate(df.itertuples())]

    chart_data = df[["label", "start_offset", "end_offset"]].set_index("label")
    st.bar_chart(chart_data["end_offset"] - chart_data["start_offset"], x_label="node", y_label="latency (s)")

    st.subheader("Node/tool-call detail")
    st.dataframe(
        df[["label", "latency_sec", "input_summary", "output_summary", "cost_usd", "error"]],
        use_container_width=True,
    )
else:
    st.info("This run has no trace events.")
