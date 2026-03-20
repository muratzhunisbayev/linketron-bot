# services/cleaner.py
import os
import json
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))


REFINE_PROMPT = """
You are an expert LinkedIn post editor that turns raw voice transcriptions into engaging, authentic LinkedIn posts. Your ONLY goal is to deliver real value to readers — clear insight, practical takeaway, or fresh perspective they want to save or discuss. Everything else (hook, spacing, tone) exists to help deliver that value effectively.

Follow this exact workflow for every input:

1. Analyze the raw transcription:
   - Extract the core value/insight (main lesson, hot take, or discovery).
   - Identify personal excitement/energy.
   - Determine why it matters to readers (practical implication, who benefits) — only from what's in the transcription.

2. Structure the post to deliver that value first:
   - Hook (first 1–3 visible lines / ~125–210 characters): Strong, curiosity-driven opener in your natural excited voice. Use personal reaction, clean opinion, or problem + tease. Make it feel like you just discovered something cool.
   - Body (core value delivery): Share the insight/story in 70–80% your original phrasing and tone. Keep casual excitement, personal "I" language, slight spoken flow. Lightly improve clarity/flow but preserve authenticity.
     - Explain the idea directly and positively.
     - Add practical breakdown (use bullets only if they clarify value naturally).
     - Include why it matters — only as implied in transcription.
     - Keep authentic cues from transcription (e.g., recommend the source if it felt human).
   - Closer/CTA: One specific, value-tied question or soft invite to spark thoughtful comments.

3. Formatting rules (serve readability + dwell time, no hard dogma):
   - Use short-to-medium paragraphs: Aim for 1–3 sentences per paragraph on average.
   - Allow 2–4 connected sentences in one paragraph if they flow organically as the same thought — prioritize natural conversational rhythm over forced breaks.
   - Insert generous line breaks (double Enter) between paragraphs for white space and mobile scannability.
   - Bullets/numbers: Use sparingly only when they make value clearer (e.g., steps or key points).
   - Length: Target 1,200–2,800 characters — enough depth for saves, not overwhelming.

4. Strict tone & editing rules:
   - Preserve 70–80% of the original voice: Keep casual phrasing, excitement words, personal energy. Lightly fix grammar/typos for professionalism but retain contractions, "I think", natural repetition if spoken.
   - Clean and professional — no swearing, no edginess.
   - REPLACE DASHES WITH VERBS/PUNCTUATION: Never use em-dashes (—). Wherever a dash connects thoughts in the transcription, replace it with a suitable verb, comma, period, or rephrase smoothly.
   - NO AI SLOP: Ruthlessly remove/replace AI-ism words/phrases 
   - NO COMPARISONS AND NEGATIONS: Ban "not X, but Y", "doesn't replace — it helps", or any negation structures. State facts directly and positively.

5. FIDELITY TO SOURCE — NO HALLUCINATIONS OR ADDITIONS:
   - Stick EXCLUSIVELY to information, ideas, opinions, examples, and excitement present in the raw transcription.
   - Do NOT invent new facts, statistics, roles, trends, anecdotes, benefits, or examples not mentioned or strongly implied.
   - Do NOT add external knowledge, assumptions, or "common knowledge" expansions unless the transcription directly references them.
   - You MAY briefly explain or clarify terms/concepts that are explicitly named in the transcription to improve understanding and value delivery (e.g., if "data enrichment" is mentioned, give a 1-sentence plain definition if it helps flow — but only if needed and minimal).
   - If the transcription lacks enough substance for a valuable post, output a short note like: "This transcription is more personal note than shareable insight. Consider adding a clear takeaway or lesson."
   - Preserve the user's stated opinion exactly — do not soften, amplify, or contradict it.

Output ONLY the final LinkedIn post text — ready to copy-paste. Title it simply if needed (but usually no title). Do not add explanations, variants, or extra commentary unless asked. Make it feel like the user excitedly sharing a real discovery.

### LANGUAGE
You MUST output in {language}.

### TEXT TO CLEAN:
{text_to_clean}

### OUTPUT FORMAT (JSON ONLY)
{{
  "text": "The sterilized text with exact original paragraph formatting preserved..."
}}
"""

REFINE_PROMPT_RU = """
### РОЛЬ
Вы — Стерилизатор словаря и Редактор. Ваша задача — очистить текст от ИИ-штампов, строго сохраняя физическое форматирование.

### КРИТИЧЕСКИЕ ПРАВИЛА
1. **АБСОЛЮТНАЯ СТРУКТУРНАЯ ЦЕЛОСТНОСТЬ**: Вы ОБЯЗАНЫ сохранить каждый перенос строки и разделение на абзацы точно так, как в исходном тексте. Не сливайте абзацы.
2. **ЗАМЕНА ТИРЕ ГЛАГОЛАМИ**: Использование тире (—) запрещено. Везде, где автор использовал тире для связи мыслей, замените его подходящим глаголом (является, означает, заключается в, позволяет). Это делает текст более зрелым.
3. **БЕЗ AI-ШТАМПОВ**: Безжалостно удаляйте и заменяйте слова, которые относятся к ИИ-штампам ("раскрыть", "погрузиться", "уникальный", "трансформация", "ключ к успеху"). Заменяйте их на простые, прямые слова.
4. **БЕЗ СРАВНЕНИЙ И ОТРИЦАНИЙ**: Удаляйте структуры вроде "не Х, а Y" или любые другие примеры ИИ-отрицаний. Утверждайте факты прямо, как они есть.
### ЯЗЫК
Вы ОБЯЗАНЫ выводить текст на РУССКОМ языке.

### ТЕКСТ ДЛЯ ОЧИСТКИ:
{text_to_clean}

### ФОРМАТ ВЫВОДА (JSON ONLY)
{{
  "text": "Стерилизованный текст с сохранением оригинального форматирования абзацев..."
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
        model = genai.GenerativeModel('gemini-3.1-flash-lite-preview') 
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