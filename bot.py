import os
import logging
import json
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from anthropic import Anthropic
from dotenv import load_dotenv
import base64

# Load environment variables
load_dotenv()

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
ALLOWED_USERS = os.getenv('ALLOWED_USERS', '').split(',')
LOG_CONVERSATIONS = os.getenv('LOG_CONVERSATIONS', 'true').lower() == 'true'

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize Anthropic client
anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)

# Load knowledge base
def load_knowledge_base():
    """Load all markdown files from knowledge_base directory"""
    kb_files = [
        'FREE_Zakladni_mytí.md',
        'PREMIUM_01_Exterier_mytí_dekontaminace.md',
        'PREMIUM_02_Exterier_lesteni_opravy.md',
        'PREMIUM_03_Exterier_osetreni.md',
        'PREMIUM_04_Interier.md',
        'PREMIUM_05_Sezonni_priprava.md',
    ]
    
    knowledge_base = ""
    for filename in kb_files:
        try:
            filepath = os.path.join('knowledge_base', filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                knowledge_base += f"\n\n=== {filename} ===\n\n"
                knowledge_base += f.read()
        except FileNotFoundError:
            logger.warning(f"Knowledge base file not found: {filename}")
        except Exception as e:
            logger.error(f"Error loading {filename}: {e}")
    
    return knowledge_base

# Load AI instructions
def load_ai_instructions():
    """Load AI instructions from file"""
    try:
        with open('AI_INSTRUKCE.md', 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        logger.error("AI_INSTRUKCE.md not found!")
        return "Jsi profesionální autodetailing asistent s 17letou praxí."
    except Exception as e:
        logger.error(f"Error loading AI instructions: {e}")
        return "Jsi profesionální autodetailing asistent s 17letou praxí."

# Load resources
logger.info("Loading knowledge base...")
KNOWLEDGE_BASE = load_knowledge_base()
logger.info(f"Knowledge base loaded: {len(KNOWLEDGE_BASE)} characters")

logger.info("Loading AI instructions...")
AI_INSTRUCTIONS = load_ai_instructions()
logger.info("AI instructions loaded")

# Conversation logging
async def log_conversation(user_id, username, message, response):
    """Log conversation for analysis"""
    if not LOG_CONVERSATIONS:
        return
    
    try:
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'user_id': user_id,
            'username': username,
            'message': message,
            'response': response
        }
        
        log_dir = 'logs'
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, f"conversations_{datetime.now().strftime('%Y%m')}.jsonl")
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
    except Exception as e:
        logger.error(f"Error logging conversation: {e}")

# Check if user is allowed
def is_allowed_user(username):
    """Check if user is in allowed list"""
    if not ALLOWED_USERS or ALLOWED_USERS == ['']:
        return True  # If no restriction, allow all
    return username in ALLOWED_USERS

