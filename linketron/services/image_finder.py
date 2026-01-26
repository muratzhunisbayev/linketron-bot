import os
import requests
import json
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

SERPER_KEY = os.getenv("SERPER_API_KEY")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_KEY)

def get_image_from_web(post_text):
    """
    1. Asks Gemini for a search keyword based on the post.
    2. Searches Google Images via Serper.
    3. Returns the Image URL.
    """
    print("🌍 Image Finder: Analyzing post for visuals...")

    # --- SUB-STEP 1: GET THE SEARCH TERM ---
    try:
        model = genai.GenerativeModel('gemini-2.5-flash') # Or 2.5/1.5
        prompt = (
            f"Read this LinkedIn post and give me ONE distinct, concrete, physical object "
            f"that represents the concept. Output ONLY the search query. "
            f"Do not use abstract words like 'Growth' or 'Success'. "
            f"Example: 'Server room blue lighting' or 'Handshake business close up'.\n\n"
            f"POST: {post_text[:500]}"
        )
        response = model.generate_content(prompt)
        search_query = response.text.strip()
        print(f"🔍 Search Query: '{search_query}'")

    except Exception as e:
        print(f"❌ Query Gen Error: {e}")
        search_query = "Business technology professional" # Fallback

    # --- SUB-STEP 2: GOOGLE SEARCH ---
    url = "https://google.serper.dev/images"
    payload = json.dumps({"q": search_query})
    headers = {
        'X-API-KEY': SERPER_KEY,
        'Content-Type': 'application/json'
    }

    try:
        response = requests.post(url, headers=headers, data=payload)
        results = response.json()
        
        # Grab the first image
        if "images" in results and len(results["images"]) > 0:
            image_url = results["images"][0]["imageUrl"]
            return image_url, search_query
        else:
            return None, search_query

    except Exception as e:
        print(f"❌ Search Error: {e}")
        return None, search_query