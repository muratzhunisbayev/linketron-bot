import asyncio
import logging
import os
import json
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from dotenv import load_dotenv
import requests
import urllib.parse
import requests
from get_token import CLIENT_ID, CLIENT_SECRET, REDIRECT_URI


# 1. LOAD ENV
load_dotenv()

# 2. IMPORTS
# 2. IMPORTS
from services.researcher import search_perplexity, format_card_text 
from services.voice_processor import transcribe_audio_groq
from services.editor_story import generate_essay_draft
from services.editor_research import generate_viral_post
from services.cleaner import clean_ai_slop
from services.image_finder import get_image_from_web
from services.image_generator import generate_ai_image
from services.linkedin_publisher import publish_to_linkedin 
from config import LENS_MAPPING

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DATA_FILE = "user_secrets.json"
upload_locks = {}

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- STATE MACHINE ---
class BotState(StatesGroup):
    waiting_for_auth_code = State()
    waiting_for_voice = State()        # Standard Story Mode
    waiting_for_reaction = State()     # Waiting for reaction to Research
    waiting_for_custom_topic = State()
    waiting_for_visual_choice = State()
    waiting_for_user_upload = State() 

# --- 1. THE VAULT ---
def load_all_secrets():
    if not os.path.exists(DATA_FILE): return {}
    try:
        with open(DATA_FILE, "r") as f: return json.load(f)
    except: return {}

def save_user_credentials(user_id, token, urn): # Renamed for clarity
    data = load_all_secrets()
    data[str(user_id)] = {
        "access_token": token,
        "user_urn": urn
    }
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_user_credentials(user_id): # Renamed for clarity
    return load_all_secrets().get(str(user_id))

def delete_user_secret(user_id):
    data = load_all_secrets()
    if str(user_id) in data:
        del data[str(user_id)]
        with open(DATA_FILE, "w") as f: json.dump(data, f, indent=2)

# --- 2. MENUS ---

def get_root_menu():
    """The New Lobby: Choose your path"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎙️ I have a Story (Voice or Text)", callback_data="mode_story")],
        [InlineKeyboardButton(text="🧠 I need Ideas (Generator)", callback_data="mode_generator")],
        [InlineKeyboardButton(text="❌ Disconnect", callback_data="logout")]
    ])

def get_lens_menu():
    """The Main Menu (Research Buttons)"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧠 Principle", callback_data="lens_principle"), 
         InlineKeyboardButton(text="📈 Case Study", callback_data="lens_case_study")],
        [InlineKeyboardButton(text="🚀 Growth Hack", callback_data="lens_growth"), 
         InlineKeyboardButton(text="🔥 Controversial", callback_data="lens_controversial")],
        [InlineKeyboardButton(text="💡 Suggest Idea (Custom)", callback_data="lens_custom")],
        [InlineKeyboardButton(text="🔙 Back", callback_data="back_to_root")]
    ])

def get_login_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        # [InlineKeyboardButton(text="🚀 Auto-Connect", callback_data="auto_connect")] <--- DELETE or COMMENT OUT
        [InlineKeyboardButton(text="🔒 Login via Admin Console", callback_data="start_login")] # Placeholder
    ])

def get_publish_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Publish to LinkedIn", callback_data="action_publish")],
        [InlineKeyboardButton(text="❌ Done (Cancel)", callback_data="action_cancel")]
    ])

