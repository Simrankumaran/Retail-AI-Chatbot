import os
from groq import Groq
from streamlit_mic_recorder import mic_recorder
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))


def record_audio(key="mic_recorder"):
    """
    Displays mic recorder and returns WAV bytes.
    """
    audio = mic_recorder(
        start_prompt="🎤 Start Recording",
        stop_prompt="⏹️ Stop Recording",
        key=key,
        format="wav"
    )
    if audio and "bytes" in audio:
        return audio["bytes"]
    return None


def transcribe_audio(audio_bytes: bytes) -> str:
    """
    Converts WAV bytes to text using Groq Whisper API.
    """
    try:
        response = client.audio.transcriptions.create(
            model="whisper-large-v3",
            file=("speech.wav", audio_bytes),
            response_format="json"
        )
        return response.text
    except Exception as e:
        return f"[Transcription failed: {e}]"
