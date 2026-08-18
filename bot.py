import os
import sys
import json
import time
import datetime
import telebot
import pandas as pd
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ----------------- CONFIGURATION -----------------
try:
    BOT_TOKEN = os.environ["BOT_TOKEN"]
    ADMIN_ID = int(os.environ["ADMIN_ID"])
    SPREADSHEET_URL = os.environ["SPREADSHEET_URL"]
    GOOGLE_CREDENTIALS_JSON = os.environ["GOOGLE_CREDENTIALS"]
except KeyError as e:
    print(f"❌ Error: Environment variable {e} missing. Please add it in Railway Variables.")
    sys.exit(1)
# --------------------------------------------------

bot = telebot.TeleBot(BOT_TOKEN)

# Temporary memory to hold file data before confirmation
pending_file_uploads = {}

# Google Sheets Setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_dict = json.loads(GOOGLE_CREDENTIALS_JSON)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
spreadsheet = client.open_by_url(SPREADSHEET_URL)

# Main Sheet (Sheet1) and Payment Sheet (Sheet2)
sheet1 = spreadsheet.get_worksheet(0)
try:
    sheet2 = spreadsheet.worksheet("Sheet2")
except:
    sheet2 = spreadsheet.add_worksheet(title="Sheet2", rows="1000", cols="10")
    sheet2.update('A1:H1', [["User ID", "Username", "Bikash Number", "Total OK", "Rate", "Total Payment", "Date", "confirmation"]])

def clean_value(val):
    if val is None: return ""
    val_str = str(val).strip()
    if val_str.endswith(".0"): val_str = val_str[:-2]
    return val_str

def has_bikash_number(user_id):
    try:
        s2_data = sheet2.get_all_values()
        for row in s2_data[1:]:
            if len(row) >= 3 and clean_value(row[0]) == str(user_id):
                bikash = clean_value(row[2])
                if bikash and len(bikash) >= 11:
                    return True
        return False
    except:
        return False

def get_bot_status():
    try:
        val = clean_value(sheet1.cell(1, 6).value).upper()
        return val if val in ["ON", "OFF"] else "ON"
    except:
        return "ON"

def set_bot_status(status):
    sheet1.update_cell(1, 6, status)

def get_admin_settings():
    try:
        rate = float(clean_value(sheet1.cell(1, 9).value) or 5.0)
    except:
        rate = 5.0
    
    date_val = clean_value(sheet1.cell(1, 10).value)
    if not date_val:
        date_val = datetime.datetime.now().strftime("%Y-%m-%d")
        
    return rate, date_val

# Keyboards Setup
def get_user_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(KeyboardButton("📝 Submit File"), KeyboardButton("💳 Payment System"))
    return markup

def get_admin_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    status = get_bot_status()
    collecting_btn = "🔴 Stop Collecting" if status == "ON" else "🟢 Start Collecting"
    markup.row(KeyboardButton(collecting_btn), KeyboardButton("📊 Send Filtered Report"))
    markup.row(KeyboardButton("📢 Send Broadcast"), KeyboardButton("💸 Payment Done"))
    markup.row(KeyboardButton("🗑️ Delete User Data"), KeyboardButton("🧹 Clear Data"))
    markup.row(KeyboardButton("ℹ️ Check Status"))
    return markup

@bot.message_handler(commands=['start'])
def start_cmd(message):
    user_id = message.chat.id
    if user_id == ADMIN_ID:
        bot.send_message(user_id, "👋 **অ্যাডমিন প্যানেলে স্বাগতম!**\nবট সফলভাবে চালু রয়েছে।", reply_markup=get_admin_keyboard())
    else:
        bot.send_message(user_id, "👋 **স্বাগতম!**\n\nবিকাশ নম্বর দেখতে বা সেট করতে '💳 Payment System' এ এবং ফাইল দিতে '📝 Submit File' এ ক্লিক করুন।", reply_markup=get_user_keyboard())

