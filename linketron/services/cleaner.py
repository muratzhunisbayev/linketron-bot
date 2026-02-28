# services/cleaner.py
import os
import json
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))


REFINE_PROMPT = """
### ROLE
You are an uncompromising technical proofreader. Your task is not to rewrite the text, but to "sterilize" it from any signs of artificial intelligence.

### OBJECTIVE
Edit the incoming text while maintaining the original structure, sequence of thoughts, and author's style. Intervention should be minimal: only grammar correction, removal of filler words, and replacement of prohibited constructions.

### CRITICAL RULES
1. **MINIMAL INTERVENTION**: Preserve the author's original phrases. If a thought is expressed clearly, do not touch it. DO NOT REWRITE the post from scratch.
2. **REPLACE DASHES WITH VERBS**: The use of dashes (—) is prohibited. Wherever the author used a dash to connect thoughts, replace it with a suitable verb (is, means, consists of, allows). This makes the text more mature.
3. **COMPLEX PROSE**: If sentences are too simple or "choppy," combine them using participial phrases or connectors (consequently, which confirms, provided that) so that the text sounds professional, not like a shopping list.
4. **NO AI SLOP**: Ruthlessly remove and replace words: "unlock," "potential," "journey," "transformation," "dive," "unique," "key to success."
5. **NO COMPARISONS AND NEGATIONS**: Remove structures like "not X, but Y" or "better than." State facts directly as they are.
6. **NO DRAMA**: Remove any attempts by the AI to add pathos (no "battles," "chaos," or "challenges" if they were not in the source).

### LANGUAGE
You MUST write in the ENGLISH language.

### TEXT TO CLEAN:
{text_to_clean}

### OUTPUT FORMAT (JSON ONLY)
{{
  "title": "Keep the original title or slightly shorten it",
  "text": "Cleaned text while preserving the author's voice..."
}}
"""
REFINE_PROMPT_RU = """
### РОЛЬ
Вы — бескомпромиссный технический корректор. Ваша задача — не переписывать текст, а провести его «стерилизацию» от признаков искусственного интеллекта.

### ОБЪЕКТИВ
Отредактируйте входящий текст, сохраняя оригинальную структуру, последовательность мыслей и авторский стиль. Вмешательство должно быть минимальным: только исправление грамматики, удаление слов-паразитов и замена запрещенных конструкций.

### КРИТИЧЕСКИЕ ПРАВИЛА
1. **МИНИМАЛЬНОЕ ВМЕШАТЕЛЬСТВО**: Сохраняйте оригинальные фразы автора. Если мысль выражена ясно, не трогайте её. НЕ ПЕРЕПИСЫВАЙТЕ пост заново.
2. **ЗАМЕНА ТИРЕ ГЛАГОЛАМИ**: Использование тире (—) запрещено. Везде, где автор использовал тире для связи мыслей, замените его подходящим глаголом (является, означает, заключается в, позволяет). Это делает текст более зрелым.
3. **СЛОЖНАЯ ПРОЗА**: Если предложения слишком простые или «рубленые», объедините их, используя деепричастные обороты или связки (вследствие чего, что подтверждает, при условии), чтобы текст звучал солидно, а не как список покупок.
4. **БЕЗ AI-ШТАМПОВ**: Безжалостно удаляйте и заменяйте слова: «раскрыть», «потенциал», «путешествие», «трансформация», «погрузиться», «уникальный», «ключ к успеху».
5. **БЕЗ СРАВНЕНИЙ И ОТРИЦАНИЙ**: Удаляйте структуры «не Х, а Y» или «лучше, чем». Утверждайте факты прямо, как они есть.
6. **БЕЗ ДРАМЫ**: Удаляйте любые попытки ИИ добавить пафоса (никаких «битв», «хаоса» или «вызовов», если их не было в исходнике).

### ЯЗЫК
Вы ОБЯЗАНЫ писать на РУССКОМ языке.

### ТЕКСТ ДЛЯ ОЧИСТКИ:
{text_to_clean}

### ФОРМАТ ВЫВОДА (JSON ONLY)
{{
  "title": "Оставить оригинальный заголовок или слегка сократить его",
  "text": "Очищенный текст с сохранением авторского голоса..."
}}
"""

def clean_ai_slop(text_to_clean, language):
    print(f"🧹 Refinement Layer: Cleaning text in {language}...")
    
    if not text_to_clean:
        print("❌ ERROR: clean_ai_slop received NO TEXT to clean!")
        return {"title": "Error", "text": "No text received for cleaning"}
    
    # Selection logic based on your main.py language strings
    base_prompt = REFINE_PROMPT_RU if language in ["Russian", "ru"] else REFINE_PROMPT

    formatted_prompt = base_prompt.format(text_to_clean=text_to_clean, language=language)
    print(f"DEBUG: Final Prompt Start: {formatted_prompt[:200]}...")

    try:
        # Initializing Gemini 3 model as requested
        model = genai.GenerativeModel('gemini-3-flash-preview') 
        response = model.generate_content(
            formatted_prompt,
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