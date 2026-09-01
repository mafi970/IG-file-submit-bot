import os
import json
import time
import datetime
import telebot
import pandas as pd
from telebot.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
import gspread
from oauth2client.service_account import ServiceAccountCredentials


# ----------------- CONFIGURATION (Railway Environment Variables) -----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
SPREADSHEET_URL = os.getenv("SPREADSHEET_URL")
CREDENTIALS_JSON = os.getenv("CREDENTIALS_JSON")

# চ্যানেল ভেরিফিকেশন কনফিগারেশন
CHANNEL_USERNAME = "@EasyEarnMatrix"
CHANNEL_LINK = "https://t.me/EasyEarnMatrix"
CHANNEL_NAME = "Easy Earn Matrix🌐"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WELCOME_CONFIG_FILE = os.path.join(BASE_DIR, "welcome_config.json")
# ----------------------------------------------------------------------------------

bot = telebot.TeleBot(BOT_TOKEN)
pending_file_uploads = {}


# Google Sheets Setup using Environment Variable JSON
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

try:
    if not CREDENTIALS_JSON:
        raise ValueError(
            "Railway-তে 'CREDENTIALS_JSON' এনভায়রনমেন্ট "
            "ভ্যারিয়েবল দেওয়া হয়নি বা এটি খালি!"
        )

    creds_dict = json.loads(CREDENTIALS_JSON)

    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        creds_dict,
        scope
    )

    client = gspread.authorize(creds)

    spreadsheet = client.open_by_url(
        SPREADSHEET_URL
    )

    sheet_collecting = spreadsheet.worksheet("collecting")
    sheet_payments = spreadsheet.worksheet("payments")
    sheet_report = spreadsheet.worksheet("report")
    sheet_all_users = spreadsheet.worksheet("all users")
    sheet_all_number = spreadsheet.worksheet("all number")

except Exception as e:
    print(
        f"❌ Error connecting to Google Sheets: {e}"
    )
    exit()


def clean_value(val):
    if val is None:
        return ""

    val_str = str(val).strip()

    if val_str.endswith(".0"):
        val_str = val_str[:-2]

    return val_str


def has_bikash_number(user_id):
    try:
        s_data = sheet_all_number.get_all_values()

        for row in s_data[1:]:
            if (
                len(row) >= 3
                and clean_value(row[0]) == str(user_id)
            ):
                bikash = clean_value(row[2])

                if bikash and len(bikash) >= 11:
                    return True

        return False

    except:
        return False


def save_user_to_sheet(user_id, username):
    try:
        user_id_str = str(user_id)

        all_rows = sheet_all_users.get_all_values()

        if not all_rows:
            sheet_all_users.append_row(
                ["User ID", "Username"]
            )

            all_rows = [
                ["User ID", "Username"]
            ]

        existing_ids = [
            clean_value(row[0])
            for row in all_rows[1:]
            if len(row) > 0
        ]

        if user_id_str not in existing_ids:
            sheet_all_users.append_row(
                [
                    user_id_str,
                    username
                ]
            )

    except Exception as e:
        print(
            f"Error saving user to 'all users' sheet: {e}"
        )


def get_all_registered_users():
    user_ids = set()

    try:
        a_data = sheet_all_users.get_all_values()

        for row in a_data[1:]:
            if (
                len(row) > 0
                and clean_value(row[0]).isdigit()
            ):
                user_ids.add(
                    clean_value(row[0])
                )

    except:
        pass

    try:
        s_data = sheet_all_number.get_all_values()

        for row in s_data[1:]:
            if (
                len(row) > 0
                and clean_value(row[0]).isdigit()
            ):
                user_ids.add(
                    clean_value(row[0])
                )

    except:
        pass

    try:
        c_data = sheet_collecting.get_all_values()

        for row in c_data[1:]:
            if (
                len(row) > 3
                and clean_value(row[3]).isdigit()
            ):
                user_ids.add(
                    clean_value(row[3])
                )

    except:
        pass

    return list(user_ids)


def get_bot_status():
    try:
        val = clean_value(
            sheet_collecting.cell(1, 6).value
        ).upper()

        return (
            val
            if val in ["ON", "OFF"]
            else "ON"
        )

    except:
        return "ON"


def set_bot_status(status):
    sheet_collecting.update_cell(
        1,
        6,
        status
    )


def get_admin_settings():
    try:
        rate = float(
            clean_value(
                sheet_report.cell(1, 9).value
            ) or 5.0
        )

    except:
        rate = 5.0

    try:
        date_val = clean_value(
            sheet_report.cell(1, 10).value
        )

        if not date_val:
            date_val = datetime.datetime.now().strftime(
                "%Y-%m-%d"
            )

    except:
        date_val = datetime.datetime.now().strftime(
            "%Y-%m-%d"
        )

    return rate, date_val


