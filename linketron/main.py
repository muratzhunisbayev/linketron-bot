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
from services.voice_processor import process_voice_note, process_text_note

# 1. LOAD ENV
load_dotenv()

# 2. IMPORTS
from services.researcher import search_perplexity, format_card_text 
from services.voice_processor import process_voice_note
from services.image_finder import get_image_from_web
from services.image_generator import generate_ai_image
from services.linkedin_publisher import publish_to_linkedin 
from config import LENS_MAPPING

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DATA_FILE = "user_secrets.json"

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
# FIX: Removed the specific state filter so it catches ALL voice notes
@dp.message(F.voice) 
async def process_voice_message(message: types.Message, state: FSMContext):
    
    # 1. DIAGNOSE THE STATE
    current_state = await state.get_state()
    print(f"🎤 Voice Received. Current State: {current_state}") # Debug print

    # 2. HANDLE "LOST" USERS (Restart Amnesia)
    valid_states = [BotState.waiting_for_voice, BotState.waiting_for_reaction]
    
    if current_state not in valid_states:
        await message.reply(
            "⚠️ **I received your voice, but I wasn't ready.**\n\n"
            "This happens if the bot was restarted.\n"
            "👇 **Please click a mode to start:**",
            reply_markup=get_root_menu()
        )
        return

    # 3. IF VALID, PROCEED NORMALLY
    status_msg = await message.reply("✅ **Voice received.** Transcribing...", parse_mode="Markdown")
    
    # 4. Download Audio
    file_id = message.voice.file_id
    file = await bot.get_file(file_id)
    file_path = f"voice_{file_id}.ogg"
    await bot.download_file(file.file_path, file_path)
    
# 5. Check Context & Language (FIXED)
    state_data = await state.get_data()
    language = state_data.get("language", "English") # Retrieve the choice from state
    research_context = None

    if current_state == BotState.waiting_for_reaction:
        research_context = state_data.get("research_context")
    
    # 6. Run Processing (FIXED: Added 'language' argument)
    loop = asyncio.get_event_loop()
    try:
        # Pass language here so the logic knows what prompt to use
        post_data = await loop.run_in_executor(None, process_voice_note, file_path, language, research_context)
    except Exception as e:
        await status_msg.edit_text(f"❌ **System Error:** {str(e)}")
        if os.path.exists(file_path): os.remove(file_path)
        return
    
    # 7. Cleanup & Success
    if os.path.exists(file_path): os.remove(file_path)

    if post_data.get("title") == "Error":
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

    # FIX: Removed parse_mode="Markdown" to prevent crashes from AI symbols (like _ or *)
    await message.answer(
        f"✅ **Draft Created.**\n"
        f"Strategy Used: {post_data.get('title')}\n\n"
        f"{post_data.get('text')}\n\n"
        "👇 **How should we illustrate this?**",
        reply_markup=keyboard
        # parse_mode="Markdown"  <-- DELETED THIS LINE
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
    research_context = None

    if current_state == BotState.waiting_for_reaction:
        research_context = state_data.get("research_context")
    
    loop = asyncio.get_event_loop()
    try:
        post_data = await loop.run_in_executor(None, process_text_note, message.text, language, research_context)
    except Exception as e:
        await status_msg.edit_text(f"❌ **System Error:** {str(e)}")
        return
    
    if post_data.get("title") == "Error":
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
        f"🚀 **{draft_post['title']}**\n\n"
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
        f"🚀 **{draft_post['title']}**\n\n"
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
        f"🚀 **{draft_post['title']}**\n\n"
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
    await callback.message.edit_text(
        "📤 **Upload Mode Active**\n\n"
        "👇 **Drop your photo here.**\n"
        "_(Send it as a Photo, not a File)_"
    )

@dp.message(BotState.waiting_for_user_upload, F.photo)
async def process_user_photo(message: types.Message, state: FSMContext):
    data = await state.get_data()
    draft_post = data.get("final_post")
    
    photo = message.photo[-1]
    file_info = await bot.get_file(photo.file_id)
    local_path = "temp_generated_image.png"
    await bot.download_file(file_info.file_path, local_path)
    
    full_text_message = (
        f"🚀 **{draft_post['title']}**\n\n"
        f"{draft_post['text']}\n\n"
        "-----------------------------\n"
        "📷 *Image Source:* User Upload"
    )
    
    await message.answer_photo(photo=photo.file_id)
    await message.answer(text=full_text_message, parse_mode="Markdown", reply_markup=get_publish_menu())

@dp.callback_query(F.data == "action_publish")
async def process_publish(callback: types.CallbackQuery, state: FSMContext):
    """Достает токены пользователя и отправляет пост в LinkedIn."""
    
    # 1. Получаем ID пользователя Telegram
    user_id = callback.from_user.id
    
    # 2. Достаем его личные учетные данные из нашего "сейфа"
    creds = get_user_credentials(user_id)
    
    if not creds:
        await callback.message.answer("❌ Ошибка: Ваши данные не найдены. Пожалуйста, авторизуйтесь снова через /start.")
        return

    status_msg = await callback.message.answer("⏳ **Публикация в LinkedIn...**")
    
    # 3. Собираем данные поста из состояния бота
    data = await state.get_data()
    draft_post = data.get("final_post")
    
    # Проверяем наличие сгенерированного изображения
    image_path = "temp_generated_image.png" if os.path.exists("temp_generated_image.png") else None
    
    try:
        # 4. Запускаем публикацию, передавая токен и URN именно этого пользователя
        loop = asyncio.get_event_loop()
        result_text = await loop.run_in_executor(
            None, 
            publish_to_linkedin, 
            draft_post['text'], 
            image_path,
            creds['access_token'], # Токен пользователя
            creds['user_urn']     # URN пользователя
        )
        
        await status_msg.edit_text(result_text)
        
        # Очистка временных файлов после публикации
        if image_path and os.path.exists(image_path):
            os.remove(image_path)
            
    except Exception as e:
        await status_msg.edit_text(f"⚠️ Ошибка при публикации: {str(e)}")
        

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