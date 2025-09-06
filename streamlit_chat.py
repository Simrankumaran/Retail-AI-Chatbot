import os
import requests
import streamlit as st

st.set_page_config(page_title="Retail Chatbot", layout="centered")
st.title("🛍️ Retail Assistant Chatbot")
st.caption("Ask about products, orders, or return policies.")

API_URL = os.getenv("RETAIL_API_URL", "http://127.0.0.1:8000")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []  # each: {"role": "user"|"assistant", "content": str}

cols = st.columns([1, 1, 3])
with cols[0]:
    if st.button("Clear chat"):
        st.session_state.messages = []
with cols[1]:
    st.write("")

# Render chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Chat input
if prompt := st.chat_input("Type your question..."):
    # Append user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Call backend
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                resp = requests.post(f"{API_URL}/chat", json={"query": prompt}, timeout=60)
                if resp.ok:
                    answer = resp.json().get("response", "")
                    st.session_state.messages.append({"role": "assistant", "content": answer})
                    st.markdown(answer)
                else:
                    err = f"Backend error ({resp.status_code})."
                    st.session_state.messages.append({"role": "assistant", "content": err})
                    st.error(err)
            except Exception as e:
                err = f"Request failed: {e}"
                st.session_state.messages.append({"role": "assistant", "content": err})
                st.error(err)
