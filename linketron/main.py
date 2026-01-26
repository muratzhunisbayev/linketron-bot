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

# 1. LOAD ENV
load_dotenv()

# 2. IMPORTS
from services.auth_agent import launch_browser_login
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

def save_user_secret(user_id, cookie_value):
    data = load_all_secrets()
    data[str(user_id)] = cookie_value
    with open(DATA_FILE, "w") as f: json.dump(data, f, indent=2)

def get_user_secret(user_id):
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
        [InlineKeyboardButton(text="🎙️ I have a Story (Voice)", callback_data="mode_story")],
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
        [InlineKeyboardButton(text="🚀 Auto-Connect (Opens Browser)", callback_data="auto_connect")]
    ])

def get_publish_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Publish to LinkedIn", callback_data="action_publish")],
        [InlineKeyboardButton(text="❌ Done (Cancel)", callback_data="action_cancel")]
    ])

# --- 3. HANDLERS ---

@dp.message(Command("start"))
async def start_command(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    cookie = get_user_secret(user_id)
    
    if cookie:
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
    await state.set_state(BotState.waiting_for_voice)
    await callback.message.edit_text(
        "🎙️ **Story Mode Active**\n\n"
        "👇 **Record a Voice Note** (English or Russian).\n"
        "I will transcribe it and structure it into a post.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Back", callback_data="back_to_root")]
        ])
    )

@dp.callback_query(F.data == "back_to_root")
async def back_to_root(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(
        "👇 **How do you want to create today?**",
        reply_markup=get_root_menu()
    )

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
    
    # 5. Check Context for Generator Mode
    state_data = await state.get_data()
    research_context = None

    if current_state == BotState.waiting_for_reaction:
        research_context = state_data.get("research_context")
    
    # 6. Run Processing
    loop = asyncio.get_event_loop()
    try:
        post_data = await loop.run_in_executor(None, process_voice_note, file_path, research_context)
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
    await callback.answer()
    status_msg = await callback.message.answer("⏳ **Connecting to LinkedIn...**")

    data = await state.get_data()
    draft_post = data.get("final_post")
    image_path = "temp_generated_image.png" if os.path.exists("temp_generated_image.png") else None
    
    loop = asyncio.get_event_loop()
    result_text = await loop.run_in_executor(
        None, publish_to_linkedin, draft_post['text'], image_path
    )
    
    await status_msg.edit_text(result_text)
    if image_path:
        try: os.remove(image_path)
        except: pass
    await state.clear()

@dp.callback_query(F.data == "action_cancel")
async def process_cancel(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("✅ **Action Cancelled.**")
    await state.clear()

# --- AUTH HANDLERS ---
@dp.callback_query(F.data == "auto_connect")
async def start_auto_login(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    await callback.answer()
    status_msg = await callback.message.edit_text("⏳ **Initializing Browser...**")
    cookie = await launch_browser_login()
    if cookie:
        save_user_secret(user_id, cookie)
        await status_msg.edit_text(
            "✅ **Login Verified!**\n\n"
            "👇 **How do you want to create today?**",
            reply_markup=get_root_menu(), 
            parse_mode="Markdown"
        )
    else:
        await status_msg.edit_text("❌ **Login Failed.**", reply_markup=get_login_menu())

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