# --- Toggle Collecting Status with Broadcast ---
@bot.message_handler(func=lambda msg: msg.chat.id == ADMIN_ID and msg.text in ["🟢 Start Collecting", "🔴 Stop Collecting"])
def toggle_collecting(message):
    current_status = get_bot_status()
    new_status = "OFF" if current_status == "ON" else "ON"
    set_bot_status(new_status)
    
    state_text = "চালু (ON) 🟢" if new_status == "ON" else "বন্ধ (OFF) 🔴"
    bot.send_message(ADMIN_ID, f"⏳ ফাইল কালেকশন **{state_text}** করা হচ্ছে এবং ইউজারদের অটো নোটিশ পাঠানো হচ্ছে...", reply_markup=get_admin_keyboard())

    try:
        s2_data = sheet2.get_all_values()
        all_user_ids = set()
        
        if len(s2_data) > 1:
            for row in s2_data[1:]:
                if len(row) > 0 and clean_value(row[0]).isdigit():
                    all_user_ids.add(clean_value(row[0]))

        if new_status == "ON":
            user_msg = "📢 **নোটিশ:**\n\nফাইল গ্রহণ চালু করা হয়েছে! 🟢\nএখন আপনারা '📝 Submit File' অপশন ব্যবহার করে ফাইল জমা দিতে পারবেন।"
        else:
            user_msg = "📢 **নোটিশ:**\n\nফাইল গ্রহণ আপাতত বন্ধ করা হয়েছে! 🔴\nপরবর্তী নোটিশ না দেওয়া পর্যন্ত নতুন কোনো ফাইল জমা নেওয়া হবে না।"

        success_count = 0
        for u_id in all_user_ids:
            try:
                bot.send_message(int(u_id), user_msg)
                success_count += 1
                time.sleep(0.1)
            except:
                pass

        bot.send_message(ADMIN_ID, f"✅ ফাইল কালেকশন এখন **{state_text}** আছে।\n📢 মোট **{success_count}** জন ইউজারকে নোটিশ পাঠানো হয়েছে!")
    except Exception as e:
        bot.send_message(ADMIN_ID, f"⚠️ ইউজারদের নোটিশ পাঠাতে সমস্যা হয়েছে: {e}")

@bot.message_handler(func=lambda msg: msg.chat.id == ADMIN_ID and msg.text == "ℹ️ Check Status")
def check_status(message):
    status = get_bot_status()
    rate, date_val = get_admin_settings()
    bot.send_message(ADMIN_ID, f"🟢 স্ট্যাটাস: **{status}**\n💰 বর্তমান রেট (I1): **{rate} টাকা**\n📅 সেট করা তারিখ (J1): **{date_val}**", reply_markup=get_admin_keyboard())

# --- Delete Specific User Data (Admin Feature) ---
@bot.message_handler(func=lambda msg: msg.chat.id == ADMIN_ID and msg.text == "🗑️ Delete User Data")
def prompt_delete_user(message):
    msg = bot.reply_to(message, "📲 আপনি যে ইউজারের ডেটা ডিলিট করতে চান তার **User ID** টি লিখে পাঠান:")
    bot.register_next_step_handler(msg, process_delete_user_data)

def process_delete_user_data(message):
    target_uid = clean_value(message.text)
    if not target_uid.isdigit():
        bot.reply_to(message, "❌ ভুল User ID! শুধুমাত্র সংখ্যা দিন।")
        return

    bot.reply_to(message, f"⏳ User ID: **{target_uid}** এর ডেটা Sheet1 থেকে ডিলিট করা হচ্ছে...")
    try:
        all_data = sheet1.get_all_values()
        if len(all_data) <= 1:
            bot.reply_to(message, "⚠️ Sheet1 এ কোনো ডেটা নেই।")
            return

        rows_to_keep = [all_data[0]]  # Header
        deleted_count = 0

        for row in all_data[1:]:
            row_uid = clean_value(row[3]) if len(row) > 3 else ""
            if row_uid == target_uid:
                deleted_count += 1
            else:
                rows_to_keep.append(row)

        if deleted_count == 0:
            bot.reply_to(message, f"⚠️ Sheet1 এ User ID **{target_uid}** এর কোনো ডেটা পাওয়া যায়নি।")
            return

        sheet1.clear()
        sheet1.update(f"A1:E{len(rows_to_keep)}", rows_to_keep)
        bot.reply_to(message, f"✅ সফলভাবে User ID **{target_uid}** এর মোট **{deleted_count}** টি রো ডিলিট করা হয়েছে!")

    except Exception as e:
        bot.reply_to(message, f"❌ ডেটা ডিলিট করতে সমস্যা হয়েছে: {e}")

