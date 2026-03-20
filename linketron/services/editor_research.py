import os
import json
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

WRITER_PROMPT = """
INPUT RESEARCH DATA (The Facts):
{research_data}

USER AUDIO TRANSCRIPT (The Angle/Opinion):
"{user_transcript}"

LANGUAGE: 
"{language}"

INSTRUCTION:
1. Use "INPUT RESEARCH DATA" as the factual source. Do NOT invent new facts.
2. Use "USER AUDIO TRANSCRIPT" to shape the opinion or specific angle of the post.
   - If the transcript is empty or generic, rely on the research.
   - If the transcript disagrees with the research, write a "Contrarian" post.
3. Use "LANGUAGE": You MUST write the entire output (title and text) in that {language}.
---

ROLE: You're an expert in viral LinkedIn posts content creation with 10 years of experience. You've created viral posts that have gotten 10 billion views in total. You also write as human as possible not as an AI.

OBJECTIVE: Your goal is to write a 1) title and 2) text for my next LinkedIn Post. They should be super valuable to my audience.

SCENARIO: I run a LinkedIn blog about marketing and sales. My audience is marketers, salespeople, founders, B2B business owners, B2C business owners, brands. My goal is to help them build better brands with valuable, and practical content.

EXPECTATION:   
- Title: First sentence <80 chars, ultra hooking.
- Text: 150-200 words. Short paragraphs (1-2 lines).
- Output: Valid JSON format only.

Make sure to have great: hook, retention, and reward at the end.
The post should clearly lead to a marketing/sales insight.

STYLE & ANTI-PATTERNS (CRITICAL):
### CRITICAL CONSTRAINTS
1. **LANGUAGE**: You MUST write the entire output (title and text) in {language}. 
2. **NO COMPARATIVE LANGUAGE**: Do not use "more than," "less than," "better," or "worse." Do not compare two states. State only the current reality.
3. **NO CONTRASTIVE NEGATIONS**: Do not use "It is not X, but Y." State what the thing is directly.
4. **NO ROBOTIC HYPHENS**: Do not use hyphens to connect ideas. Use full verbs and complete sentences.
5. **DENSE PARAGRAPHS**: Use traditional 3-5 sentence paragraphs. No one-sentence lines.
6. **NO AI-SLOP**: Strictly ban: "unlock," "unleash," "dive," "humbled," "thrilled."
7. **NO PREACHY OUTROS**: Avoid "Remember," or "In conclusion,". Just end with the punchline or question.

OUTPUT FORMAT (JSON ONLY):
{{
  "text": "The full post body here..."
}}
"""

WRITER_PROMPT_RU = """
ДАННЫЕ ИССЛЕДОВАНИЯ:
{research_data}

ТРАНСКРИПТ ПОЛЬЗОВАТЕЛЯ:
"{user_transcript}"

### РОЛЬ
Вы — зрелый профессионал. Вы пишете ясно, честно и с человеческим подходом. Вы выражаетесь прямо, но не как робот.

### ЦЕЛЬ
Напишите заголовок и текст поста для LinkedIn. Сохраняйте повествование от первого лица («Я») и оберегайте человеческий элемент истории.

### КРИТИЧЕСКИЕ ПРАВИЛА
1. **ЯЗЫК**: Вы ОБЯЗАНЫ написать весь текст на РУССКОМ языке.
2. **БЕЗ СРАВНИТЕЛЬНОЙ «ВОДЫ»**: Не используйте «более чем», «менее чем» или «лучше/хуже». Описывайте текущую реальность как факт.
3. **БЕЗ КОНТРАСТНЫХ ОТРИЦАНИЙ**: Запрещено использовать структуру «не Х, а Y». Утверждайте прямо, чем является объект.
4. **НИКАКОЙ ДРАМЫ**: Удалите искусственное напряжение (никаких «битв», «хаоса», «разбитых надежд»).
5. **НИКАКИХ ТИРЕ И ДЕФИСОВ**: Стройте полные предложения с глаголами и точками. Не используйте тире (—) для связи мыслей.
6. **ПЛОТНЫЕ АБЗАЦЫ**: Используйте традиционные абзацы по 3-5 предложений. Никаких однострочных предложений.
7. **БЕЗ AI-ШТАМПОВ**: Строго запрещены слова «раскрыть», «погрузиться», «уникальный», «трансформация», «путешествие».

### OUTPUT FORMAT (JSON ONLY):
{{
  "text": "Полный текст поста..."
}}
"""

def generate_viral_post(research_json, user_transcript, language):
    """Generates a post draft by combining research data and user transcript."""
    print(f"✍️ Research Editor: Connecting Research + Voice in {language}...")
    
    try:
        research_text = json.dumps(research_json, indent=2)
        clean_transcript = user_transcript if user_transcript else "Focus on technical facts and professional insight."
        
        selected_prompt = WRITER_PROMPT_RU if language in ["Russian", "ru"] else WRITER_PROMPT
        model = genai.GenerativeModel('gemini-3.1-flash-lite-preview')
        
        response = model.generate_content(
            selected_prompt.format(
                research_data=research_text, 
                user_transcript=clean_transcript,
                language=language
            ),
            generation_config={"response_mime_type": "application/json"}
        )
        
        clean_text = response.text.strip()
        if clean_text.startswith("```json"):
            clean_text = clean_text[7:]
        if clean_text.endswith("```"):
            clean_text = clean_text[:-3]
            
        return json.loads(clean_text)

    except Exception as e:
        print(f"❌ Research Editor Error: {e}")
        return {
            "title": "Error Generating Post",
            "text": f"An error occurred while writing: {e}"
        }