def get_language_menu(mode):
    """Simple toggle for English/Russian before starting the session."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇬🇧 English", callback_data=f"lang_en_{mode}"),
         InlineKeyboardButton(text="🇷🇺 Russian", callback_data=f"lang_ru_{mode}")]
    ])

# --- 3. HANDLERS ---

@dp.message(Command("start"))
async def start_command(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    
    # CHANGE THIS LINE:
    creds = get_user_credentials(user_id) 
    
    # Update the logic to check for the new credentials dictionary
    if creds and creds.get("access_token"): 
        await message.answer(
            "✅ **System Online.** Welcome back!\n\n"
            "👇 **How do you want to create today?**\n\n"
            "🎙️ **Story Mode:** You talk, I write.\n"
            "🧠 **Generator Mode:** I research, you react.",
            reply_markup=get_root_menu(), 
            parse_mode="Markdown"
        )
    else:
        await message.answer(
            f"👋 **Welcome.**\nI need to connect to your LinkedIn to start.",
            reply_markup=get_login_menu(), parse_mode="Markdown"
        )

# --- A. NAVIGATION HANDLERS ---

@dp.callback_query(F.data == "mode_generator")
async def enter_generator_mode(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(
        "🧠 **Generator Mode Active**\n\n👇 **Choose a Lens to research:**",
        reply_markup=get_lens_menu()
    )

@dp.callback_query(F.data == "mode_story")
async def enter_story_mode(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    # Instead of going straight to voice, ask for language first
    await callback.message.edit_text("🌐 **Choose output language:**", reply_markup=get_language_menu("story"))

@dp.callback_query(F.data.startswith("lang_"))
async def start_capture(callback: types.CallbackQuery, state: FSMContext):
    # Extract language and mode from the callback (e.g., lang_en_story)
    _, lang_code, mode = callback.data.split("_")
    language = "English" if lang_code == "en" else "Russian"
    await state.update_data(language=language)
    
    await state.set_state(BotState.waiting_for_voice)
    await callback.message.edit_text(f"🎙️ **{language} Story Mode Active**\nSend your voice or text note.")

@dp.callback_query(F.data == "back_to_root")
async def back_to_root(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(
        "👇 **How do you want to create today?**",
        reply_markup=get_root_menu()
    )

# --- NEW LOGIN & OAUTH HANDLERS ---

@dp.callback_query(F.data == "start_login")
async def handle_login_request(callback: types.CallbackQuery, state: FSMContext):
    """Generates the LinkedIn Auth URL and sends it to the user."""
    auth_url = "https://www.linkedin.com/oauth/v2/authorization"
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": "openid profile w_member_social email",
    }
    url = f"{auth_url}?{urllib.parse.urlencode(params)}"
    
    await callback.message.edit_text(
        "🔐 **LinkedIn Connection**\n\n"
        "1. [Click here to Authorize](" + url + ")\n"
        "2. Login and click 'Allow'.\n"
        "3. You'll be sent to a Google page. **Copy the code** from the URL bar.\n\n"
        "👇 **Paste that code here:**",
        parse_mode="Markdown",
        disable_web_page_preview=True
    )
    await state.set_state(BotState.waiting_for_auth_code)

@dp.message(BotState.waiting_for_auth_code)
async def process_auth_code(message: types.Message, state: FSMContext):
    """Exchanges the code for a real token and saves it to the vault."""
    raw_input = message.text.strip()
    
    # 1. ROBUST EXTRACTION: Automatically find the code in a full URL or raw string
    if "code=" in raw_input:
        try:
            # Extracts everything between 'code=' and the next '&'
            auth_code = raw_input.split("code=")[1].split("&")[0]
        except IndexError:
            auth_code = raw_input 
    else:
        # Just in case there's browser junk like &zx=... at the end of a raw code
        auth_code = raw_input.split("&")[0]

    status_msg = await message.answer(f"⏳ Verifying code with LinkedIn...")
    
    token_url = "https://www.linkedin.com/oauth/v2/accessToken"
    data = {
        "grant_type": "authorization_code",
        "code": auth_code,
        "redirect_uri": REDIRECT_URI, # Imported from get_token.py
        "client_id": CLIENT_ID,     # Imported from get_token.py
        "client_secret": CLIENT_SECRET, # Imported from get_token.py
    }
    
    try:
        # 2. EXCHANGE CODE FOR TOKEN
        response = requests.post(token_url, data=data)
        if response.status_code == 200:
            token = response.json().get("access_token")
            
            # 3. FETCH USER URN (Required for posting)
            headers = {"Authorization": f"Bearer {token}"}
            user_response = requests.get("https://api.linkedin.com/v2/userinfo", headers=headers)
            
            if user_response.status_code == 200:
                user_info = user_response.json()
                urn = user_info.get("sub")
                
                # 4. SAVE TO VAULT (User-specific storage)
                save_user_credentials(message.from_user.id, token, urn)
                
                await status_msg.edit_text(
                    "✅ **LinkedIn Connected!**\nYour account is now linked to this bot.", 
                    reply_markup=get_root_menu()
                )
                await state.clear()
            else:
                await status_msg.edit_text("❌ Could not retrieve your User ID from LinkedIn.")
        else:
            await status_msg.edit_text(f"❌ **LinkedIn Error:** {response.text}")
            
    except Exception as e:
        await status_msg.edit_text(f"⚠️ **System Error:** {str(e)}")

# --- B. LENS CLICK HANDLER ---
@dp.callback_query(F.data.startswith("lens_"))
async def process_lens_click(callback: types.CallbackQuery, state: FSMContext):
    lens_key = callback.data 
    
    # 1. Handle Custom Topic Input
    if lens_key == "lens_custom":
        await callback.answer()
        await state.set_state(BotState.waiting_for_custom_topic)
        await callback.message.answer("💡 **Custom Idea Mode**\n👇 **Type your topic below:**")
        return

    # 2. Handle Standard Lenses
    await callback.answer()
    await run_briefing_sequence(callback.message, state, lens_key, custom_topic=None)

# --- C. CUSTOM TOPIC HANDLER ---
@dp.message(BotState.waiting_for_custom_topic)
async def process_custom_topic(message: types.Message, state: FSMContext):
    user_topic = message.text
    await run_briefing_sequence(message, state, "lens_custom", custom_topic=user_topic)

# --- D. BRIEFING SEQUENCE ---
async def run_briefing_sequence(message_obj, state, lens_key, custom_topic=None):
    """
    1. Searches Perplexity.
    2. Formats a Briefing Card.
    3. Waits for User Voice Reaction.
    """
    status_msg = await message_obj.answer(
        f"🕵️ **Investigating...**\n"
        f"Searching for a unique angle on this...",
        parse_mode="Markdown"
    )

    loop = asyncio.get_event_loop()
    
    # 1. Research (The Infinite Investigator)
    try:
        research_data = await loop.run_in_executor(None, search_perplexity, lens_key, custom_topic)
    except Exception as e:
        await status_msg.edit_text(f"❌ **Search Error:** {str(e)}")
        return
    
    # 2. Format the Card (The Briefing)
    card_text = format_card_text(research_data)

    if "Search Failed" in card_text:
        await status_msg.edit_text(card_text)
        return

    # 3. Save Data & Wait
    await state.update_data(research_context=research_data)
    await state.set_state(BotState.waiting_for_reaction) # <--- Bot waits here

    # 4. Display Card
    await status_msg.delete()
    await message_obj.answer(
        card_text,
        parse_mode="Markdown"
    )

# --- E. VOICE HANDLER (ROBUST VERSION) ---
# --- E. VOICE HANDLER (ORCHESTRATED) ---
@dp.message(F.voice) 
async def process_voice_message(message: types.Message, state: FSMContext):
    current_state = await state.get_state()

    valid_states = [BotState.waiting_for_voice, BotState.waiting_for_reaction]
    if current_state not in valid_states:
        await message.reply(
            "⚠️ **I received your voice, but I wasn't ready.**\n\n"
            "This happens if the bot was restarted.\n"
            "👇 **Please click a mode to start:**",
            reply_markup=get_root_menu()
        )
        return

    status_msg = await message.reply("✅ **Voice received.** Processing...", parse_mode="Markdown")
    
    # 1. Download Audio
    file_id = message.voice.file_id
    file = await bot.get_file(file_id)
    file_path = f"voice_{file_id}.ogg"
    await bot.download_file(file.file_path, file_path)
    
    # 2. Check Context
    state_data = await state.get_data()
    language = state_data.get("language", "English")
    research_context = state_data.get("research_context") if current_state == BotState.waiting_for_reaction else None
    
    # 3. Execution Pipeline
    loop = asyncio.get_event_loop()
    try:
        await status_msg.edit_text("⏳ **Transcribing audio...**")
        raw_text = await loop.run_in_executor(None, transcribe_audio_groq, file_path)
        
        if raw_text.startswith("Error") or raw_text.startswith("Groq Error"):
            raise Exception(raw_text)

        await status_msg.edit_text("⏳ **Drafting post...**")
        if research_context:
            initial_draft = await loop.run_in_executor(None, generate_viral_post, research_context, raw_text, language)
        else:
            initial_draft = await loop.run_in_executor(None, generate_essay_draft, raw_text, language)

        draft_text = initial_draft.get('text') or initial_draft.get('post', '')
        draft_title = initial_draft.get('title') or "Draft"

        # ==========================================
        # 1. PRINT THE EDITOR'S RAW DRAFT TO TERMINAL
        # ==========================================
        print("\n" + "="*40)
        print(f"📝 VOICE EDITOR OUTPUT:")
        print(f"Title: {draft_title}")
        print(f"Text:\n{draft_text}")
        print("="*40 + "\n")

        # await status_msg.edit_text("⏳ **Refining output...**")
        # final_post = await loop.run_in_executor(None, clean_ai_slop, draft_text, language)
        
        # # ==========================================
        # # 2. PRINT THE CLEANER'S RESULT TO TERMINAL
        # # ==========================================
        # print("\n" + "="*40)
        # print(f"🧹 VOICE CLEANER OUTPUT:")
        # print(f"Title: {final_post.get('title')}")
        # print(f"Text:\n{final_post.get('text')}")
        # print("="*40 + "\n")

        # post_data = {
        #     "title": final_post.get("title") or draft_title,
        #     "text": final_post.get("text") or draft_text
        # }

        # --- CLEANER SKIPPED ---
        # await status_msg.edit_text("⏳ **Refining output...**")
        # final_post = await loop.run_in_executor(None, clean_ai_slop, draft_text, language)
        # 
        # print("\n" + "="*40)
        # print(f"🧹 VOICE CLEANER OUTPUT:")
        # print(f"Title: {final_post.get('title')}")
        # print(f"Text:\n{final_post.get('text')}")
        # print("="*40 + "\n")

        # Bypass final_post and use the raw draft directly
        post_data = {
            "title": draft_title,
            "text": draft_text
        }

    except Exception as e:
        await status_msg.edit_text(f"❌ **System Error:** {str(e)}")
        if os.path.exists(file_path): os.remove(file_path)
        return
    
    if os.path.exists(file_path): os.remove(file_path)

    if post_data.get("title") == "Error Generating Post" or post_data.get("title") == "Drafting Error":
        await status_msg.edit_text(f"❌ **Writer Error:** {post_data.get('text')}")
        return

    await state.update_data(final_post=post_data)
    await state.set_state(BotState.waiting_for_visual_choice)
    await status_msg.delete()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌍 Auto-Web Photo", callback_data="visual_web")],
        [InlineKeyboardButton(text="🎨 Generate AI (Imagen)", callback_data="visual_ai")],
        [InlineKeyboardButton(text="📤 Upload Own", callback_data="visual_upload")], 
        [InlineKeyboardButton(text="⏩ Skip (Text Only)", callback_data="visual_skip")]
    ])

    await message.answer(
        f"✅ **Draft Created.**\n"
        f"Strategy Used: {post_data.get('title')}\n\n"
        f"{post_data.get('text')}\n\n"
        "👇 **How should we illustrate this?**",
        reply_markup=keyboard
    )

@dp.message(F.text)
async def process_text_draft_message(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    
    valid_states = [BotState.waiting_for_voice, BotState.waiting_for_reaction]
    if current_state not in valid_states:
        return

    status_msg = await message.reply("✅ **Text draft received.** Processing...", parse_mode="Markdown")
    
    state_data = await state.get_data()
    language = state_data.get("language", "English")
    research_context = state_data.get("research_context") if current_state == BotState.waiting_for_reaction else None
    
    loop = asyncio.get_event_loop()
    try:
        raw_text = message.text

        await status_msg.edit_text("⏳ **Drafting post...**")
        if research_context:
            initial_draft = await loop.run_in_executor(None, generate_viral_post, research_context, raw_text, language)
        else:
            initial_draft = await loop.run_in_executor(None, generate_essay_draft, raw_text, language)

        draft_text = initial_draft.get('text') or initial_draft.get('post', '')
        draft_title = initial_draft.get('title') or "Draft"

        # ==========================================
        # 1. PRINT THE EDITOR'S RAW DRAFT TO TERMINAL
        # ==========================================
        print("\n" + "="*40)
        print(f"📝 TEXT EDITOR OUTPUT:")
        print(f"Title: {draft_title}")
        print(f"Text:\n{draft_text}")
        print("="*40 + "\n")

        # await status_msg.edit_text("⏳ **Refining output...**")
        # final_post = await loop.run_in_executor(None, clean_ai_slop, draft_text, language)
        
        # # ==========================================
        # # 2. PRINT THE CLEANER'S RESULT TO TERMINAL
        # # ==========================================
        # print("\n" + "="*40)
        # print(f"🧹 TEXT CLEANER OUTPUT:")
        # print(f"Title: {final_post.get('title')}")
        # print(f"Text:\n{final_post.get('text')}")
        # print("="*40 + "\n")

        # post_data = {
        #     "title": final_post.get("title") or draft_title,
        #     "text": final_post.get("text") or draft_text
        # }

        # --- CLEANER SKIPPED ---
        # await status_msg.edit_text("⏳ **Refining output...**")
        # final_post = await loop.run_in_executor(None, clean_ai_slop, draft_text, language)
        # 
        # print("\n" + "="*40)
        # print(f"🧹 TEXT CLEANER OUTPUT:")
        # print(f"Title: {final_post.get('title')}")
        # print(f"Text:\n{final_post.get('text')}")
        # print("="*40 + "\n")

        # Bypass final_post and use the raw draft directly
        post_data = {
            "title": draft_title,
            "text": draft_text
        }

    except Exception as e:
        await status_msg.edit_text(f"❌ **System Error:** {str(e)}")
        return
    
    if post_data.get("title") == "Error Generating Post" or post_data.get("title") == "Drafting Error":
        await status_msg.edit_text(f"❌ **Writer Error:** {post_data.get('text')}")
        return

    await state.update_data(final_post=post_data)
    await state.set_state(BotState.waiting_for_visual_choice)
    await status_msg.delete()
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌍 Auto-Web Photo", callback_data="visual_web")],
        [InlineKeyboardButton(text="🎨 Generate AI (Imagen)", callback_data="visual_ai")],
        [InlineKeyboardButton(text="📤 Upload Own", callback_data="visual_upload")], 
        [InlineKeyboardButton(text="⏩ Skip (Text Only)", callback_data="visual_skip")]
    ])

    await message.answer(
        f"✅ **Draft Created.**\n"
        f"Strategy Used: {post_data.get('title')}\n\n"
        f"{post_data.get('text')}\n\n"
        "👇 **How should we illustrate this?**",
        reply_markup=keyboard
    )

# --- F. VISUAL HANDLERS ---
@dp.callback_query(BotState.waiting_for_visual_choice, F.data == "visual_web")
async def process_visual_web(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    status_msg = await callback.message.edit_text("🌍 **Searching & Downloading...**")
    
    data = await state.get_data()
    draft_post = data.get("final_post")
    
    loop = asyncio.get_event_loop()
    image_url, query_used = await loop.run_in_executor(None, get_image_from_web, draft_post['text'])
    
    full_text_message = (
        f"{draft_post['text']}\n\n"
        "-----------------------------\n"
        f"📷 *Image Source:* {query_used}"
    )

    if not image_url:
        await callback.message.answer(
            f"⚠️ **No Image Found.** Sending text only.\n\n{full_text_message}",
            reply_markup=get_publish_menu()
        )
        await status_msg.delete()
        return

    try:
        img_response = await loop.run_in_executor(None, requests.get, image_url)
        img_response.raise_for_status()
        
        local_path = "temp_generated_image.png"
        with open(local_path, "wb") as f:
            f.write(img_response.content)

        image_file = FSInputFile(local_path)
        await callback.message.answer_photo(photo=image_file)
        await callback.message.answer(text=full_text_message, parse_mode="Markdown", reply_markup=get_publish_menu())
        
    except Exception as e:
        await callback.message.answer(
            f"⚠️ **Image Error.** Text below:\n\n{full_text_message}",
            reply_markup=get_publish_menu()
        )

    await status_msg.delete()

@dp.callback_query(BotState.waiting_for_visual_choice, F.data == "visual_ai")
async def process_visual_ai(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    status_msg = await callback.message.edit_text("🎨 **Director is thinking...**")
    
    user_id = callback.from_user.id  # <--- 1. Get User ID
    data = await state.get_data()
    draft_post = data.get("final_post")
    
    loop = asyncio.get_event_loop()
    
    # <--- 2. Pass user_id to the generator
    image_path, subject_used = await loop.run_in_executor(
        None, generate_ai_image, draft_post['text'], user_id
    )
    
    full_text_message = (
        f"{draft_post['text']}\n\n"
        "-----------------------------\n"
        f"🎨 *AI Concept:* {subject_used}"
    )

    if image_path and os.path.exists(image_path):
        photo_file = FSInputFile(image_path)
        await callback.message.answer_photo(photo=photo_file)
        await callback.message.answer(text=full_text_message, parse_mode="Markdown", reply_markup=get_publish_menu())
    else:
        await callback.message.answer(
            f"⚠️ **Generation Failed:** {subject_used}\n\n{full_text_message}",
            reply_markup=get_publish_menu()
        )
    await status_msg.delete()

@dp.callback_query(BotState.waiting_for_visual_choice, F.data == "visual_skip")
async def process_visual_skip(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    draft_post = data.get("final_post")
    
    await callback.message.edit_text(
        f"{draft_post['text']}\n\n"
        "-----------------------------\n"
        "👇 *Ready to Post.*",
        reply_markup=get_publish_menu()
    )

# --- G. UPLOAD & PUBLISH HANDLERS ---
@dp.callback_query(BotState.waiting_for_visual_choice, F.data == "visual_upload")
async def process_visual_upload_click(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(BotState.waiting_for_user_upload)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Done Uploading", callback_data="finish_uploading")]
    ])
    
    msg = await callback.message.edit_text(
        "📤 **Upload Mode Active**\n\n"
        "👇 **Send your photos now.**\n"
        "You can send one or multiple. When finished, click the button below.",
        reply_markup=keyboard
    )
    
    # Save the empty queue AND the ID of this message
    msg_id = msg.message_id if isinstance(msg, types.Message) else callback.message.message_id
    await state.update_data(uploaded_photos=[], status_msg_id=msg_id)

@dp.message(BotState.waiting_for_user_upload, F.photo)
async def process_user_photo(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    
    # 1. Create a traffic lock for this specific user
    if user_id not in upload_locks:
        upload_locks[user_id] = asyncio.Lock()
        
    # 2. Force simultaneous photos to wait in line
    async with upload_locks[user_id]:
        data = await state.get_data()
        photo_queue = data.get("uploaded_photos", [])
        status_msg_id = data.get("status_msg_id")
        
        photo = message.photo[-1]
        file_info = await bot.get_file(photo.file_id)
        
        # Use file_id for a truly unique filename
        local_path = f"temp_upload_{photo.file_id}.png"
        await bot.download_file(file_info.file_path, local_path)
        
        photo_queue.append(local_path)
        
        # Delete the old button
        if status_msg_id:
            try:
                await bot.delete_message(chat_id=message.chat.id, message_id=status_msg_id)
            except Exception:
                pass
                
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Done Uploading", callback_data="finish_uploading")]
        ])
        
        # Send the new button
        new_msg = await message.answer(
            f"📸 Received. Total in queue: **{len(photo_queue)}**\n"
            f"Send more, or click Done.",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        
        # Save the updated queue and new message ID
        await state.update_data(uploaded_photos=photo_queue, status_msg_id=new_msg.message_id)

@dp.callback_query(BotState.waiting_for_user_upload, F.data == "finish_uploading")
async def process_done_uploading(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    draft_post = data.get("final_post")
    photo_queue = data.get("uploaded_photos", [])
    
    if not photo_queue:
        await callback.message.answer("⚠️ You haven't uploaded any photos yet. Send a photo or click 'Cancel'.")
        return
        
    full_text_message = (
        f"🚀 **{draft_post['title']}**\n\n"
        f"{draft_post['text']}\n\n"
        "-----------------------------\n"
        f"📷 *Image Source:* User Upload ({len(photo_queue)} photos queued)"
    )
    
    await callback.message.edit_text(
        text=full_text_message, 
        parse_mode="Markdown", 
        reply_markup=get_publish_menu()
    )

@dp.callback_query(F.data == "action_publish")
async def process_publish(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    creds = get_user_credentials(user_id)
    
    if not creds:
        await callback.message.answer("❌ Error: Credentials not found. Please /start and login again.")
        return

    status_msg = await callback.message.answer("⏳ **Publishing to LinkedIn...**")
    
    data = await state.get_data()
    draft_post = data.get("final_post")
    photo_queue = data.get("uploaded_photos", [])
    
    # Determine the payload: Queue first, fallback to AI/Web temp image
    image_paths = []
    if photo_queue:
        image_paths = photo_queue
    elif os.path.exists("temp_generated_image.png"):
        image_paths = ["temp_generated_image.png"]
    
    try:
        loop = asyncio.get_event_loop()
        result_text = await loop.run_in_executor(
            None, 
            publish_to_linkedin, 
            draft_post['text'], 
            image_paths,
            creds['access_token'],
            creds['user_urn']
        )
        
        await status_msg.edit_text(result_text)
        
        # Cleanup temporary files
        for path in image_paths:
            if os.path.exists(path):
                os.remove(path)
                
    except Exception as e:
        await status_msg.edit_text(f"⚠️ Publish Error: {str(e)}")


@dp.callback_query(F.data == "action_cancel")
async def process_cancel(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("✅ **Action Cancelled.**")
    await state.clear()

@dp.callback_query(F.data == "logout")
async def logout(callback: types.CallbackQuery):
    delete_user_secret(callback.from_user.id)
    await callback.message.edit_text("🔌 **Disconnected.**", reply_markup=get_login_menu())

async def main():
    print("🤖 Linketron Full-Stack is running...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())