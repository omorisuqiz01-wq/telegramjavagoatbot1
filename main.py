import os
import telebot
from flask import Flask, request
from apify_client import ApifyClient
import threading
import json
import openai # Imported as requested

# ==========================================
# 1. SETUP ENVIRONMENT VARIABLES
# ==========================================
BOT_TOKEN = os.environ.get('BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')
HF_TOKEN = os.environ.get('HF_TOCKEN', 'YOUR_HF_TOKEN_HERE') # As requested
APIFY_TOKEN = os.environ.get('APIFY_TOKEN', 'YOUR_APIFY_TOKEN_HERE')

# Initialize Telegram Bot
bot = telebot.TeleBot(BOT_TOKEN)

# Initialize Flask App (for Render Webhook hosting)
app = Flask(__name__)

# ==========================================
# 2. APIFY ACTOR FUNCTION
# ==========================================
def fetch_terabox_data(url, chat_id):
    """
    Runs the Apify actor and sends the results back to the user.
    """
    try:
        # Initialize the ApifyClient
        client = ApifyClient(APIFY_TOKEN)

        # Prepare Actor input
        run_input = {
            "links": [url],
            "proxyConfiguration": {
                "useApifyProxy": True,
                "apifyProxyGroups": ["RESIDENTIAL"]
            }
        }

        # Run the Actor and wait for it to finish
        bot.send_message(chat_id, "⏳ Task started! Waiting for Apify to process the link...")
        run = client.actor("igview-owner/terabox-fast-video-downloader").call(run_input=run_input)

        # Fetch Actor results from the run's dataset
        dataset_items = client.dataset(run["defaultDatasetId"]).list_items().items
        
        if not dataset_items:
            bot.send_message(chat_id, "❌ No results found in the dataset.")
            return

        # Send results to Telegram
        for item in dataset_items:
            # Formatting the dictionary into a readable format
            formatted_item = json.dumps(item, indent=2, ensure_ascii=False)
            
            # Telegram message length limit is 4096, slicing if it exceeds
            if len(formatted_item) > 4000:
                formatted_item = formatted_item[:4000] + "\n...[Truncated]"
                
            bot.send_message(chat_id, f"✅ **Result:**\n```json\n{formatted_item}\n```", parse_mode="Markdown")

    except Exception as e:
        bot.send_message(chat_id, f"⚠️ An error occurred during extraction:\n{str(e)}")


# ==========================================
# 3. TELEGRAM BOT HANDLERS
# ==========================================
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "Hello! Send me a Terabox link, and I will download the info for you using Apify.")

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    text = message.text
    
    # Check if a link is sent (Basic validation)
    if "http" in text:
        bot.reply_to(message, "Processing your link...")
        # Using a Thread so the Telegram Webhook doesn't timeout while Apify is running!
        threading.Thread(target=fetch_terabox_data, args=(text, message.chat.id)).start()
    else:
        bot.reply_to(message, "Please send a valid HTTP link.")

# ==========================================
# 4. FLASK ROUTES (WEBHOOK SETUP)
# ==========================================
@app.route('/' + BOT_TOKEN, methods=['POST'])
def getMessage():
    bot.process_new_updates([telebot.types.Update.de_json(request.stream.read().decode("utf-8"))])
    return "!", 200

@app.route("/")
def webhook():
    # Render requires a web server to bind to a port, this route keeps Render happy.
    bot.remove_webhook()
    
    # If deploying on Render, you should dynamically get the Render URL
    # Replace 'YOUR-RENDER-APP-URL' below with your actual Render URL after creation if RENDER_EXTERNAL_URL fails
    render_url = os.environ.get('RENDER_EXTERNAL_URL', '')
    if render_url:
        bot.set_webhook(url=f"{render_url}/{BOT_TOKEN}")
        return "Webhook set up successfully!", 200
    else:
        return "Bot is running, but Render external URL is not set. Webhook not active.", 200

# ==========================================
# 5. START SERVER
# ==========================================
if __name__ == "__main__":
    # Get port from Render environment, default to 10000
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