# চ্যানেল জয়েন চেক ফাংশন
def check_user_membership(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if member.status in ["member", "administrator", "creator"]:
            return True
        return False
    except Exception as e:
        print(f"Membership check error: {e}")
        return False


def verify_membership_or_warn(message):
    user_id = message.chat.id
    if user_id == ADMIN_ID:
        return True
    if not check_user_membership(user_id):
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton(CHANNEL_NAME, url=CHANNEL_LINK))
        markup.row(InlineKeyboardButton("✅ Verify", callback_data="verify_join", style="success"))

        verify_msg = (
            "*📢 আমাদের সার্ভিসটি ব্যবহার করতে অবশ্যই নিচের চ্যানেল/গ্রুপগুলোতে যুক্ত হতে হবে。\n\n"
            "যুক্ত হওয়ার পর 'Verify' বাটনে ক্লিক করুন।*"
        )
        bot.send_message(
            user_id,
            verify_msg,
            parse_mode="Markdown",
            reply_markup=markup
        )
        return False
    return True


# ============================================================
# USER KEYBOARD
# ============================================================
def get_user_keyboard():
    markup = ReplyKeyboardMarkup(
        resize_keyboard=True
    )

    markup.row(
        KeyboardButton(
            "📝 Submit File",
            style="success"
        ),
        KeyboardButton(
            "💳 Payment System",
            style="success"
        )
    )

    markup.row(
        KeyboardButton(
            "🛠️ Support",
            style="danger"
        )
    )

    return markup


# ============================================================
# ADMIN KEYBOARD
# ============================================================
def get_admin_keyboard():
    markup = ReplyKeyboardMarkup(
        resize_keyboard=True
    )

    status = get_bot_status()

    if status == "ON":
        collecting_btn = "🔴 Stop Collecting"
        collecting_style = "danger"
    else:
        collecting_btn = "🟢 Start Collecting"
        collecting_style = "success"

    markup.row(
        KeyboardButton(
            collecting_btn,
            style=collecting_style
        ),
        KeyboardButton(
            "📊 Generate Report",
            style="primary"
        )
    )

    markup.row(
        KeyboardButton(
            "📢 Send Broadcast",
            style="primary"
        ),
        KeyboardButton(
            "💬 Message User",
            style="primary"
        )
    )

    markup.row(
        KeyboardButton(
            "⚙️ Set Welcome Msg",
            style="primary"
        ),
        KeyboardButton(
            "💸 Payment Done",
            style="success"
        )
    )

    markup.row(
        KeyboardButton(
            "🗑️ Delete User Data",
            style="danger"
        ),
        KeyboardButton(
            "🧹 Clear Data",
            style="danger"
        )
    )

    markup.row(
        KeyboardButton(
            "ℹ️ Check Status",
            style="primary"
        )
    )

    return markup


def load_welcome_msg():
    if os.path.exists(
        WELCOME_CONFIG_FILE
    ):
        with open(
            WELCOME_CONFIG_FILE,
            "r"
        ) as f:
            return json.load(f)

    return None


def save_welcome_msg(message_id):
    with open(
        WELCOME_CONFIG_FILE,
        "w"
    ) as f:
        json.dump(
            {
                "message_id": message_id
            },
            f
        )


def send_welcome_content(user_id, message):
    welcome_data = load_welcome_msg()

    if (
        welcome_data
        and "message_id" in welcome_data
    ):
        try:
            bot.copy_message(
                chat_id=user_id,
                from_chat_id=ADMIN_ID,
                message_id=welcome_data["message_id"],
                reply_markup=get_user_keyboard()
            )
            return
        except Exception as e:
            print(
                f"Custom welcome msg failed: {e}"
            )

    first_name = message.from_user.first_name if hasattr(message, 'from_user') and message.from_user else "ইউজার"
    welcome_user = (
        f"*👋 আসসালামু আলাইকুম, {first_name}!\n\n"
        "🎉 আমাদের বটে আপনাকে স্বাগতম!\n\n"
        "১. কাজ জমা দেওয়ার আগে '💳 Payment System' এ গিয়ে বিকাশ নম্বর সেট করুন।\n"
        "২. এরপর '📝 Submit File' অপশন চাপ দিয়ে Excel (.xlsx) ফাইল জমা দিন.*"
    )

    bot.send_message(
        user_id,
        welcome_user,
        parse_mode="Markdown",
        reply_markup=get_user_keyboard()
    )


@bot.message_handler(commands=['start'])
def start_cmd(message):
    user_id = message.chat.id
    username = (
        message.from_user.username
        or message.from_user.first_name
    )

    save_user_to_sheet(
        user_id,
        username
    )

    if user_id == ADMIN_ID:
        welcome_admin = (
            "*👑 অ্যাডমিন প্যানেলে স্বাগতম!\n\n"
            "বট সফলভাবে রানিং রয়েছে.*"
        )
        bot.send_message(
            user_id,
            welcome_admin,
            parse_mode="Markdown",
            reply_markup=get_admin_keyboard()
        )
        return

    if not check_user_membership(user_id):
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton(CHANNEL_NAME, url=CHANNEL_LINK))
        markup.row(InlineKeyboardButton("✅ Verify", callback_data="verify_join", style="success"))

        verify_msg = (
            "*📢 আমাদের সার্ভিসটি ব্যবহার করতে অবশ্যই নিচের চ্যানেল/গ্রুপগুলোতে যুক্ত হতে হবে。\n\n"
            "যুক্ত হওয়ার পর 'Verify' বাটনে ক্লিক করুন.*"
        )
        bot.send_message(
            user_id,
            verify_msg,
            parse_mode="Markdown",
            reply_markup=markup
        )
        return

    send_welcome_content(user_id, message)