@bot.message_handler(func=lambda msg: msg.chat.id == ADMIN_ID and msg.text == "🧹 Clear Data")
def clear_data_handler(message):
    try:
        row_count = len(sheet1.get_all_values())
        if row_count > 1:
            sheet1.delete_rows(2, row_count)
            bot.reply_to(message, "✅ Sheet1 সফলভাবে খালি করা হয়েছে।")
        else:
            bot.reply_to(message, "⚠️ Sheet1 ইতিমধ্যে খালি আছে।")
    except Exception as e:
        bot.reply_to(message, f"❌ সমস্যা হয়েছে: {e}")

# --- Broadcast Feature ---
@bot.message_handler(func=lambda msg: msg.chat.id == ADMIN_ID and msg.text == "📢 Send Broadcast")
def broadcast_prompt(message):
    msg = bot.reply_to(message, "📢 আপনি সকল ইউজারের কাছে যে মেসেজটি পাঠাতে চান তা লিখে পাঠান:")
    bot.register_next_step_handler(msg, send_broadcast_to_all)

def send_broadcast_to_all(message):
    text_to_send = message.text
    try:
        s2_data = sheet2.get_all_values()
        all_user_ids = set()
        
        if len(s2_data) > 1:
            for row in s2_data[1:]:
                if len(row) > 0 and clean_value(row[0]).isdigit():
                    all_user_ids.add(clean_value(row[0]))
        
        success_count = 0
        fail_count = 0
        
        for u_id in all_user_ids:
            try:
                bot.send_message(int(u_id), f"📢 **অ্যাডমিন নোটিশ:**\n\n{text_to_send}")
                success_count += 1
                time.sleep(0.2)
            except:
                fail_count += 1
                
        bot.reply_to(message, f"✅ ব্রডকাস্ট সফল!\nসফলভাবে গেছে: **{success_count}** জনের কাছে\nফেইল হয়েছে: **{fail_count}** জনের কাছে")
    except Exception as e:
        bot.reply_to(message, f"❌ ব্রডকাস্ট পাঠাতে সমস্যা হয়েছে: {e}")

# --- Payment Done Handler ---
@bot.message_handler(func=lambda msg: msg.chat.id == ADMIN_ID and msg.text == "💸 Payment Done")
def payment_done_handler(message):
    bot.reply_to(message, "⏳ পেমেন্ট কমপ্লিট মেসেজ পাঠানো ও শিট আপডেট করা হচ্ছে...")
    try:
        s2_data = sheet2.get_all_values()
        if len(s2_data) <= 1:
            bot.reply_to(message, "⚠️ পেমেন্ট শিটে (Sheet2) কোনো ডেটা নেই।")
            return

        blue_format = {"backgroundColor": {"red": 0.7, "green": 0.88, "blue": 0.98}}
        success_count = 0

        for idx, row in enumerate(s2_data[1:], start=2):
            if len(row) >= 8:
                u_id = clean_value(row[0])
                pay_amount = clean_value(row[5])
                confirmation = clean_value(row[7])
                
                if u_id.isdigit() and confirmation.lower() == "done":
                    try:
                        bot.send_message(
                            int(u_id), 
                            f"✅ **পেমেন্ট কমপ্লিট!**\n\nআপনার **{pay_amount} টাকা** সফলভাবে আপনার দেওয়া বিকাশ নম্বরে পাঠানো হয়েছে।\nআমাদের সাথে কাজ করার জন্য ধন্যবাদ!"
                        )
                        sheet2.format(f"A{idx}:H{idx}", blue_format)
                        success_count += 1
                        time.sleep(0.2)
                    except:
                        pass
                        
        if success_count > 0:
            bot.reply_to(message, f"✅ সফলভাবে **{success_count}** জনকে পেমেন্ট কমপ্লিট মেসেজ পাঠানো হয়েছে এবং শিটে হালকা নীল রঙ করা হয়েছে!")
        else:
            bot.reply_to(message, "⚠️ কাউকেই মেসেজ পাঠানো হয়নি। দয়া করে নিশ্চিত করুন যে Sheet2 এর H কলামে 'done' লেখা আছে।")
            
    except Exception as e:
        bot.reply_to(message, f"❌ মেসেজ পাঠাতে সমস্যা হয়েছে: {e}")

