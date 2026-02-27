import os
import json
import logging
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# Configure Gemini
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    logging.error("❌ GEMINI_API_KEY is missing in .env")
else:
    genai.configure(api_key=api_key)

# --- SOPHISTICATED VIRAL PROMPT ---
WRITER_PROMPT = """
INPUT RESEARCH DATA (The Facts):
{research_data}

USER AUDIO TRANSCRIPT (The Angle/Opinion):
"{user_transcript}"

INSTRUCTION:
1. Use "INPUT RESEARCH DATA" as the factual source. Do NOT invent new facts.
2. Use "USER AUDIO TRANSCRIPT" to shape the opinion or specific angle of the post.
   - If the transcript is empty or generic, rely on the research.
   - If the transcript disagrees with the research, write a "Contrarian" post.

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
1. NO "NOT X, BUT Y" STRUCTURES:
   - Bad: "It is not about the price, but about the value."
   - Good: "The price is irrelevant. Only value matters."
2. NO ROBOTIC HYPHENS:
   - Bad: "The result - a massive increase in sales."
   - Good: "The result was a massive increase in sales."
3. NO "LABEL: EXPLANATION" BULLETS:
   - Bad: "• Specificity: Use exact numbers."
   - Good: "• Use exact numbers like '503 agencies' instead of generic terms."
4. BANNED VOCABULARY:
   - Do not use: "Unlock", "Unleash", "Elevate", "Delve", "Game-changer", "In today's landscape", "Foster", "Harness".
5. NO PREACHY OUTROS:
   - Avoid "Remember," or "In conclusion,". Just end with the punchline or question.

OUTPUT FORMAT (JSON ONLY):
{{
  "title": "The headline here",
  "text": "The full post body here..."
}}
"""

def generate_viral_post(research_json, user_transcript):
    """
    Takes structured research + user voice and writes the post using strict viral rules.
    """
    print("✍️ Editor: Connecting Research + Voice...")
    
    try:
        # 1. Prepare the input
        research_text = json.dumps(research_json, indent=2)
        # Handle cases where user didn't speak
        clean_transcript = user_transcript if user_transcript else "No specific opinion given. Focus on the facts."
        
        # 2. Select Model (Gemini 2.0 Flash is fast and smart enough for this)
        model = genai.GenerativeModel('gemini-3-flash-preview')
        
        # 3. Call the API
        response = model.generate_content(
            WRITER_PROMPT.format(
                research_data=research_text, 
                user_transcript=clean_transcript
            ),
            generation_config={"response_mime_type": "application/json"} # Forces JSON
        )
        
        # 4. Parse Response
        clean_text = response.text.strip()
        # Remove potential markdown wrapping
        if clean_text.startswith("```json"):
            clean_text = clean_text[7:]
        if clean_text.endswith("```"):
            clean_text = clean_text[:-3]
            
        return json.loads(clean_text)

    except Exception as e:
        print(f"❌ Editor Error: {e}")
        return {
            "title": "Error Generating Post",
            "text": f"An error occurred while writing: {e}"
        }