@bot.callback_query_handler(func=lambda call: call.data == "verify_join")
def verify_join_callback(call):
    user_id = call.message.chat.id
    if check_user_membership(user_id):
        try:
            bot.delete_message(chat_id=user_id, message_id=call.message.message_id)
        except:
            pass
        bot.answer_callback_query(call.id, "✅ ভেরিফিকেশন সফল হয়েছে!")
        send_welcome_content(user_id, call.message)
    else:
        bot.answer_callback_query(call.id, "⚠️ আপনি এখনো চ্যানেল/গ্রুপগুলোতে যুক্ত হননি!", show_alert=True)


@bot.message_handler(
    func=lambda msg:
    msg.chat.id == ADMIN_ID
    and msg.text == "⚙️ Set Welcome Msg"
)
def prompt_welcome_msg(message):
    msg = bot.reply_to(
        message,
        "*📝 নতুন ওয়েলকাম মেসেজ সেট করুন:\n\n"
        "আপনি ইউজারদের যে মেসেজ দেখাতে চান, সেটি সেন্ড বা ফরওয়ার্ড করুন.*",
        parse_mode="Markdown"
    )

    bot.register_next_step_handler(
        msg,
        save_custom_welcome
    )


def save_custom_welcome(message):
    try:
        save_welcome_msg(
            message.message_id
        )

        bot.reply_to(
            message,
            "*✅ ওয়েলকাম মেসেজ সফলভাবে সেভ হয়েছে!*",
            parse_mode="Markdown"
        )

    except Exception as e:
        bot.reply_to(
            message,
            f"*❌ সমস্যা হয়েছে: {e}*",
            parse_mode="Markdown"
        )


@bot.message_handler(
    func=lambda msg:
    msg.chat.id == ADMIN_ID
    and msg.text == "💬 Message User"
)
def prompt_message_user(message):
    msg = bot.reply_to(
        message,
        "*📲 আপনি যে ইউজারকে মেসেজ পাঠাতে চান, তার User ID টি এখানে লিখুন:*",
        parse_mode="Markdown"
    )

    bot.register_next_step_handler(
        msg,
        prompt_message_content
    )


def prompt_message_content(message):
    target_id = message.text.strip()

    if not target_id.isdigit():
        bot.reply_to(
            message,
            "*❌ ভুল User ID! শুধুমাত্র সংখ্যা দিন.*",
            parse_mode="Markdown"
        )
        return

    msg = bot.reply_to(
        message,
        f"*✉️ User ID {target_id} কে কী পাঠাতে চান? মেসেজ বা ছবি সেন্ড করুন:*",
        parse_mode="Markdown"
    )

    bot.register_next_step_handler(
        msg,
        lambda m:
        send_specific_user_msg(
            m,
            target_id
        )
    )


def send_specific_user_msg(
    message,
    target_id
):
    try:
        bot.copy_message(
            chat_id=int(target_id),
            from_chat_id=message.chat.id,
            message_id=message.message_id
        )

        bot.reply_to(
            message,
            f"*✅ User ID {target_id} এর কাছে মেসেজ সফলভাবে পাঠানো হয়েছে!*",
            parse_mode="Markdown"
        )

    except Exception as e:
        bot.reply_to(
            message,
            f"*❌ সমস্যা হয়েছে: {e}*",
            parse_mode="Markdown"
        )


@bot.message_handler(
    func=lambda msg:
    msg.text == "🛠️ Support"
)
def user_support_handler(message):
    if not verify_membership_or_warn(message):
        return

    user_id = message.chat.id
    username = (
        message.from_user.username
        or message.from_user.first_name
    )

    save_user_to_sheet(
        user_id,
        username
    )

    bot.reply_to(
        message,
        "*🎧 কাস্টমার সাপোর্ট:\n\n"
        "যেকোনো সমস্যায় সরাসরি অ্যাডমিনের সাথে যোগাযোগ করুন: @Mafi5661*",
        parse_mode="Markdown"
    )


@bot.message_handler(
    func=lambda msg:
    msg.chat.id == ADMIN_ID
    and msg.text in [
        "🟢 Start Collecting",
        "🔴 Stop Collecting"
    ]
)
def toggle_collecting(message):
    current_status = get_bot_status()

    new_status = (
        "OFF"
        if current_status == "ON"
        else "ON"
    )

    set_bot_status(
        new_status
    )

    bot.send_message(
        ADMIN_ID,
        f"*✅ ফাইল কালেকশন এখন {new_status} করা হয়েছে.*",
        parse_mode="Markdown",
        reply_markup=get_admin_keyboard()
    )

    all_user_ids = get_all_registered_users()

    if new_status == "OFF":
        notice_text = (
            "*📢 নোটিশ:\n\n"
            "ফাইল গ্রহণ আপাতত বন্ধ করা হয়েছে! 🔴\n"
            "পরবর্তী নোটিশ না দেওয়া পর্যন্ত নতুন কোনো ফাইল জমা নেওয়া হবে না.*"
        )
    else:
        notice_text = (
            "*📢 নোটিশ:\n\n"
            "ফাইল কালেকশন শুরু হয়েছে! 🟢\n"
            "এখন থেকে নিয়মিত ফাইল জমা দিতে পারবেন.*"
        )

    success_cnt = 0

    for u_id in all_user_ids:
        try:
            bot.send_message(
                int(u_id),
                notice_text,
                parse_mode="Markdown"
            )
            success_cnt += 1
            time.sleep(0.1)
        except:
            pass

    bot.reply_to(
        message,
        f"*📢 নোটিশ সফলভাবে মোট {success_cnt} জন ইউজারের কাছে পাঠানো হয়েছে.*",
        parse_mode="Markdown"
    )


