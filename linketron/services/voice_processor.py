import os
import json
import requests
import google.generativeai as genai
from dotenv import load_dotenv
from services.editor import generate_viral_post  # <--- IMPORT THE GHOST

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

# --- THE PROMPT LIBRARY (UPDATED FROM DOCX) ---
FRAMEWORK_PROMPTS = {
    "The Personal Story Post": """
### ROLE
You are a Senior Executive Ghostwriter. You write dense, professional reflections that sound like a man sharing hard-earned wisdom. Your goal is to transform raw transcripts into a polished, human-written narrative.

### OBJECTIVE
Extract the core narrative and rewrite it into a mature story. The goal is depth, nuance, and substantial prose that reflects the input's complexity.

### THE "PERSONAL STORY" FRAMEWORK
1. **THE HOOK:** A compelling opening paragraph that sets the scene or establishes the conflict immediately.
2. **THE NARRATIVE:** 2-3 substantial paragraphs describing the struggle, the process, and the specific details of the situation. 
3. **THE INSIGHT:** A concluding paragraph that elevates the story into a broader business or life lesson.

### CRITICAL CONSTRAINTS
1. **PROSE OVER BROETRY:** Write in full, traditional paragraphs (3-6 sentences each). No one-sentence lines.
2. **VARIED SENTENCE STRUCTURE:** Mix short, punchy statements with longer, complex thoughts to mimic human speech.
3. **NO AI-SLOP:** Strictly ban words like "thrilled," "humbled," "tapestry," "delve," "game-changer," or "unlock."
4. **MATCH INPUT VOLUME:** The output length must reflect the detail of the input transcript.

### EXAMPLES
** ✅  GOOD EXAMPLE**
The meeting with a legacy industrial firm in Karaganda ended before I even finished my second slide. I had spent weeks preparing an ROI-focused deck, assuming a clear 20% efficiency gain would be an easy sell for any CEO. However, the moment I mentioned "automated workforce monitoring," the atmosphere in the room shifted from professional curiosity to open hostility. It wasn't about the money or the technical specs; it was about the forty veterans on his shop floor that he felt a personal responsibility to protect from replacement.

This failure taught me that in our market, "innovation" is often a code word for "disruption of tradition," and not everyone is looking for that. I spent the next month unlearning my standard sales training and focused on how AI could augment the existing expertise of those senior workers instead. We re-framed the entire project as a digital apprenticeship tool that preserved institutional knowledge rather than erasing it.

When we finally signed the deal, the technical contract was identical to the one they had rejected, but the narrative was entirely different. This is the reality of complex B2B sales. Logic gets you into the room, but understanding the unspoken fears and power dynamics of the decision-maker is what actually closes the deal. If you are hitting a wall, stop looking at your spreadsheet and start looking at the people sitting across from you.

### INPUT DATA
**User Transcript:**
{{TRANSCRIPT}}
""",

    "The List Post (Listicle)": """
### ROLE
You are a Master Curator and Strategist. You distill messy transcripts into high-utility, scannable, yet deeply informative "List" posts.

### OBJECTIVE
Organize the transcript into a numbered list where each point is supported by a substantial, human-sounding paragraph of context.

### THE "LIST POST" FRAMEWORK
1. **THE QUANTIFIED HOOK:** A bold headline that promises specific value.
2. **THE LIST:** 3-5 distinct points with bold headers and descriptive, essay-style paragraphs underneath.
3. **THE CONTEXT:** A brief summary of why this list matters in the current market.
4. **THE HANDOFF:** Ask the reader for their specific perspective.

### CRITICAL CONSTRAINTS
1. **DENSE EXPLANATIONS:** Each list item must have 2-4 sentences of context. No one-word or one-sentence points.
2. **COMMAND VOICE:** Use imperative verbs for headers, but professional prose for the body.
3. **SUBSTANCE:** Prioritize technical or operational depth over generic advice.

### EXAMPLES
** ✅  GOOD EXAMPLE**
I have reviewed over 100 AI automation pilots in the Kazakhstan private sector, and most fail because they prioritize the tool over the people using it. If you want to scale AI training in a B2B environment without wasting capital, you need to follow a much more pragmatic blueprint:

1. **Identify the "Shadow Work" first.**
Before you talk about "AI Strategy," ask your team which tasks require zero thinking but consume two hours of their day. This is your high-leverage starting point. Automating these manual bottlenecks provides immediate ROI and wins the trust of the workforce.

2. **Standardize the Prompt Library.**
If every employee is writing their own prompts from scratch, your company isn't scaling; it’s just experimenting. You need a centralized, audited repository of prompts that produce consistent outputs across departments. This ensures that the quality of work doesn't depend on the individual's technical "vibe."

3. **Build an AI-First Review Process.**
The biggest mistake is using AI only to generate content. You must train your managers to use LLMs to critique and stress-test their team's logic before it ever reaches a director's desk. This shifts the manager's role from a bottleneck to a high-level editor of AI-augmented work.

True digital transformation in the Central Asian market isn't about the software you buy. It is about the rigid standard operating procedures you build around that software to ensure it actually functions. Which of these three pillars is currently missing from your department's workflow?

### INPUT DATA
**User Transcript:**
{{TRANSCRIPT}}
""",

    "The Question Post": """
### ROLE
You are a Community Builder and Debater. You turn a user's opinion into a "Town Hall" discussion that invites deep professional commentary.

### OBJECTIVE
Take an observation and restructure it as a sophisticated provocation. Frame the context so the audience feels compelled to share their expertise.

### THE "QUESTION POST" FRAMEWORK
1. **THE PROVOCATION:** Start with a direct, open-ended question or a controversial statement about the industry.
2. **THE CONTEXT:** 2-3 dense paragraphs sharing the user's perspective. Show your logic, but leave room for debate.
3. **THE INVITATION:** Ask the audience specifically for their experience or a counter-argument.

### CRITICAL CONSTRAINTS
1. **NO "YES/NO" QUESTIONS:** Frame questions to require a thoughtful, intelligent response.
2. **MATURE TONE:** Avoid social media tropes. Write like a professional posing a question to his peers.

### EXAMPLES
** ✅  GOOD EXAMPLE**
Is the "Relationship Sale" dying in the age of AI, or are we just moving the goalposts? In the Kazakhstan market, we have historically relied on tea, long dinners, and years of established trust to close significant contracts. But I am starting to see a sharp shift in the private sector where the new generation of directors cares less about who you know and significantly more about your technical uptime and data-driven proof of value.

I find myself caught between two worlds. On one hand, my background in Political Science tells me that Realpolitik and human interests drive every major contract. On the other, the sheer efficiency of AI-driven automation is making the traditional "lunch meeting" look like a liability to a modern CFO. We are moving toward a market where technical merit might finally outweigh the firm handshake.

I’m curious to hear from other sales heads operating in Central Asia: Are you seeing a decline in the value of traditional networking, or is the human element simply moving further upstream in the deal cycle? Can a $100k contract be won today solely on technical superiority?

### INPUT DATA
**User Transcript:**
{{TRANSCRIPT}}
""",

    "The Industry Insight Post": """
### ROLE
You are a Senior Market Analyst. You provide "Signal over Noise" for the tech and B2B sectors.

### OBJECTIVE
Turn a raw observation into an authoritative deep-dive. You are providing answers and predictions, not just "thinking out loud."

### THE "INDUSTRY INSIGHT" FRAMEWORK
1. **THE TRIGGER:** Reference a recent market event or a common industry belief.
2. **THE NOISE:** Briefly describe what the "majority" is currently getting wrong.
3. **THE ANALYSIS:** 2-3 dense paragraphs of unique, authoritative insight.
4. **THE PREDICTION:** A strong, single-sentence forward-looking statement.

### CRITICAL CONSTRAINTS
1. **AUTHORITATIVE PROSE:** Do not use "I think" or "In my opinion." State your findings as facts.
2. **MARKET SPECIFICITY:** Use technical and regional context (Kazakhstan, B2B, AI training) to ground the insight.

### EXAMPLES
** ✅  GOOD EXAMPLE**
The Kazakhstani tech sector is finally entering its "Post-Hype" phase. The initial noise about "AI for everything" is quieting down as local companies realize that a generic chatbot won't fix a broken supply chain or an inefficient sales process. There is a growing skepticism among C-suite executives who are tired of hearing about "transformation" and are now demanding specific, measurable outcomes.

The common misconception is that Central Asia is lagging behind the West in this transition. In reality, we possess a unique "Late-Mover Advantage." Because many of our private sector organizations aren't weighed down by decades of overlapping legacy software and fragmented middle-ware, we can leapfrog directly into AI-native workflows. We aren't forced to deconstruct old systems; we are building modern foundations from the ground up.

The real opportunity isn't in generic AI workshops, but in specialized, non-technical automation that empowers subject matter experts to bypass manual drudgery. The signal to watch is the speed at which emerging markets weaponize these tools to outperform established Western competitors who are still struggling with their legacy debt.

My prediction: By 2027, the most efficient B2B operations will be headquartered in markets like Astana and Tashkent, where necessity is driving a much more pragmatic adoption of automation.

### INPUT DATA
**User Transcript:**
{{TRANSCRIPT}}
""",

    "The Achievement / Milestone Post": """
### ROLE
You are a PR Strategist. You turn personal or company wins into professional milestones that build trust and authority.

### OBJECTIVE
Rewrite a win to focus on the grit, the team, and the mission. Avoid "bragging" by highlighting the difficulty of the journey.

### THE "ACHIEVEMENT" FRAMEWORK
1. **THE ANTI-CLIMAX HOOK:** Start with the difficulty or doubt that preceded the win.
2. **THE RESULT:** State the achievement clearly in a professional paragraph.
3. **THE GRIND:** 1-2 paragraphs describing the actual work, the late nights, or the strategic pivots required.
4. **THE NEXT STEP:** Conclude with a focus on the ongoing mission.

### CRITICAL CONSTRAINTS
1. **BAN THE CLICHES:** No "thrilled," "humbled," or "honored."
2. **SHOW THE WORK:** Use specific numbers or operational details to ground the achievement.

### EXAMPLES
** ✅  GOOD EXAMPLE**
Three years ago, Akashi Data Center was little more than a vision on a whiteboard in Astana. This month, we officially completed our transition to focusing exclusively on B2B AI automation training. This wasn't a "seamless pivot" or a lucky break; it was the result of six months of failed pilots, rejected proposals, and a complete overhaul of our sales methodology to meet the needs of a changing market.

I had to personally unlearn a decade of hardware-focused sales tactics to understand how to sell a "Mindset Shift" to traditional business leaders. The win belongs to the team that stayed in the office until 10 PM, not just coding, but debating the ethics and operational impact of automation with our early clients. We didn't just hit a revenue milestone; we proved that Kazakhstani businesses are ready for high-level technical transformation.

While the title "Head of B2B Sales" is a new chapter for me, the mission remains the same. We are here to remove the manual drudgery that holds back our country's top talent. We aren't celebrating yet because the market is vast and we are still very much on Day One. It is time to get back to the work.

### INPUT DATA
**User Transcript:**
{{TRANSCRIPT}}
""",

    "The Behind-the-Scenes Post": """
### ROLE
You are a Documentary Ghostwriter. You show the "Messy Middle" of business to build authenticity and relatability.

### OBJECTIVE
Take a transcript about a process or a mistake and turn it into a post about reality. Highlight the imperfections and the grit.

### THE "BEHIND-THE-SCENES" FRAMEWORK
1. **THE REALITY CHECK:** Start by contrasting a polished image with a messy reality.
2. **THE PROCESS:** 2-3 paragraphs describing the actual, unglamorous work.
3. **THE INSIGHT:** Why this specific struggle matters for the final product or the company culture.
4. **THE INVITATION:** Ask the audience about their own "unseen" work.

### CRITICAL CONSTRAINTS
1. **NO FILTER:** Keep the mentions of mistakes or chaotic moments. 
2. **VIVID IMAGERY:** Use descriptive prose to "show" the scene (the late night office, the messy spreadsheets, the long Slack threads).

### EXAMPLES
** ✅  GOOD EXAMPLE**
The marketing materials for our new B2B curriculum look polished and effortless, but the reality behind them is far less glamorous. Last night, our lead trainers and I were in a heated debate until 2 AM over a single module in our AI automation course. We realized that our initial "B2C-style" prompts were far too creative for a corporate environment where a mid-level manager's primary goal is to produce a report that won't get them fired by their CFO.

We ended up throwing out nearly 30% of our existing content because it didn't pass the "Business Logic" test. Innovation is rarely about a sudden spark of genius; it’s usually 10% inspiration and 90% tedious, late-night auditing of every single line of code and every training slide. We aren't interested in delivering "magic buttons"; we are building reliable tools that work in the high-stakes environment of Kazakhstani industry.

If you think AI implementation is a "set it and forget it" process, you haven't seen the sheer amount of manual work it takes to make these systems dependable. Success is almost always more boring and more exhausting than the final LinkedIn post makes it look. What is the "messy middle" of the project you are currently working on?

### INPUT DATA
**User Transcript:**
{{TRANSCRIPT}}
""",

    "The Contrarian / Hot Take Post": """
### ROLE
You are a Professional Debater. You take unpopular opinions and turn them into logical, persuasive disruptions of the status quo.

### OBJECTIVE
Refine a "Hot Take" into an insightful argument. Attack the prevailing logic with evidence and a superior alternative.

### THE "CONTRARIAN" FRAMEWORK
1. **THE ATTACK:** State clearly that a common industry belief is fundamentally wrong.
2. **THE LOGIC:** 2-3 dense paragraphs explaining why the current belief is inefficient or outdated.
3. **THE NEW TRUTH:** Offer the alternative perspective or solution.
4. **THE CHALLENGE:** Dare the reader to defend the old way of thinking.

### CRITICAL CONSTRAINTS
1. **NO HEDGING:** Be absolute in your stance. Do not use "maybe" or "in some cases."
2. **LOGICAL DEPTH:** Use your experience in B2B sales and automation to provide a "why" that others can't ignore.

### EXAMPLES
** ✅  GOOD EXAMPLE**
Stop hiring "AI Specialists" for your corporate teams. It is the fastest way to waste a department budget in 2026. When you hire a dedicated specialist, you inadvertently create a knowledge silo where the rest of your staff stops learning because they believe "AI is just that guy's job." This is the exact same strategic error companies made with "Digital Transformation" a decade ago.

The goal for a modern B2B organization isn't to have an isolated AI department; it is to have an AI-literate workforce across every function. I have seen companies pay $50k to consultants for "AI reports" that a well-trained junior staffer could have generated in ten minutes if they had been given the right tools and training. The real competitive advantage isn't the expert you bring in from the outside; it’s the internal training of your existing sales and ops teams who actually understand how your business makes money.

Your subject matter experts are your most valuable asset. They just need the technical leverage to execute their existing knowledge ten times faster. Fire the "specialist" who doesn't understand your industry and invest that capital into training the people who are already in the trenches. I’m ready for the pushback on this one, so let’s hear it in the comments.

### INPUT DATA
**User Transcript:**
{{TRANSCRIPT}}
"""
}

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
        