# --- Payment System ---
@bot.message_handler(func=lambda msg: msg.text == "💳 Payment System")
def payment_system_handler(message):
    user_id = str(message.chat.id)
    try:
        s2_data = sheet2.get_all_values()
        existing_bikash = ""
        
        for row in s2_data[1:]:
            if len(row) > 0 and clean_value(row[0]) == user_id:
                existing_bikash = clean_value(row[2])
                break
        
        if existing_bikash:
            markup = InlineKeyboardMarkup()
            markup.row(
                InlineKeyboardButton("✏️ Edit", callback_data="edit_bikash"),
                InlineKeyboardButton("💾 Save", callback_data="save_bikash")
            )
            bot.reply_to(message, f"💳 আপনার বর্তমান সেভ করা বিকাশ নম্বর:\n👉 **{existing_bikash}**\n\nআপনি কি এটি রাখতে চান নাকি পরিবর্তন করতে চান?", reply_markup=markup)
        else:
            msg = bot.reply_to(message, "📲 আপনার সঠিক বিকাশ (Bikash) নম্বরটি এখানে লিখে পাঠান (যেমন: 017xxxxxxxx):")
            bot.register_next_step_handler(msg, save_bikash_number)
    except Exception as e:
        bot.reply_to(message, f"❌ সমস্যা হয়েছে: {e}")

@bot.callback_query_handler(func=lambda call: call.data in ["edit_bikash", "save_bikash"])
def payment_inline_callback(call):
    user_id = str(call.message.chat.id)
    try:
        bot.edit_message_reply_markup(chat_id=user_id, message_id=call.message.message_id, reply_markup=None)
    except:
        pass

    if call.data == "edit_bikash":
        bot.answer_callback_query(call.id, "নতুন নম্বর এডিট মোড চালু হয়েছে।")
        msg = bot.send_message(user_id, "📲 আপনার নতুন সঠিক বিকাশ নম্বরটি লিখে পাঠান:")
        bot.register_next_step_handler(msg, save_bikash_number)
    elif call.data == "save_bikash":
        bot.answer_callback_query(call.id, "সংরক্ষিত হয়েছে!")
        bot.send_message(user_id, "✅ আপনার পেমেন্ট পদ্ধতি সফলভাবে নিশ্চিত করা হয়েছে!")

