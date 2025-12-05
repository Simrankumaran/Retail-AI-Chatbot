import os
import logging
from groq import Groq
from streamlit_mic_recorder import mic_recorder
from dotenv import load_dotenv

load_dotenv()

# -----------------------
# Configure simple console logging
# -----------------------
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# -----------------------
# Initialize Groq client
# -----------------------
api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    logger.error("GROQ_API_KEY is missing! Set it in your environment.")
else:
    logger.info("GROQ_API_KEY loaded successfully.")

client = Groq(api_key=api_key)


def record_audio(key="mic_recorder"):
    """
    Displays mic recorder and returns WAV bytes.
    """
    logger.info("Waiting for audio input...")
    audio = mic_recorder(
        start_prompt="Start Recording",
        stop_prompt="Stop Recording",
        key=key,
        format="wav"
    )

    if audio and "bytes" in audio:
        logger.info(f"Audio captured. Size: {len(audio['bytes'])} bytes")
        return audio["bytes"]

    logger.info("No audio captured yet.")
    return None


def transcribe_audio(audio_bytes: bytes) -> str:
    """
    Converts WAV bytes to text using Groq Whisper API.
    """
    if not audio_bytes:
        logger.warning("transcribe_audio called with empty audio bytes.")
        return ""

    logger.info("Sending audio to Groq Whisper for transcription...")

    try:
        response = client.audio.transcriptions.create(
            model="whisper-large-v3",
            file=("speech.wav", audio_bytes),
            response_format="json"
        )
        text = response.text
        logger.info(f"Transcription result: {text}")
        return text

    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        return f"[Transcription failed: {e}]"