# ============================================================
# SUBMIT FILE
# ============================================================
@bot.message_handler(
    func=lambda msg:
    msg.text == "📝 Submit File"
)
def submit_prompt(message):
    if not verify_membership_or_warn(message):
        return

    user_id = str(
        message.chat.id
    )

    username = (
        message.from_user.username
        or message.from_user.first_name
    )

    save_user_to_sheet(
        user_id,
        username
    )

    if (
        user_id != str(ADMIN_ID)
        and not has_bikash_number(user_id)
    ):
        bot.reply_to(
            message,
            "*⚠️ ফাইল জমার আগে '💳 Payment System' এ বিকাশ নম্বর সেভ করুন.*",
            parse_mode="Markdown"
        )
        return

    if get_bot_status() == "OFF":
        bot.reply_to(
            message,
            "*❌ বর্তমানে ফাইল রিসিভ করা বন্ধ আছে।\n\nকিছু সময় পর আবার চেষ্টা করুন.*",
            parse_mode="Markdown"
        )
        return

    bot.reply_to(
        message,
        "*👉 আপনার Excel (.xlsx) ফাইলটি এখন পাঠান.*",
        parse_mode="Markdown"
    )


@bot.message_handler(
    content_types=['document']
)
def handle_docs(message):
    if not verify_membership_or_warn(message):
        return

    user_id = str(
        message.chat.id
    )

    username = (
        message.from_user.username
        or message.from_user.first_name
    )

    save_user_to_sheet(
        user_id,
        username
    )

    if user_id != str(ADMIN_ID):
        if not has_bikash_number(user_id):
            return bot.reply_to(
                message,
                "*⚠️ আগে বিকাশ নম্বর সেভ করুন.*",
                parse_mode="Markdown"
            )

        if get_bot_status() == "OFF":
            return bot.reply_to(
                message,
                "*❌ ফাইল কালেকশন বন্ধ.*",
                parse_mode="Markdown"
            )

    file_name = message.document.file_name

    if not file_name.endswith(
        ('.xlsx', '.xls')
    ):
        return bot.reply_to(
            message,
            "*❌ সঠিক Excel (.xlsx) ফাইল পাঠান.*",
            parse_mode="Markdown"
        )

    bot.reply_to(
        message,
        "*⏳ ফাইলটি চেক করা হচ্ছে...*",
        parse_mode="Markdown"
    )

    file_info = bot.get_file(
        message.document.file_id
    )

    downloaded_file = bot.download_file(
        file_info.file_path
    )

    temp_path = os.path.join(
        BASE_DIR,
        f"temp_{user_id}.xlsx"
    )

    with open(
        temp_path,
        'wb'
    ) as f:
        f.write(
            downloaded_file
        )

    try:
        df = pd.read_excel(
            temp_path,
            header=None
        )

        rows_to_append = []

        for _, row in df.iterrows():
            col_a = (
                clean_value(row.iloc[0])
                if len(row) > 0
                else ""
            )

            col_b = (
                clean_value(row.iloc[1])
                if len(row) > 1
                else ""
            )

            col_c = (
                clean_value(row.iloc[2])
                if len(row) > 2
                else ""
            )

            if col_a:
                rows_to_append.append(
                    [
                        col_a,
                        col_b,
                        col_c,
                        user_id,
                        username
                    ]
                )

    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)

        return bot.reply_to(
            message,
            f"*❌ ফাইল রিড করতে সমস্যা: {e}*",
            parse_mode="Markdown"
        )

    if os.path.exists(temp_path):
        os.remove(temp_path)

    if not rows_to_append:
        return bot.reply_to(
            message,
            "*⚠️ ফাইলে কোনো ডেটা পাওয়া যায়নি.*",
            parse_mode="Markdown"
        )

    pending_file_uploads[user_id] = (
        rows_to_append
    )

    markup = InlineKeyboardMarkup()

    markup.row(
        InlineKeyboardButton(
            "✅ Confirm & Save",
            callback_data="confirm_file",
            style="success"
        ),
        InlineKeyboardButton(
            "❌ Cancel",
            callback_data="cancel_file",
            style="danger"
        )
    )

    bot.reply_to(
        message,
        f"*📊 আপনার ফাইলে {len(rows_to_append)} টি অ্যাকাউন্ট পাওয়া গেছে। ফাইনাল জমা দিবেন?*",
        parse_mode="Markdown",
        reply_markup=markup
    )