def save_bikash_number(message):
    user_id = str(message.chat.id)
    username = message.from_user.username or message.from_user.first_name
    bikash_num = clean_value(message.text)

    if not bikash_num.isdigit() or len(bikash_num) < 11:
        bot.reply_to(message, "❌ ভুল নম্বর! দয়া করে সঠিক ১১ ডিজিটের বিকাশ নম্বর দিন। আবার চেষ্টা করতে '💳 Payment System' এ চাপুন।")
        return

    try:
        s2_data = sheet2.get_all_values()
        row_index = -1
        
        for idx, row in enumerate(s2_data[1:], start=2):
            if len(row) > 0 and clean_value(row[0]) == user_id:
                row_index = idx
                break
        
        if row_index != -1:
            sheet2.update_cell(row_index, 3, bikash_num)
            sheet2.update_cell(row_index, 2, username)
        else:
            rate, date_val = get_admin_settings()
            sheet2.append_row([user_id, username, bikash_num, 0, rate, 0, date_val, ""])

        bot.reply_to(message, f"✅ ধন্যবাদ! আপনার বিকাশ নম্বর (**{bikash_num}**) সফলভাবে সেভ করা হয়েছে। এখন আপনি ফাইল জমা দিতে পারবেন।")
    except Exception as e:
        bot.reply_to(message, f"❌ বিকাশ নম্বর সেভ করতে সমস্যা হয়েছে: {e}")

# --- Submit Prompt ---
@bot.message_handler(func=lambda msg: msg.text == "📝 Submit File")
def submit_prompt(message):
    user_id = str(message.chat.id)
    
    if user_id != str(ADMIN_ID) and not has_bikash_number(user_id):
        bot.reply_to(message, "⚠️ **আপনার বিকাশ নম্বর সেট করা নেই!**\n\nফাইল জমা দেওয়ার আগে অবশ্যই '💳 Payment System' অপশনে ক্লিক করে আপনার বিকাশ নম্বর সেভ করুন।")
        return

    status = get_bot_status()
    if status == "OFF":
        bot.reply_to(message, "❌ **বর্তমানে ফাইল কালেকশন বন্ধ রয়েছে!**")
        return
        
    bot.reply_to(message, "👉 আপনার কাজের Excel (.xlsx) ফাইলটি এখন সেন্ড করুন।")

