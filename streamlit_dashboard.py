import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="Retail Chatbot Metrics", layout="centered")
st.title("📊 Retail Chatbot – Interaction Metrics")

mlflow_log_dir = "mlruns"

# Load all logged interactions
def get_logged_queries():
    runs_data = []

    for root, dirs, files in os.walk(mlflow_log_dir):
        if "params" in root and "params.json" in files:
            run_dir = os.path.dirname(root)
            query_file = os.path.join(run_dir, "params", "query")
            tool_file = os.path.join(run_dir, "params", "tool_used")
            response_file = os.path.join(run_dir, "artifacts", "response.txt")

            if os.path.exists(query_file) and os.path.exists(response_file):
                with open(query_file) as qf, open(response_file) as rf:
                    query = qf.read().strip()
                    response = rf.read().strip()
                tool = open(tool_file).read().strip() if os.path.exists(tool_file) else "unknown"
                runs_data.append({"Query": query, "Tool": tool, "Response": response})

    return pd.DataFrame(runs_data)

# Load logs
df = get_logged_queries()

# Display
if df.empty:
    st.warning("No logged interactions yet.")
else:
    st.subheader("🔍 Interaction Log")
    st.dataframe(df)

    st.subheader("🧰 Tool Usage Distribution")
    st.bar_chart(df["Tool"].value_counts())