@bot.callback_query_handler(
    func=lambda call:
    call.data in [
        "confirm_file",
        "cancel_file"
    ]
)
def handle_file_confirmation(call):
    user_id = str(
        call.message.chat.id
    )

    try:
        bot.edit_message_reply_markup(
            chat_id=user_id,
            message_id=call.message.message_id,
            reply_markup=None
        )
    except:
        pass

    if (
        call.data == "confirm_file"
        and user_id in pending_file_uploads
    ):
        rows_data = pending_file_uploads[
            user_id
        ]

        try:
            col_a_values = (
                sheet_collecting.col_values(1)
            )

            next_row = len(
                col_a_values
            ) + 1

            end_row = (
                next_row
                + len(rows_data)
                - 1
            )

            sheet_collecting.update(
                f'A{next_row}:E{end_row}',
                rows_data
            )

            bot.answer_callback_query(
                call.id,
                "ফাইল জমা হয়েছে!"
            )

            bot.send_message(
                user_id,
                f"*✅ আপনার {len(rows_data)} টি অ্যাকাউন্ট সফলভাবে জমা হয়েছে!*",
                parse_mode="Markdown"
            )

        except Exception as e:
            bot.send_message(
                user_id,
                f"*❌ ডেটা সেভ করতে সমস্যা: {e}*",
                parse_mode="Markdown"
            )

        finally:
            del pending_file_uploads[user_id]

    elif call.data == "cancel_file":
        if user_id in pending_file_uploads:
            del pending_file_uploads[user_id]

        bot.send_message(
            user_id,
            "*❌ ফাইল জমা দেওয়া বাতিল করা হয়েছে.*",
            parse_mode="Markdown"
        )


# ============================================================
# Generate Report Logic
# ============================================================
@bot.message_handler(
    func=lambda msg:
    msg.chat.id == ADMIN_ID
    and msg.text == "📊 Generate Report"
)
def admin_report_handler(message):
    bot.reply_to(
        message,
        "*⏳ 'report' শিট থেকে ডেটা প্রসেস এবং পেমেন্ট হিসাব করা হচ্ছে...*",
        parse_mode="Markdown"
    )

    try:
        all_data = sheet_report.get_all_values()

        if len(all_data) <= 1:
            return bot.reply_to(
                message,
                "*⚠️ 'report' শিটে কোনো ডেটা নেই.*",
                parse_mode="Markdown"
            )

        PER_TASK_RATE, REPORT_DATE = (
            get_admin_settings()
        )

        good_accounts = set()

        for row in all_data[1:]:
            if len(row) > 7 and row[7]:
                good_accounts.add(
                    clean_value(row[7])
                )

        user_stats = {}
        filtered_good_rows = []

        for row in all_data[1:]:
            if (
                len(row) >= 4
                and row[0]
            ):
                col_a = clean_value(
                    row[0]
                )

                u_id = (
                    clean_value(row[3])
                    if len(row) > 3
                    else "Unknown"
                )

                u_name = (
                    clean_value(row[4])
                    if len(row) > 4
                    else "User"
                )

                if u_id not in user_stats:
                    user_stats[u_id] = {
                        "name": u_name,
                        "total": 0,
                        "ok": 0
                    }

                user_stats[u_id]["total"] += 1

                if col_a in good_accounts:
                    user_stats[u_id]["ok"] += 1

                    col_b = (
                        clean_value(row[1])
                        if len(row) > 1
                        else ""
                    )

                    col_c = (
                        clean_value(row[2])
                        if len(row) > 2
                        else ""
                    )

                    filtered_good_rows.append(
                        [
                            col_a,
                            col_b,
                            col_c,
                            u_id,
                            u_name
                        ]
                    )

        s_payments_data = (
            sheet_all_number.get_all_values()
        )

        existing_users_map = {}

        if len(s_payments_data) > 1:
            for s_row in s_payments_data[1:]:
                if (
                    len(s_row) > 0
                    and clean_value(s_row[0]) != ""
                ):
                    u_id = clean_value(
                        s_row[0]
                    )

                    existing_users_map[u_id] = {
                        "username": (
                            s_row[1]
                            if len(s_row) > 1
                            else ""
                        ),
                        "bikash": (
                            s_row[2]
                            if len(s_row) > 2
                            else ""
                        ),
                        "confirmation": ""
                    }

        for u_id, stats in user_stats.items():
            if u_id not in existing_users_map:
                existing_users_map[u_id] = {
                    "username": stats["name"],
                    "bikash": "",
                    "confirmation": ""
                }
            else:
                existing_users_map[u_id][
                    "username"
                ] = stats["name"]

        combined_rows = []

        for u_id, info in existing_users_map.items():
            ok_count = (
                user_stats[u_id]["ok"]
                if u_id in user_stats
                else 0
            )

            if ok_count > 0:
                total_pay = (
                    ok_count
                    * PER_TASK_RATE
                )

                row_data = [
                    u_id,
                    info["username"],
                    info["bikash"],
                    ok_count,
                    PER_TASK_RATE,
                    total_pay,
                    REPORT_DATE,
                    info["confirmation"]
                ]

                combined_rows.append(
                    row_data
                )

        combined_rows.sort(
            key=lambda x: x[3],
            reverse=True
        )

        final_rows = [
            [
                "User ID",
                "Username",
                "Bikash Number",
                "Total OK",
                "Rate",
                "Total Payment",
                "Date",
                "confirmation"
            ]
        ] + combined_rows

        sheet_payments.clear()

        if len(final_rows) > 1:
            sheet_payments.update(
                f"A1:H{len(final_rows)}",
                final_rows
            )

            green_format = {
                "backgroundColor": {
                    "red": 0.8,
                    "green": 1.0,
                    "blue": 0.8
                }
            }

            for idx, row in enumerate(
                combined_rows,
                start=2
            ):
                if row[3] > 0:
                    try:
                        sheet_payments.format(
                            f"A{idx}:H{idx}",
                            green_format
                        )
                    except:
                        pass
        else:
            sheet_payments.update(
                "A1:H1",
                [final_rows[0]]
            )

        try:
            df = pd.DataFrame(
                filtered_good_rows,
                columns=[
                    "Col_A",
                    "Col_B",
                    "Col_C",
                    "UserID",
                    "Username"
                ]
            )

            file_name = (
                "Filtered_Report.xlsx"
            )

            file_path = os.path.join(
                BASE_DIR,
                file_name
            )

            df.to_excel(
                file_path,
                index=False
            )

            with open(
                file_path,
                "rb"
            ) as f:
                caption_text = (
                    f"*📂 ফিল্টার করা রেজাল্ট ফাইল (তারিখ: {REPORT_DATE})।*"
                )

                bot.send_document(
                    message.chat.id,
                    f,
                    caption=caption_text
                )

            if os.path.exists(file_path):
                os.remove(file_path)

        except Exception as e:
            bot.send_message(
                message.chat.id,
                f"*❌ এক্সেল ফাইল তৈরি করতে সমস্যা: {e}*",
                parse_mode="Markdown"
            )

        for u_id, stats in user_stats.items():
            if u_id.isdigit():
                try:
                    pay_amount = (
                        stats["ok"]
                        * PER_TASK_RATE
                    )

                    bot.send_message(
                        int(u_id),
                        f"*📊 রিপোর্ট ({REPORT_DATE}):\n"
                        f"📌 মোট জমা: {stats['total']} টি\n"
                        f"✅ OK: {stats['ok']} টি\n"
                        f"💰 পেমেন্ট: {pay_amount} টাকা*",
                        parse_mode="Markdown"
                    )
                except:
                    pass

        bot.reply_to(
            message,
            "*✅ রিপোর্ট সফলভাবে তৈরি হয়েছে, পেমেন্ট পাওয়া ইউজারদের উপরে ও সবুজ রঙ করা হয়েছে এবং এক্সেল ফাইল পাঠানো হয়েছে!*",
            parse_mode="Markdown"
        )

    except Exception as e:
        bot.reply_to(
            message,
            f"*❌ রিপোর্ট তৈরি করতে সমস্যা: {e}*",
            parse_mode="Markdown"
        )


