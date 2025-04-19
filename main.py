from telegram import Update, Document
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters
from pathlib import Path
import os, shutil, tarfile, subprocess

# === CONFIG ===
TOKEN = '7875349256:AAHj-gMmqAdc_RJXNIgCQJ00tj95jupyclQ'
MODE = {"type": "strings"}

# === PATCH LOGIC ===
PATCH_STRINGS = [
    b"api_key", b"apikey", b"API_KEY", b"apiKey_web", b"udid", b"UDID",
    b"auth_token", b"client_secret", b"access_token", b"jwt_secret",
    b"firebase_api_key", b"google_api_key", b"googleMapsAPIKey"
]

def patch_binary(data):
    patched = 0
    for target in PATCH_STRINGS:
        if target in data:
            replacement = b"noop_" + b"_" * max(0, len(target) - 5)
            data = data.replace(target, replacement[:len(target)])
            patched += 1
    return data, patched

def patch_dylibs_in_dir(root_dir):
    patched = 0
    for dirpath, _, filenames in os.walk(root_dir):
        for name in filenames:
            if name.endswith('.dylib'):
                path = os.path.join(dirpath, name)
                data = Path(path).read_bytes()
                new_data, count = patch_binary(data)
                Path(path).write_bytes(new_data)
                patched += count
    return patched

# === .deb UTILS ===
def extract_deb(deb_path, extract_dir):
    os.makedirs(extract_dir, exist_ok=True)
    shutil.copy(deb_path, os.path.join(extract_dir, 'package.deb'))
    subprocess.run(['ar', 'x', 'package.deb'], cwd=extract_dir)
    return (
        os.path.join(extract_dir, 'control.tar.gz'),
        os.path.join(extract_dir, 'data.tar.gz')
    )

def extract_tar(tar_path, out_dir):
    with tarfile.open(tar_path, 'r:*') as tar:
        tar.extractall(path=out_dir)

def repack_tar(tar_path, source_dir):
    with tarfile.open(tar_path, 'w:gz') as tar:
        tar.add(source_dir, arcname='.')

def rebuild_deb(out_path, extract_dir):
    parts = ['debian-binary', 'control.tar.gz', 'data.tar.gz']
    with open(out_path, 'wb') as outfile:
        for part in parts:
            with open(os.path.join(extract_dir, part), 'rb') as f:
                outfile.write(f.read())

# === CLEANUP ===
def cleanup(*paths):
    for path in paths:
        if os.path.isfile(path):
            os.remove(path)
        elif os.path.isdir(path):
            shutil.rmtree(path)

# === HANDLERS ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Gửi mình file .dylib hoặc .deb, mình sẽ xử lý giúp bạn!")

async def mode_strings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    MODE["type"] = "strings"
    await update.message.reply_text("✅ Đang ở chế độ vá chuỗi.")

async def mode_logic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    MODE["type"] = "logic"
    await update.message.reply_text("✅ Chế độ patch logic (WIP).")

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc: Document = update.message.document
    filename = doc.file_name
    file_path = f"./{filename}"

    await update.message.reply_text("⚙️ Đang xử lý...")

    file = await context.bot.get_file(doc.file_id)
    await file.download_to_drive(file_path)

    if filename.endswith(".dylib"):
        data = Path(file_path).read_bytes()
        new_data, patched_count = patch_binary(data)
        patched_path = f"patched_{filename}"
        Path(patched_path).write_bytes(new_data)

        await update.message.reply_document(document=open(patched_path, "rb"))
        await update.message.reply_text(f"✅ Đã vá {patched_count} chuỗi trong file .dylib!")

        cleanup(file_path, patched_path)

    elif filename.endswith(".deb"):
        work_dir = "./work"
        os.makedirs(work_dir, exist_ok=True)
        control_tar, data_tar = extract_deb(file_path, work_dir)

        control_dir = os.path.join(work_dir, 'control')
        data_dir = os.path.join(work_dir, 'data')
        os.makedirs(control_dir, exist_ok=True)
        os.makedirs(data_dir, exist_ok=True)

        extract_tar(control_tar, control_dir)
        extract_tar(data_tar, data_dir)

        patched_count = patch_dylibs_in_dir(data_dir)

        repack_tar(os.path.join(work_dir, 'control.tar.gz'), control_dir)
        repack_tar(os.path.join(work_dir, 'data.tar.gz'), data_dir)

        patched_deb = f"patched_{filename}"
        rebuild_deb(patched_deb, work_dir)

        await update.message.reply_document(document=open(patched_deb, "rb"))
        await update.message.reply_text(f"✅ Vá thành công {patched_count} chuỗi trong file .deb!")

        cleanup(work_dir, file_path, patched_deb)

    else:
        await update.message.reply_text("❌ Chỉ hỗ trợ file .dylib hoặc .deb.")

# === MAIN ===
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("mode_strings", mode_strings))
    app.add_handler(CommandHandler("mode_logic", mode_logic))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    app.run_polling()

if __name__ == "__main__":
    main()