def classify_transcript(raw_text):
    """Step 2: The Strategist (Gemini)"""
    # CRITICAL FIX: Removed F-String for raw_text to prevent crashes on curly braces
    base_prompt = """
### ROLE
You are an expert LinkedIn Content Strategist. Your sole purpose is to analyze raw, unstructured audio transcripts and categorize them into the single best viral framework.

### TASK
Read the user's raw input and map it to ONE of the following 7 frameworks. Do not rewrite the text. Return only the classification.

### THE 7 FRAMEWORK DEFINITIONS
1. **The Personal Story Post**
2. **The List Post (Listicle)**
3. **The Question Post**
4. **The Industry Insight Post**
5. **The Achievement / Milestone Post**
6. **The Behind-the-Scenes Post**
7. **The Contrarian / Hot Take Post**

### DECISION LOGIC
- If the content fits multiple categories, prioritize the one that matches the **dominant emotion**.

### RAW TRANSCRIPT FROM USER
"{{TRANSCRIPT}}"

### OUTPUT FORMAT (JSON ONLY)
{
  "framework": "The Personal Story Post"
}
    """
    
    # Use replace instead of f-string
    prompt = base_prompt.replace("{{TRANSCRIPT}}", raw_text)
    
    try:
        response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        return json.loads(response.text)
    except:
        return {"framework": "The Personal Story Post"}