# --- Document Upload Handler with Confirmation Prompt ---
@bot.message_handler(content_types=['document'])
def handle_docs(message):
    user_id = str(message.chat.id)
    
    if user_id != str(ADMIN_ID):
        if not has_bikash_number(user_id):
            bot.reply_to(message, "⚠️ **আপনার বিকাশ নম্বর সেট করা নেই!**\n\nফাইল জমা দেওয়ার আগে '💳 Payment System' অপশনে গিয়ে বিকাশ নম্বরটি সেভ করুন।")
            return

        status = get_bot_status()
        if status == "OFF":
            bot.reply_to(message, "❌ **বট এখন ফাইল কালেকশন বন্ধ রেখেছে।**")
            return

    file_name = message.document.file_name
    if not file_name.endswith(('.xlsx', '.xls')):
        bot.reply_to(message, "❌ অনুগ্রহ করে একটি সঠিক Excel (.xlsx) ফাইল পাঠান।")
        return

    bot.reply_to(message, "⏳ ফাইলটি চেক করা হচ্ছে...")
    
    file_info = bot.get_file(message.document.file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    
    temp_path = f"temp_{user_id}.xlsx"
    with open(temp_path, 'wb') as f:
        f.write(downloaded_file)

    try:
        df = pd.read_excel(temp_path, header=None)
        username = message.from_user.username or message.from_user.first_name
        rows_to_append = []

        for _, row in df.iterrows():
            col_a = clean_value(row.iloc[0]) if len(row) > 0 else ""
            col_b = clean_value(row.iloc[1]) if len(row) > 1 else ""
            col_c = clean_value(row.iloc[2]) if len(row) > 2 else ""
            
            if col_a:
                rows_to_append.append([col_a, col_b, col_c, user_id, username])

    except Exception as e:
        if os.path.exists(temp_path): os.remove(temp_path)
        bot.reply_to(message, f"❌ ফাইল রিড করতে সমস্যা হয়েছে: {e}")
        return

    if os.path.exists(temp_path): os.remove(temp_path)

    if not rows_to_append:
        bot.reply_to(message, "⚠️ আপনার ফাইলে কোনো ডেটা পাওয়া যায়নি।")
        return

    # Memory-তে সাময়িকভাবে সেভ করে রাখা হচ্ছে
    pending_file_uploads[user_id] = rows_to_append
    total_count = len(rows_to_append)

    # Confirmation Buttons
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("✅ Confirm & Save", callback_data="confirm_file"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel_file")
    )

    bot.reply_to(
        message, 
        f"📊 **ফাইল রিভিউ:**\n\nআপনার ফাইলে **{total_count}** টি অ্যাকাউন্ট পাওয়া গেছে।\nআপনি কি এটি ফাইনাল জমা দিতে চান?", 
        reply_markup=markup
    )

# --- Confirmation Inline Callback ---
@bot.callback_query_handler(func=lambda call: call.data in ["confirm_file", "cancel_file"])
def handle_file_confirmation(call):
    user_id = str(call.message.chat.id)

    try:
        bot.edit_message_reply_markup(chat_id=user_id, message_id=call.message.message_id, reply_markup=None)
    except:
        pass

    if call.data == "confirm_file":
        if user_id in pending_file_uploads:
            rows_data = pending_file_uploads[user_id]
            try:
                sheet1.append_rows(rows_data)
                total_count = len(rows_data)
                bot.answer_callback_query(call.id, "ফাইল জমা হয়েছে!")
                bot.send_message(user_id, f"✅ আপনার **{total_count}** টি অ্যাকাউন্ট সফলভাবে জমা হয়েছে!")
            except Exception as e:
                bot.send_message(user_id, f"❌ গুগল শিটে ডেটা সেভ করতে সমস্যা হয়েছে: {e}")
            finally:
                del pending_file_uploads[user_id]
        else:
            bot.send_message(user_id, "⚠️ পেন্ডিং কোনো ফাইলের ডেটা পাওয়া যায়নি। আবার ট্রাই করুন।")

    elif call.data == "cancel_file":
        if user_id in pending_file_uploads:
            del pending_file_uploads[user_id]
        bot.answer_callback_query(call.id, "বাতিল করা হয়েছে")
        bot.send_message(user_id, "❌ ফাইল জমা দেওয়া বাতিল করা হয়েছে। আপনি চাইলে সঠিক ফাইলটি আবার সেন্ড করতে পারেন।")

# --- Report Handler ---
@bot.message_handler(func=lambda msg: msg.chat.id == ADMIN_ID and msg.text == "📊 Send Filtered Report")
def admin_report_handler(message):
    bot.reply_to(message, "⏳ ডেটা প্রসেস, ফিল্টার এবং পেমেন্ট হিসাব করা হচ্ছে...")
    
    try:
        all_data = sheet1.get_all_values()
        if len(all_data) <= 1:
            bot.reply_to(message, "⚠️ Sheet1 এ কোনো ডেটা নেই। সংযোগ বা ডেটা চেক করুন।")
            return

        PER_TASK_RATE, REPORT_DATE = get_admin_settings()

        good_accounts = set()
        for row in all_data[1:]:
            if len(row) > 7 and row[7]:
                good_accounts.add(clean_value(row[7]))

        user_stats = {} 
        df_rows = []

        for row in all_data[1:]:
            if len(row) >= 3 and row[0]:
                col_a = clean_value(row[0])
                col_b = clean_value(row[1])
                col_c = clean_value(row[2])
                u_id = clean_value(row[3]) if len(row) > 3 else "Unknown"
                u_name = clean_value(row[4]) if len(row) > 4 else "User"

                if u_id not in user_stats:
                    user_stats[u_id] = {"name": u_name, "total": 0, "ok": 0}

                user_stats[u_id]["total"] += 1

                if col_a in good_accounts:
                    user_stats[u_id]["ok"] += 1
                    df_rows.append({
                        "Col_A": col_a,
                        "Col_B": col_b,
                        "Col_C": col_c,
                        "UserID": u_id,
                        "Username": u_name
                    })

        s2_data = sheet2.get_all_values()
        existing_users_map = {}
        
        if len(s2_data) > 1:
            for s2_row in s2_data[1:]:
                if len(s2_row) > 0 and clean_value(s2_row[0]) != "":
                    u_id = clean_value(s2_row[0])
                    existing_users_map[u_id] = {
                        "username": s2_row[1] if len(s2_row) > 1 else "",
                        "bikash": s2_row[2] if len(s2_row) > 2 else "",
                        "confirmation": s2_row[7] if len(s2_row) > 7 else ""
                    }

        for u_id, stats in user_stats.items():
            if u_id not in existing_users_map:
                existing_users_map[u_id] = {"username": stats["name"], "bikash": "", "confirmation": ""}
            else:
                existing_users_map[u_id]["username"] = stats["name"]

        active_list = []
        inactive_list = []

        for u_id, info in existing_users_map.items():
            ok_count = user_stats[u_id]["ok"] if u_id in user_stats else 0
            total_pay = ok_count * PER_TASK_RATE
            
            row_data = [u_id, info["username"], info["bikash"], ok_count, PER_TASK_RATE, total_pay, REPORT_DATE, info["confirmation"]]
            
            if ok_count > 0:
                active_list.append(row_data)
            else:
                inactive_list.append(row_data)

        final_sheet2_rows = [["User ID", "Username", "Bikash Number", "Total OK", "Rate", "Total Payment", "Date", "confirmation"]] + active_list + inactive_list

        sheet2.clear()
        sheet2.update(f"A1:H{len(final_sheet2_rows)}", final_sheet2_rows)

        green_format = {"backgroundColor": {"red": 0.85, "green": 0.95, "blue": 0.85}}
        blue_format = {"backgroundColor": {"red": 0.7, "green": 0.88, "blue": 0.98}}

        for idx, row in enumerate(final_sheet2_rows[1:], start=2):
            ok_val = int(row[3]) if str(row[3]).isdigit() else 0
            conf_val = clean_value(row[7]).lower()
            
            if conf_val == "done":
                sheet2.format(f"A{idx}:H{idx}", blue_format)
            elif ok_val > 0:
                sheet2.format(f"A{idx}:H{idx}", green_format)

        for u_id, stats in user_stats.items():
            if u_id.isdigit():
                try:
                    pay_amount = stats['ok'] * PER_TASK_RATE
                    bot.send_message(
                        int(u_id),
                        f"📊 **তারিখ: {REPORT_DATE} এর কাজের রিপোর্ট:**\n\n"
                        f"📌 মোট জমা দিয়েছেন: **{stats['total']}** টি\n"
                        f"✅ OK হয়েছে: **{stats['ok']}** টি\n"
                        f"💰 পেমেন্ট পাবেন: **{pay_amount} টাকা**"
                    )
                except:
                    pass

        if df_rows:
            matched_df = pd.DataFrame(df_rows)
            report_file = "Filtered_Report.xlsx"
            matched_df.to_excel(report_file, index=False)
            
            with open(report_file, 'rb') as f:
                bot.send_document(ADMIN_ID, f, caption=f"📂 ফিল্টার করা রেজাল্ট ফাইল (তারিখ: {REPORT_DATE})।")
            
            if os.path.exists(report_file): os.remove(report_file)
        else:
            bot.reply_to(message, f"⚠️ গুড অ্যাকাউন্টের সাথে কোনো অ্যাকাউন্ট ম্যাচ করেনি। তবে Sheet2 ({REPORT_DATE}) আপডেট হয়েছে।")

    except Exception as e:
        bot.reply_to(message, f"❌ রিপোর্ট তৈরি করতে সমস্যা হয়েছে: {e}")

if __name__ == "__main__":
    print("Bot is running with File Confirmation and Specific User Delete Features...")
    while True:
        try:
            bot.infinity_polling(timeout=20, long_polling_timeout=15)
        except Exception as e:
            print(f"Error: {e}. Retrying in 5s...")
            time.sleep(5)
