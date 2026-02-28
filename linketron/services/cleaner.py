# services/cleaner.py
import os
import json
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

REFINE_PROMPT = """
### ROLE
You are a Mature Professional. You write with clarity, integrity, and a human touch. You are direct but not robotic.

### OBJECTIVE
Rewrite the input text into a polished LinkedIn post. Maintain the first-person perspective ("I") and preserve the human element of the story.

### CRITICAL RULES
1. **PRESERVE EXPRESSED EMOTION**: If the user explicitly mentions a feeling (e.g., "I was worried," "I felt relieved," "I am proud"), KEEP IT. Do not strip out the human experience.
2. **NO MANUFACTURED DRAMA**: Do not add theatricality that wasn't in the original transcript. Avoid "battlefields," "chaos," or "shattered dreams" unless the user used those exact words.
3. **NOUN PRESERVATION**: Keep specific physical details (terminal, coffee cups, server logs, Astana).
4. **NO COMPARATIVE SLOP**: Do not use "more than," "less than," or "not X but Y." State facts and feelings directly. 
   - Bad: "This is more than just code."
   - Good: "This code represents months of technical work."
5. **NO HYPHENS OR DASHES**: Construct full sentences with proper verbs and periods. No robotic fragments.
6. **NO AI-SLOP**: Strictly ban "unlock," "tapestry," "delve," "humbled," or "game-changer."

### LANGUAGE
You MUST write the entire output in: {language}.

### INPUT TEXT:
{text_to_clean}

### OUTPUT FORMAT (JSON ONLY)
{{
  "title": "original title",
  "text": "The refined text here..."
}}
"""

REFINE_PROMPT_RU = """
### РОЛЬ

### ОБЪЕКТИВ
Перепишите входящий текст в пост для LinkedIn. Просто следуйте правилам ниже.

### КРИТИЧЕСКИЕ ПРАВИЛА
1. **СЛОЖНАЯ ПРОЗА**: Избегайте рубленых, детских предложений. Используйте деепричастные обороты и сложные связки (поскольку, вследствие чего, в то время как), чтобы текст звучал солидно.
2. **ЗАМЕНА ТИРЕ ГЛАГОЛАМИ**: Поскольку тире запрещено, используйте полноценные глаголы (является, представляет собой, заключается в, означает). Это сделает речь более живой.

5. **НИКАКОЙ ДРАМЫ**: 
6. **БЕЗ СРАВНЕНИЙ И ОТРИЦАНИЙ**: Никаких "не Х, а Y" или "лучше, чем". Утверждайте факты прямо. 
7. **БЕЗ AI-ШТАМПОВ**: Никаких "раскрыть потенциал", "путешествие" или "трансформация".

### ЯЗЫК
Вы ОБЯЗАНЫ писать на РУССКОМ языке.

### ФОРМАТ ВЫВОДА (JSON ONLY)
{{
  "title": "Оригинальный заголовок",
  "text": "Плотный, глубокий и профессиональный текст поста..."
}}
"""

# def clean_ai_slop(text, language):
#     """The Final Refinement Layer: Strips drama, comparisons, and hyphens."""
#     model = genai.GenerativeModel('gemini-3-flash-preview') # Fast and precise for editing
    
#     try:
#         response = model.generate_content(
#             REFINE_PROMPT.format(text_to_clean=text, language=language),
#             generation_config={"response_mime_type": "application/json"}
#         )
#         return json.loads(response.text.strip())
#     except Exception as e:
#         print(f"❌ Refinement Error: {e}")
#         return {"title": "Refinement Error", "text": text}
 
# services/cleaner.py

def clean_ai_slop(text_to_clean, language):
    print(f"🧹 Refinement Layer: Cleaning text in {language}...")
    
    # Selection logic based on your main.py language strings
    base_prompt = REFINE_PROMPT_RU if language in ["Russian", "ru"] else REFINE_PROMPT

    try:
        model = genai.GenerativeModel('gemini-3-flash-preview') 
        response = model.generate_content(
            base_prompt.format(text_to_clean=text_to_clean, language=language),
            generation_config={"response_mime_type": "application/json"}
        )
        
        parsed = json.loads(response.text.strip())
        
        # INSURANCE: If AI returns a list, take the first item
        if isinstance(parsed, list):
            parsed = parsed[0]
            
        return parsed

    except Exception as e:
        print(f"❌ Refinement Error: {e}")
        return {"title": "Refinement Error", "text": text_to_clean}