def generate_post(raw_text, framework):
    """Step 3: The Ghostwriter (Gemini)"""
    
    base_prompt = FRAMEWORK_PROMPTS.get(framework, FRAMEWORK_PROMPTS["The Personal Story Post"])
    final_prompt = base_prompt.replace("{{TRANSCRIPT}}", raw_text)
    
    final_prompt += """
    
    ### FINAL OUTPUT FORMAT (JSON ONLY)
    {
        "title": "A short, internal title for this post (e.g. 'My Failure Story')",
        "text": "The full LinkedIn post text here..."
    }
    """
    
    try:
        response = model.generate_content(final_prompt, generation_config={"response_mime_type": "application/json"})
        return json.loads(response.text)
    except Exception as e:
        return {"title": "Error", "text": f"Writing Error: {str(e)}"}

def process_voice_note(file_path, research_context=None):
    """
    The Master Pipeline
    """
    # 1. Transcribe (Common Step)
    raw_text = transcribe_audio_groq(file_path)
    if "Error" in raw_text: 
        return {"title": "Error", "text": raw_text}
    
    # 2. LOGIC BRANCH: Generator Mode vs. Story Mode
    
    # PATH A: GENERATOR MODE (Research + Reaction)
    if research_context:
        print("🔀 Route: Delegating to Viral Editor...")
        # We pass the transcription + the research to the specialist
        return generate_viral_post(research_context, raw_text)

    # PATH B: STORY MODE (Raw Voice Only)
    else:
        print("🔀 Route: Standard Story Mode...")
        strategy = classify_transcript(raw_text)
        chosen_framework = strategy.get("framework", "The Personal Story Post")
        
        final_post = generate_post(raw_text, chosen_framework)
        final_post["title"] = f"[{chosen_framework}] {final_post.get('title', 'Draft')}"
        return final_post