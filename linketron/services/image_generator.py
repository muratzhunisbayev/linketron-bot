import os
from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO
from dotenv import load_dotenv

load_dotenv()

GEMINI_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_KEY)

# --- 1. THE DIRECTOR (Logic) ---
DIRECTOR_PROMPT = """
ROLE: You are a Lead 3D Set Designer.
TASK: Read the "INPUT POST" below and describe a SINGLE, TANGIBLE PHYSICAL OBJECT that represents the core theme.

INPUT POST:
{post_text}

CRITICAL RULES:
1. CONCRETE ONLY: No abstract shapes. Real objects only.
2. NO TEXT: No text inside the image.
3. NO COLORS: Do not describe colors (the style guide handles that).
4. OUTPUT: Just the object description (e.g., "A matte black chess king").
"""

# --- 2. THE ARTIST (Image Generation) ---
# Note: "gemini-2.5-flash-image" works best with a direct description
ARTIST_PROMPT_TEMPLATE = """
Generate an image of {subject_desc}.

STYLE GUIDE:
Corporate tech graphic design style. Ultra-clean 3D vector art render.
COLOR PALETTE: Strict limitation to three colors: Deep Black (#000000), Vibrant Neon Red (#FF0000), and Pure White (#FFFFFF).
BACKGROUND: Deep matte black with a very subtle, faint technical grid pattern.
COMPOSITION: High contrast, sleek, minimalist. No text.
"""

# ... (imports remain the same)

# UPDATE THE FUNCTION SIGNATURE to accept user_id
def generate_ai_image(post_text, user_id):
    print("🎨 AI Artist: Starting generation pipeline...")

    try:
        # --- PHASE 1: THE DIRECTOR ---
        response = client.models.generate_content(
            model='gemini-2.0-flash-exp',
            contents=DIRECTOR_PROMPT.format(post_text=post_text[:1000])
        )
        object_description = response.text.strip()
        print(f"🎨 Director Selected: '{object_description}'")

        # --- PHASE 2: THE ARTIST ---
        final_prompt = ARTIST_PROMPT_TEMPLATE.format(subject_desc=object_description)
        
        image_response = client.models.generate_content(
            model='gemini-2.5-flash-image', 
            contents=final_prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                safety_settings=[
                    types.SafetySetting(
                        category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                        threshold="BLOCK_ONLY_HIGH"
                    )
                ]
            )
        )

        for part in image_response.candidates[0].content.parts:
            if part.inline_data:
                image_bytes = part.inline_data.data
                
                # FIX: Use dynamic filename based on user_id
                image_path = f"temp_image_{user_id}.png"
                
                image = Image.open(BytesIO(image_bytes))
                image.save(image_path)
                
                print(f"✅ Image Generated and Saved to {image_path}.")
                return image_path, object_description

        print("❌ No image data found in response.")
        return None, "Model refused to generate image."

    except Exception as e:
        print(f"❌ Generation Error: {e}")
        return None, str(e)