# ============================================================
# Multi-Media Broadcast Feature
# ============================================================
@bot.message_handler(
    func=lambda msg:
    msg.chat.id == ADMIN_ID
    and msg.text == "📢 Send Broadcast"
)
def broadcast_prompt(message):
    msg = bot.reply_to(
        message,
        "*📢 আপনি সকল ইউজারের কাছে যে মেসেজ বা ছবি/ভিডিও পাঠাতে চান তা এখানে সেন্ড করুন:*",
        parse_mode="Markdown"
    )

    bot.register_next_step_handler(
        msg,
        send_broadcast_to_all
    )


def send_broadcast_to_all(message):
    try:
        all_user_ids = (
            get_all_registered_users()
        )

        success_count = 0
        fail_count = 0

        for u_id in all_user_ids:
            try:
                bot.copy_message(
                    chat_id=int(u_id),
                    from_chat_id=message.chat.id,
                    message_id=message.message_id
                )
                success_count += 1
                time.sleep(0.15)
            except:
                fail_count += 1

        bot.reply_to(
            message,
            f"*✅ ব্রডকাস্ট সফল!\n\n"
            f"🟢 সফল হয়েছে: {success_count} জনের কাছে\n"
            f"🔴 ফেইল হয়েছে: {fail_count} জনের কাছে*",
            parse_mode="Markdown"
        )

    except Exception as e:
        bot.reply_to(
            message,
            f"*❌ ব্রডকাস্ট পাঠাতে সমস্যা হয়েছে: {e}*",
            parse_mode="Markdown"
        )


@bot.message_handler(
    func=lambda msg:
    msg.chat.id == ADMIN_ID
    and msg.text == "🧹 Clear Data"
)
def clear_data_handler(message):
    try:
        row_count = len(
            sheet_collecting.get_all_values()
        )

        if row_count > 1:
            sheet_collecting.delete_rows(
                2,
                row_count
            )

            bot.reply_to(
                message,
                "*✅ Row 1 ঠিক রেখে 'collecting' শিটের ডেটা পরিষ্কার করা হয়েছে.*",
                parse_mode="Markdown"
            )
        else:
            bot.reply_to(
                message,
                "*⚠️ 'collecting' শিটে ডিলিট করার মতো ডেটা নেই.*",
                parse_mode="Markdown"
            )

    except Exception as e:
        bot.reply_to(
            message,
            f"*❌ সমস্যা হয়েছে: {e}*",
            parse_mode="Markdown"
        )


@bot.message_handler(
    func=lambda msg:
    msg.chat.id == ADMIN_ID
    and msg.text == "🗑️ Delete User Data"
)
def prompt_delete_user(message):
    msg = bot.reply_to(
        message,
        "*📲 আপনি যে ইউজারের ডেটা ডিলিট করতে চান তার User ID টি লিখে পাঠান:*",
        parse_mode="Markdown"
    )

    bot.register_next_step_handler(
        msg,
        process_delete_user_data
    )


