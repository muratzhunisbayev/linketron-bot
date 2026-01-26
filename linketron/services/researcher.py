import os
import requests
import json
import re  # <--- NEW: For robust JSON cleaning
import logging
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# --- CONFIGURATION ---
PERPLEXITY_KEY = os.getenv("PERPLEXITY_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") 

genai.configure(api_key=GEMINI_API_KEY)
# Using Flash for speed on the "Angle Generation"
model = genai.GenerativeModel('gemini-2.0-flash-exp') 

# --- 1. DEFINITIONS ---
BUCKET_DEFINITIONS = {
    "lens_principle": "timeless mental models, cognitive biases, or psychological frameworks in business",
    "lens_case_study": "specific company case studies (wins or failures) from 2025-2026",
    "lens_growth": "tactical growth hacking experiments, marketing tools, or viral strategies",
    "lens_controversial": "polarizing debates, unpopular opinions, or hot takes in the tech/business world",
}

# --- 2. THE PROMPT TEMPLATE ---
RESEARCH_PROMPT_TEMPLATE = """
ROLE: You are an Investigative Data Journalist.

ASSIGNED LENS: {lens_name}
CONTEXT: {lens_context}

TASK:
Dig deep to find a specific, concrete example. Do not provide generic advice.
Find a specific entity (a specific ad, a specific person, a specific experiment).

OUTPUT FORMAT (JSON ONLY):
{{
  "headline_fact": "The single most surprising number or result (e.g. 'Generated $5M in 24 hours')",
  "subject_name": "The specific name of the book, person, or campaign",
  "origin_story": "Context on where this came from",
  "core_mechanism": "The technical explanation of WHY it works",
  "viral_angle": "The counter-intuitive insight or tension (The 'Conflict')",
  "proof_points": ["Stat 1", "Stat 2", "Quote"],
  "actionable_step": "One concrete step for founders"
}}
"""

# --- 3. HELPER FUNCTIONS ---

def generate_search_angle(base_topic):
    prompt = f"Give me a specific, unique, non-obvious search angle for: '{base_topic}'. Output just the angle phrase."
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except:
        return "focus on recent trends"

def search_perplexity(lens_key, custom_topic=None):
    """
    The Core Researcher.
    """
    print(f"🔍 Researcher: Initiating search for '{lens_key}'...")

    # A. Determine Context
    if lens_key == "lens_custom" and custom_topic:
        base_context = custom_topic
        lens_name = "Custom Topic"
    else:
        base_context = BUCKET_DEFINITIONS.get(lens_key, "business trends")
        lens_name = lens_key.replace("lens_", "").title().replace("_", " ")

    # B. Generate Infinite Angle
    angle = generate_search_angle(base_context)
    full_context = f"{base_context}. {angle}."
    
    # C. Prepare Request
    url = "https://api.perplexity.ai/chat/completions"
    formatted_prompt = RESEARCH_PROMPT_TEMPLATE.format(lens_name=lens_name, lens_context=full_context)
    
    payload = {
        "model": "sonar-pro", 
        "messages": [
            {"role": "system", "content": "You are a helpful research assistant. You answer ONLY in valid JSON format."},
            {"role": "user", "content": formatted_prompt}
        ],
        "temperature": 0.2
    }
    headers = {"Authorization": f"Bearer {PERPLEXITY_KEY}", "Content-Type": "application/json"}

    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        
        # Cleanup JSON with Regex (Fixes the "None" issue)
        raw_content = response.json()['choices'][0]['message']['content']
        
        # Use regex to find the first '{' and the last '}'
        json_match = re.search(r'\{.*\}', raw_content, re.DOTALL)
        if json_match:
            clean_json_text = json_match.group(0)
            parsed_data = json.loads(clean_json_text)
        else:
            raise ValueError("No JSON found in response")
        
        # Add metadata for the bot
        parsed_data["meta_lens"] = lens_name
        parsed_data["meta_angle"] = angle
        return parsed_data

    except Exception as e:
        print(f"❌ Research Error: {e}")
        return {"headline_fact": "Error", "subject_name": "System Error", "origin_story": str(e), "viral_angle": "N/A"}

def format_card_text(data):
    """
    UPDATED: SIMPLIFIED DISPLAY.
    Only shows the 'Spark' to get the user talking.
    """
    if data.get("headline_fact") == "Error" or data.get("subject_name") == "System Error":
        return f"❌ **Search Failed:** {data.get('origin_story')}"

    # We extract just the provocative bits
    return (
        f"🕵️ **Briefing: {data.get('meta_lens', 'Topic')}**\n"
        f"📐 *Angle: {data.get('meta_angle', 'N/A')}*\n\n"
        f"🔥 **{data.get('subject_name', 'Topic Found')}**\n\n"
        f"📊 **The Spark:** {data.get('headline_fact', 'Data not found')}\n"
        f"⚔️ **The Angle:** {data.get('viral_angle', 'No conflict found')}\n\n"
        f"👇 **What is your take?**\n"
        f"Record a voice note. Do you agree, or is this nonsense?"
    )