import os
import requests
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

def transcribe_audio_groq(file_path):
    """
    Pure transcription layer. 
    Takes an audio file path, sends it to Groq, and returns the raw text string.
    """
    if not GROQ_API_KEY: 
        return "Error: Missing GROQ_API_KEY"
    
    url = "https://api.groq.com/openai/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
    
    with open(file_path, "rb") as file:
        files = {"file": (os.path.basename(file_path), file, "audio/ogg")}
        data = {"model": "whisper-large-v3", "response_format": "json"}
        
        try:
            response = requests.post(url, headers=headers, files=files, data=data)
            if response.status_code != 200: 
                return f"Groq Error: {response.text}"
            print(f"The raw voice transcription:\n---------------------------------------------\n{response.json().get('text', '')}")
            return response.json().get("text", "")
        except Exception as e:
            return f"Transcribe Exception: {str(e)}"