def process_delete_user_data(message):
    target_uid = clean_value(
        message.text
    )

    if not target_uid.isdigit():
        bot.reply_to(
            message,
            "*❌ ভুল User ID! শুধুমাত্র সংখ্যা দিন.*",
            parse_mode="Markdown"
        )
        return

    bot.reply_to(
        message,
        f"*⏳ User ID: {target_uid} এর ডেটা 'collecting' শিট থেকে ডিলিট করা হচ্ছে...*",
        parse_mode="Markdown"
    )

    try:
        all_data = (
            sheet_collecting.get_all_values()
        )

        if len(all_data) <= 1:
            bot.reply_to(
                message,
                "*⚠️ শিটে ডিলিট করার মতো কোনো ডেটা নেই.*",
                parse_mode="Markdown"
            )
            return

        header_row = all_data[0]
        data_rows = all_data[1:]

        rows_to_keep = [
            header_row
        ]

        deleted_count = 0

        for row in data_rows:
            row_uid = (
                clean_value(row[3])
                if len(row) > 3
                else ""
            )

            if row_uid == target_uid:
                deleted_count += 1
            else:
                rows_to_keep.append(
                    row
                )

        if deleted_count == 0:
            bot.reply_to(
                message,
                f"*⚠️ User ID {target_uid} এর কোনো ডেটা পাওয়া যায়নি.*",
                parse_mode="Markdown"
            )
            return

        sheet_collecting.clear()

        sheet_collecting.update(
            "A1",
            rows_to_keep
        )

        bot.reply_to(
            message,
            f"*✅ সফলভাবে User ID {target_uid} এর মোট {deleted_count} টি রো ডিলিট করা হয়েছে!*",
            parse_mode="Markdown"
        )

    except Exception as e:
        bot.reply_to(
            message,
            f"*❌ ডেটা ডিলিট করতে সমস্যা হয়েছে: {e}*",
            parse_mode="Markdown"
        )


@bot.message_handler(
    func=lambda msg:
    msg.chat.id == ADMIN_ID
    and msg.text == "💸 Payment Done"
)
def payment_done_handler(message):
    bot.reply_to(
        message,
        "*⏳ পেমেন্ট কমপ্লিট মেসেজ পাঠানো ও শিট আপডেট করা হচ্ছে...*",
        parse_mode="Markdown"
    )

    try:
        s_data = (
            sheet_payments.get_all_values()
        )

        if len(s_data) <= 1:
            bot.reply_to(
                message,
                "*⚠️ পেমেন্ট শিটে কোনো ডেটা নেই.*",
                parse_mode="Markdown"
            )
            return

        blue_format = {
            "backgroundColor": {
                "red": 0.7,
                "green": 0.88,
                "blue": 0.98
            }
        }

        success_count = 0

        for idx, row in enumerate(
            s_data[1:],
            start=2
        ):
            if len(row) >= 8:
                u_id = clean_value(
                    row[0]
                )

                pay_amount = clean_value(
                    row[5]
                )

                report_date = clean_value(
                    row[6]
                )

                confirmation = clean_value(
                    row[7]
                )

                if (
                    u_id.isdigit()
                    and confirmation.lower() == "done"
                ):
                    try:
                        msg_text = (
                            "*✅ পেমেন্ট কমপ্লিট!\n\n"
                            f"আপনার {pay_amount} টাকা সফলভাবে আপনার দেওয়া বিকাশ নম্বরে পাঠানো হয়েছে。\n"
                            f"📅 রিপোর্টের তারিখ: {report_date}\n\n"
                            "আমাদের সাথে কাজ করার জন্য ধন্যবাদ!*"
                        )

                        bot.send_message(
                            int(u_id),
                            msg_text,
                            parse_mode="Markdown"
                        )

                        sheet_payments.format(
                            f"A{idx}:H{idx}",
                            blue_format
                        )

                        success_count += 1
                        time.sleep(0.2)

                    except:
                        pass

        if success_count > 0:
            bot.reply_to(
                message,
                f"*✅ সফলভাবে {success_count} জনকে পেমেন্ট মেসেজ পাঠানো হয়েছে!*",
                parse_mode="Markdown"
            )
        else:
            bot.reply_to(
                message,
                "*⚠️ কাউকেই মেসেজ পাঠানো হয়নি। নিশ্চিত করুন যে 'payments' শিটের H কলামে 'done' লেখা আছে.*",
                parse_mode="Markdown"
            )

    except Exception as e:
        bot.reply_to(
            message,
            f"*❌ মেসেজ পাঠাতে সমস্যা হয়েছে: {e}*",
            parse_mode="Markdown"
        )