# Command handlers
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    username = update.effective_user.username
    
    if not is_allowed_user(username):
        await update.message.reply_text(
            "Omlouvám se, tato beta verze je dostupná pouze pro vybrané testery.\n\n"
            "Pokud máte zájem o přístup, kontaktujte prosím autora."
        )
        return
    
    welcome_message = (
        "👋 Vítejte v AutoDetailing Asistentovi!\n\n"
        "Jsem tu, abych vám pomohl s péčí o vaše auto.\n\n"
        "**Co umím:**\n"
        "✅ Poradit s mytím, leštěním, ošetřením\n"
        "✅ Analyzovat fotky problémů na voze\n"
        "✅ Navrhnout postup krok za krokem\n"
        "✅ Varovat před chybami\n\n"
        "**Beta test:**\n"
        "Tato verze je v testování. Vaše zpětná vazba je neocenitelná!\n"
        "Konverzace zaznamenávám pro vylepšení služby.\n\n"
        "**Jak začít:**\n"
        "- Pošlete mi otázku o péči o auto\n"
        "- Nebo pošlete fotku problému\n\n"
        "Zkuste třeba: _\"Jak správně umýt auto?\"_"
    )
    
    await update.message.reply_text(welcome_message, parse_mode='Markdown')
    logger.info(f"User {username} started the bot")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_text = (
        "**Jak mě používat:**\n\n"
        "**1. Položte otázku:**\n"
        "_\"Jak naaplikovat vosk?\"_\n"
        "_\"Co je dekontaminace laku?\"_\n\n"
        "**2. Pošlete fotku:**\n"
        "Vyfoťte problém na autě a pošlete mi.\n"
        "Analyzuji ho a doporučím řešení.\n\n"
        "**3. Postupujte krok za krokem:**\n"
        "Ptejte se průběžně, pomohu vám celým procesem.\n\n"
        "**Příkazy:**\n"
        "/start - Úvodní zpráva\n"
        "/help - Tato nápověda\n"
        "/feedback - Pošlete zpětnou vazbu\n\n"
        "Mám otázku? Jen se ptejte! 🚗"
    )
    
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def feedback_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /feedback command"""
    feedback_text = (
        "**Děkuji za zájem o zpětnou vazbu!**\n\n"
        "Prosím napište mi:\n"
        "- Co fungovalo dobře?\n"
        "- Co by mohlo být lepší?\n"
        "- Chybělo vám nějaké téma?\n"
        "- Byla odpověď jasná a použitelná?\n\n"
        "Vaše poznámky mi velmi pomůžou vylepšit službu!"
    )
    
    await update.message.reply_text(feedback_text, parse_mode='Markdown')

# Message handlers
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages"""
    username = update.effective_user.username
    user_id = update.effective_user.id
    
    if not is_allowed_user(username):
        return
    
    message_text = update.message.text
    logger.info(f"Received message from {username}: {message_text[:50]}...")
    
    # Send typing indicator
    await update.message.chat.send_action("typing")
    
    try:
        # Call Claude API
        logger.info("Calling Claude API...")
        response = anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            system=f"{AI_INSTRUCTIONS}\n\n=== KNOWLEDGE BASE ===\n\n{KNOWLEDGE_BASE}",
            messages=[
                {"role": "user", "content": message_text}
            ]
        )
        
        bot_response = response.content[0].text
        logger.info(f"Claude response length: {len(bot_response)} chars")
        
        # Log conversation
        await log_conversation(user_id, username, message_text, bot_response)
        
        # Send response
        await update.message.reply_text(bot_response, parse_mode='Markdown')
        logger.info("Response sent successfully")
        
    except Exception as e:
        logger.error(f"Error processing message: {e}", exc_info=True)
        await update.message.reply_text(
            "Omlouvám se, něco se pokazilo. Zkuste to prosím znovu."
        )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle photo messages"""
    username = update.effective_user.username
    user_id = update.effective_user.id
    
    if not is_allowed_user(username):
        return
    
    # Get photo
    photo = update.message.photo[-1]  # Get highest resolution
    caption = update.message.caption or "Co je na této fotce?"
    logger.info(f"Received photo from {username} with caption: {caption}")
    
    # Send typing indicator
    await update.message.chat.send_action("typing")
    
    try:
        # Download photo
        logger.info("Downloading photo...")
        photo_file = await photo.get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        
        # Convert to base64
        photo_base64 = base64.b64encode(photo_bytes).decode('utf-8')
        logger.info(f"Photo converted to base64: {len(photo_base64)} chars")
        
        # Call Claude API with image
        logger.info("Calling Claude API with image...")
        response = anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            system=f"{AI_INSTRUCTIONS}\n\n=== KNOWLEDGE BASE ===\n\n{KNOWLEDGE_BASE}",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": photo_base64
                            }
                        },
                        {
                            "type": "text",
                            "text": caption
                        }
                    ]
                }
            ]
        )
        
        bot_response = response.content[0].text
        logger.info(f"Claude image analysis response: {len(bot_response)} chars")
        
        # Log conversation
        await log_conversation(user_id, username, f"[PHOTO] {caption}", bot_response)
        
        # Send response
        await update.message.reply_text(bot_response, parse_mode='Markdown')
        logger.info("Photo analysis response sent successfully")
        
    except Exception as e:
        logger.error(f"Error processing photo: {e}", exc_info=True)
        await update.message.reply_text(
            "Omlouvám se, něco se pokazilo při analýze fotky. Zkuste to prosím znovu."
        )

# Error handler
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    logger.error(f"Update {update} caused error {context.error}", exc_info=context.error)

# Main function
def main():
    """Start the bot"""
    logger.info("="*50)
    logger.info("Starting AutoDetailing Bot...")
    logger.info("="*50)
    
    # Check configuration
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not found in .env!")
        return
    
    if not ANTHROPIC_API_KEY:
        logger.error("ANTHROPIC_API_KEY not found in .env!")
        return
    
    logger.info(f"Token configured: {TELEGRAM_BOT_TOKEN[:10]}...")
    logger.info(f"API key configured: {ANTHROPIC_API_KEY[:20]}...")
    logger.info(f"Allowed users: {ALLOWED_USERS}")
    
    # Create application
    logger.info("Creating Telegram application...")
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Add handlers
    logger.info("Adding handlers...")
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("feedback", feedback_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_error_handler(error_handler)
    
    # Start bot
    logger.info("="*50)
    logger.info("✅ BOT IS RUNNING!")
    logger.info("="*50)
    logger.info("Press Ctrl+C to stop")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()


