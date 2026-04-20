import os
import requests
import streamlit as st
from app.ui.speech_utils import record_audio, transcribe_audio

st.set_page_config(page_title="Retail Chatbot", layout="centered")
st.title("🛍️ Retail Assistant Chatbot")
st.caption("Ask about products, orders, or return policies.")

API_URL = os.getenv("RETAIL_API_URL", "http://127.0.0.1:8000")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []  # each: {"role": "user"|"assistant", "content": str}

# Initialize state
if "voice_key_id" not in st.session_state:
    st.session_state.voice_key_id = 0
if "last_voice_input" not in st.session_state:
    st.session_state.last_voice_input = None
if "processing_audio" not in st.session_state:
    st.session_state.processing_audio = False

cols = st.columns([1, 1, 3])
with cols[0]:
    if st.button("Clear chat"):
        st.session_state.messages = []
        st.session_state.voice_key_id += 1
        st.session_state.last_voice_input = None
        st.session_state.processing_audio = False
        st.rerun()
with cols[1]:
    st.write("")

# Render chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

st.subheader("🎙️ Voice Input")
# Use dynamic key to allow resetting
audio_bytes = record_audio(key=f"voice_input_{st.session_state.voice_key_id}")

# Process audio only if it's new and not already being processed
if audio_bytes and not st.session_state.processing_audio:
    # Create a hash of audio bytes to detect actual changes
    import hashlib
    audio_hash = hashlib.md5(audio_bytes).hexdigest()
    
    if audio_hash != st.session_state.last_voice_input:
        st.session_state.processing_audio = True
        st.session_state.last_voice_input = audio_hash
        
        text = transcribe_audio(audio_bytes)
        if text and text.strip():
            st.write(f"**You said:** {text}")
            
            # Append user message
            st.session_state.messages.append({"role": "user", "content": text})
            
            # Call backend
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    try:
                        # Use demo endpoint (no auth required, defaults to user 2001)
                        resp = requests.post(
                            f"{API_URL}/chat/demo",
                            params={"query": text},
                            timeout=60
                        )
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
            
            # Reset processing flag and increment key
            st.session_state.processing_audio = False
            st.session_state.voice_key_id += 1
            st.rerun()
        else:
            st.session_state.processing_audio = False

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
                # Use demo endpoint (no auth required, defaults to user 2001)
                resp = requests.post(
                    f"{API_URL}/chat/demo",
                    params={"query": prompt},
                    timeout=60
                )
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