# ============================================================
# Payment System
# ============================================================
@bot.message_handler(
    func=lambda msg:
    msg.text == "💳 Payment System"
)
def payment_system_handler(message):
    if not verify_membership_or_warn(message):
        return

    user_id = str(
        message.chat.id
    )

    username = (
        message.from_user.username
        or message.from_user.first_name
    )

    save_user_to_sheet(
        user_id,
        username
    )

    try:
        s_data = (
            sheet_all_number.get_all_values()
        )

        existing_bikash = ""

        for row in s_data[1:]:
            if (
                len(row) > 0
                and clean_value(row[0]) == user_id
            ):
                existing_bikash = clean_value(
                    row[2]
                )
                break

        # বিকাশ লোগোর ডাইরেক্ট লিংক
        logo_url = "https://i.ibb.co.com/LzVPxMXZ/vecteezy-bkash-logo-vector.jpg"

        if existing_bikash:
            markup = InlineKeyboardMarkup()

            markup.row(
                InlineKeyboardButton(
                    "✏️ Edit Bikash",
                    callback_data="select_bikash",
                    style="primary"
                ),
                InlineKeyboardButton(
                    "💾 Save",
                    callback_data="save_bikash",
                    style="success"
                )
            )

            caption_text = (
                f"*💳 আপনার রানিং বিকাশ নম্বর: {existing_bikash}\n\n"
                "এটি কি ঠিক আছে, নাকি পরিবর্তন করতে চান?*"
            )

        else:
            markup = InlineKeyboardMarkup()

            markup.row(
                InlineKeyboardButton(
                    "🟣 bKash",
                    callback_data="select_bikash",
                    style="success"
                )
            )

            caption_text = "*💳 পেমেন্ট মেথড সিলেক্ট করুন:*"

        bot.send_photo(
            chat_id=user_id,
            photo=logo_url,
            caption=caption_text,
            parse_mode="Markdown",
            reply_markup=markup
        )

    except Exception as e:
        bot.reply_to(
            message,
            f"*❌ সমস্যা: {e}*",
            parse_mode="Markdown"
        )


@bot.callback_query_handler(
    func=lambda call:
    call.data in [
        "select_bikash",
        "save_bikash"
    ]
)
def payment_inline_callback(call):
    user_id = str(
        call.message.chat.id
    )

    try:
        bot.delete_message(
            chat_id=user_id,
            message_id=call.message.message_id
        )
    except:
        try:
            bot.edit_message_reply_markup(
                chat_id=user_id,
                message_id=call.message.message_id,
                reply_markup=None
            )
        except:
            pass

    if call.data == "select_bikash":
        msg = bot.send_message(
            user_id,
            "*📲 আপনার বিকাশ নম্বরটি লিখে পাঠান:*",
            parse_mode="Markdown"
        )

        bot.register_next_step_handler(
            msg,
            save_bikash_number
        )

    elif call.data == "save_bikash":
        bot.answer_callback_query(
            call.id,
            "পেমেন্ট পদ্ধতি নিশ্চিত করা হয়েছে!",
            show_alert=False
        )

        bot.send_message(
            user_id,
            "*✅ আপনার পেমেন্ট পদ্ধতি সফলভাবে নিশ্চিত করা হয়েছে!*",
            parse_mode="Markdown"
        )


def save_bikash_number(message):
    user_id = str(
        message.chat.id
    )

    username = (
        message.from_user.username
        or message.from_user.first_name
    )

    save_user_to_sheet(
        user_id,
        username
    )

    bikash_num = clean_value(
        message.text
    )

    if (
        not bikash_num.isdigit()
        or len(bikash_num) < 11
    ):
        return bot.reply_to(
            message,
            "*❌ ভুল নম্বর! সঠিক ১১ ডিজিটের বিকাশ নম্বর দিন.*",
            parse_mode="Markdown"
        )

    try:
        s_data = (
            sheet_all_number.get_all_values()
        )

        if not s_data:
            sheet_all_number.append_row(
                [
                    "User ID",
                    "Username",
                    "Bikash Number"
                ]
            )

            s_data = [
                [
                    "User ID",
                    "Username",
                    "Bikash Number"
                ]
            ]

        row_index = -1

        for idx, row in enumerate(
            s_data[1:],
            start=2
        ):
            if (
                len(row) > 0
                and clean_value(row[0]) == user_id
            ):
                row_index = idx
                break

        formatted_bikash = (
            f"'{bikash_num}"
        )

        if row_index != -1:
            sheet_all_number.update_cell(
                row_index,
                3,
                formatted_bikash
            )

            sheet_all_number.update_cell(
                row_index,
                2,
                username
            )
        else:
            sheet_all_number.append_row(
                [
                    user_id,
                    username,
                    formatted_bikash
                ]
            )

        bot.reply_to(
            message,
            f"*✅ আপনার বিকাশ নম্বর ({bikash_num}) সফলভাবে সেভ করা হয়েছে.*",
            parse_mode="Markdown"
        )

    except Exception as e:
        bot.reply_to(
            message,
            f"*❌ সমস্যা: {e}*",
            parse_mode="Markdown"
        )


@bot.message_handler(
    func=lambda msg:
    msg.chat.id == ADMIN_ID
    and msg.text == "ℹ️ Check Status"
)
def check_status(message):
    rate, date_val = (
        get_admin_settings()
    )

    bot.send_message(
        ADMIN_ID,
        f"*🟢 স্ট্যাটাস: {get_bot_status()}\n"
        f"💰 রেট: {rate}\n"
        f"📅 তারিখ: {date_val}*",
        parse_mode="Markdown"
    )


# ============================================================
# RUN
# ============================================================
if __name__ == "__main__":
    print(
        "Bot is running with Railway environment "
        "variables and 'all users' Google Sheet tracking..."
    )

    while True:
        try:
            bot.infinity_polling(
                timeout=20,
                long_polling_timeout=15
            )
        except Exception as e:
            print(
                f"Error: {e}. Retrying..."
            )
            time.sleep(5)
