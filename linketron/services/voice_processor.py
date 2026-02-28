import os
import json
import requests
import google.generativeai as genai
from dotenv import load_dotenv
from services.editor import generate_viral_post  # <--- IMPORT THE GHOST
from services.cleaner import clean_ai_slop # <--- 1. Import the new layer

load_dotenv()

# --- CONFIGURATION ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    print("❌ CRITICAL ERROR: GEMINI_API_KEY not found in .env file!")

genai.configure(api_key=GEMINI_API_KEY)

# ---------------------------------------------------------
# CRITICAL FIX: Switched to 'gemini-2.0-flash-exp' 
# 'gemini-3.0-pro-preview' was causing the infinite hang.
# ---------------------------------------------------------
model = genai.GenerativeModel('gemini-3-flash-preview')

# 1. THE CONSOLIDATED ESSAY PROMPTS
ESSAY_PROMPT = """
### ROLE
You are a Senior Professional Editor. Your task is to transform a raw, unstructured audio transcript into a polished, human-written LinkedIn post.

### OBJECTIVE
Fix the grammar, remove filler words (um, uh, like, you know), and organize the thoughts into a logical flow. 
Maintain the first-person ("I") perspective. 
Do NOT add "AI-slop" or creative flourishes that weren't in the original transcript.

### CRITICAL CONSTRAINTS
- **LANGUAGE**: Write in {language}.
- **STYLE**: Professional, dense prose. Use 3-5 sentence paragraphs.
- **NO BROETRY**: No one-sentence lines. No theatrical drama (chaos, war, battle).
- **NO CONTRASTIVE NEGATION**: Do not use "Not X, but Y." State facts directly.
- **PUNCTUATION**: Use full sentences and periods. No hyphens or dashes to connect ideas.
- **BANNED WORDS**: unlock, unleash, delve, humbled, thrilled, tapestry, game-changer.

### RAW TRANSCRIPT:
{transcript}

### OUTPUT FORMAT (JSON ONLY)
{{
  "title": "A short, professional headline (<80 chars)",
  "text": "The polished essay text here..."
}}
"""

ESSAY_PROMPT_RU = """
### РОЛЬ
Вы — старший технический редактор. Ваша задача — превратить сырой транскрипт в отполированное профессиональный пост для LinkedIn.

### ЦЕЛЬ
Исправьте грамматику, удалите слова-паразиты и структурируйте мысли. Сохраняйте повествование от первого лица («Я»). 
Не добавляйте пафоса или эпитетов, которых не было в оригинале.

### КРИТИЧЕСКИЕ ПРАВИЛА
1. **ЯЗЫК**: Пишите строго на РУССКОМ языке.
2. **ПЛОТНАЯ ПРОЗА**: Используйте полноценные абзацы по 3-5 предложений. Никаких однострочных предложений.
3. **НИКАКИХ ТИРЕ**: Стройте полные предложения с глаголами. Не используйте тире (—) для связи мыслей.
4. **БЕЗ ОТРИЦАНИЙ**: Избегайте структуры «не Х, а Y». Утверждайте факты прямо.
5. **БЕЗ AI-ШТАМПОВ**: Запрещены слова «раскрыть», «погрузиться», «уникальный», «трансформация».

### ТРАНСКРИПТ:
{transcript}

### ФОРМАТ ВЫВОДА (JSON ONLY)
{{
  "title": "Краткий заголовок",
  "text": "Отполированный текст эссе..."
}}
"""

# --- FUNCTIONS ---



def transcribe_audio_groq(file_path):
    """Step 1: The Ear (Groq)"""
    if not GROQ_API_KEY: return "Error: Missing GROQ_API_KEY"
    
    url = "https://api.groq.com/openai/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
    
    with open(file_path, "rb") as file:
        files = {"file": (os.path.basename(file_path), file, "audio/ogg")}
        data = {"model": "whisper-large-v3", "response_format": "json"}
        
        try:
            response = requests.post(url, headers=headers, files=files, data=data)
            if response.status_code != 200: return f"Groq Error: {response.text}"
            return response.json().get("text", "")
        except Exception as e:
            return f"Transcribe Exception: {str(e)}"
        
def generate_essay_draft(raw_text, language):
    """Simplified single-path generation."""
    selected_prompt = ESSAY_PROMPT_RU if language in ["Russian", "ru"] else ESSAY_PROMPT
    
    try:
        response = model.generate_content(
            selected_prompt.format(transcript=raw_text, language=language),
            generation_config={"response_mime_type": "application/json"}
        )
        return json.loads(response.text.strip())
    except Exception as e:
        return {"title": "Error", "text": f"Drafting Error: {str(e)}"}

def process_voice_note(file_path, language="English", research_context=None):
    """The simplified pipeline."""
    # 1. Transcription
    raw_text = transcribe_audio_groq(file_path)
    
    # 2. Drafting (Branches only if research is present)
    if research_context:
        # Uses your updated editor.py for research-backed essays
        initial_draft = generate_viral_post(research_context, raw_text, language)
    else:
        # Uses the new single essay logic
        initial_draft = generate_essay_draft(raw_text, language)

    # 3. Cleanup Logic
    draft_text = initial_draft.get('text') or initial_draft.get('post')
    draft_title = initial_draft.get('title') or "Professional Insight"
    print(f"DEBUG: Text being sent to CLEANER: {draft_text[:100]}...")
    if not draft_text:
        print("DEBUG ALERT: draft_text is EMPTY before cleaner!")

    # 4. Final Refinement (Cleaner.py handles the slop)
    refined_post = clean_ai_slop(draft_text, language)
    print(f"DEBUG: Cleaner output: {refined_post}")
    
    return {
        "title": refined_post.get("title") or draft_title,
        "text": refined_post.get("text") or draft_text
    }