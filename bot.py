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
LOG_CONVERSATIONS = os.getenv('LOG_CONVERSATIONS', 'true').lower() == 'true'

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize Anthropic client
anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)

# Knowledge base cache - load once at startup
KB_FILES = {
    'free': 'FREE_Zakladni_mytí.md',
    'mytí': 'PREMIUM_01_Exterier_mytí_dekontaminace.md',
    'leštění': 'PREMIUM_02_Exterier_lesteni_opravy.md',
    'ošetření': 'PREMIUM_03_Exterier_osetreni.md',
    'interiér': 'PREMIUM_04_Interier.md',
    'sezóna': 'PREMIUM_05_Sezonni_priprava.md',
}

KB_CACHE = {}

# Registered users storage (in-memory for beta)
REGISTERED_USERS = set()

def load_kb_file(filename):
    """Load a single knowledge base file"""
    try:
        filepath = os.path.join('knowledge_base', filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        logger.warning(f"KB file not found: {filename}")
        return ""
    except Exception as e:
        logger.error(f"Error loading {filename}: {e}")
        return ""

def load_ai_instructions():
    """Load AI instructions from file"""
    try:
        with open('AI_INSTRUKCE.md', 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        logger.error("AI_INSTRUKCE.md not found!")
        return "Jsi profesionální autodetailing asistent s 17letou praxí. Komunikuješ česky a pomáháš s péčí o auta."
    except Exception as e:
        logger.error(f"Error loading AI instructions: {e}")
        return "Jsi profesionální autodetailing asistent s 17letou praxí."

# Load resources at startup
logger.info("Loading knowledge base files...")
for key, filename in KB_FILES.items():
    KB_CACHE[key] = load_kb_file(filename)
    logger.info(f"Loaded {key}: {len(KB_CACHE[key])} chars")

logger.info("Loading AI instructions...")
AI_INSTRUCTIONS = load_ai_instructions()
logger.info(f"AI instructions loaded: {len(AI_INSTRUCTIONS)} chars")

def get_relevant_kb(user_message):
    """
    Select most relevant knowledge base based on keywords.
    Returns only ONE file to stay under token limits.
    """
    message_lower = user_message.lower()
    
    # Keyword mapping with priority (most specific first)
    keywords = {
        'leštění': ['leštění', 'lešti', 'leštit', 'škrában', 'hologram', 'opravu', 'pdr', 'disk', 'světl', 'odřen'],
        'ošetření': ['vosk', 'nano', 'keramik', 'ošetření', 'ochran', 'ppf', 'fólie', 'pneumatik', 'plast'],
        'interiér': ['interiér', 'sedačk', 'kůže', 'kobere', 'tepován', 'vysáv', 'volant', 'displej', 'klimatizac'],
        'sezóna': ['jaro', 'jar', 'zima', 'zim', 'nový vůz', 'používaný', 'sezón'],
        'mytí': ['dekontaminace', 'hmyz', 'smůla', 'mytí', 'myj', 'umýt', 'čištění'],
    }
    
    # Find best match
    for category, words in keywords.items():
        if any(word in message_lower for word in words):
            logger.info(f"Selected KB category: {category}")
            return KB_CACHE.get(category, KB_CACHE['free'])
    
    # Default to free topics
    logger.info("Selected KB category: free (default)")
    return KB_CACHE['free']

async def log_conversation(user_id, username, message, response):
    """Log conversation for analysis - with verbose Railway logging"""
    if not LOG_CONVERSATIONS:
        return
    
    try:
        # Log to Railway logs (stdout) - THIS IS THE MAIN LOG
        logger.info("="*60)
        logger.info("📝 CONVERSATION LOG")
        logger.info(f"👤 User: {username} (ID: {user_id})")
        logger.info(f"💬 Message: {message[:200]}{'...' if len(message) > 200 else ''}")
        logger.info(f"🤖 Response: {response[:200]}{'...' if len(response) > 200 else ''}")
        logger.info(f"📊 Stats: Message {len(message)} chars, Response {len(response)} chars")
        logger.info("="*60)
        
        # Also save to file (backup, will be lost on redeploy)
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'user_id': user_id,
            'username': username,
            'message': message,
            'response': response[:500]
        }
        
        log_dir = 'logs'
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, f"conversations_{datetime.now().strftime('%Y%m')}.jsonl")
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
            
        logger.info(f"✅ Conversation also saved to file: {log_file}")
        
    except Exception as e:
        logger.error(f"❌ Error logging conversation: {e}", exc_info=True)

def is_user_registered(user_id):
    """Check if user is registered"""
    return user_id in REGISTERED_USERS

def register_user(user_id):
    """Register a new user"""
    REGISTERED_USERS.add(user_id)
    logger.info(f"📋 Total registered users: {len(REGISTERED_USERS)}")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command with beta code registration"""
    username = update.effective_user.username
    user_id = update.effective_user.id
    
    # Check if user provided beta code
    if not context.args or len(context.args) == 0:
        # Check if already registered
        if is_user_registered(user_id):
            welcome_message = (
                "👋 Vítejte zpět!\n\n"
                "Jsem tu, abych vám pomohl s péčí o vaše auto.\n\n"
                "**Co umím:**\n"
                "✅ Poradit s mytím, leštěním, ošetřením\n"
                "✅ Analyzovat fotky problémů na voze\n"
                "✅ Navrhnout postup krok za krokem\n"
                "✅ Varovat před chybami\n\n"
                "Pošlete mi otázku nebo fotku problému!"
            )
            await update.message.reply_text(welcome_message, parse_mode='Markdown')
            logger.info(f"🔄 Returning user: {username} (ID: {user_id})")
            return
        
        # Not registered, ask for code
        await update.message.reply_text(
            "👋 Vítejte v AutoDetailing Asistentovi!\n\n"
            "Tento bot je momentálně v **beta testu**.\n\n"
            "**Pro aktivaci potřebujete registrační kód.**\n\n"
            "Napište: `/start VÁŠ_KÓD`\n\n"
            "❓ Nemáte kód?\n"
            "Kontaktujte autora pro přístup do beta testu.",
            parse_mode='Markdown'
        )
        logger.info(f"🚫 Unregistered user tried to start: {username} (ID: {user_id})")
        return
    
    # Get beta code from command
    beta_code = context.args[0].upper()
    
    # Valid beta codes
    valid_codes = ['MVBOT26', 'VIPYOU26']
    
    if beta_code not in valid_codes:
        await update.message.reply_text(
            "❌ **Neplatný registrační kód.**\n\n"
            "Zkontrolujte prosím překlepy nebo kontaktujte autora.\n\n"
            "Správný formát: `/start VÁŠ_KÓD`",
            parse_mode='Markdown'
        )
        logger.warning(f"⚠️ Invalid code attempt: {username} (ID: {user_id}) used: {beta_code}")
        return
    
    # Register user
    register_user(user_id)
    
    # Successful registration!
    logger.info(f"✅ NEW REGISTRATION: {username} (ID: {user_id}) with code: {beta_code}")
    
    # Welcome message
    welcome_message = (
        "🎉 **Registrace úspěšná!**\n\n"
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

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    user_id = update.effective_user.id
    
    if not is_user_registered(user_id):
        await update.message.reply_text(
            "⚠️ Pro použití bota se prosím nejdřív zaregistrujte pomocí `/start VÁŠ_KÓD`",
            parse_mode='Markdown'
        )
        return
    
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
    user_id = update.effective_user.id
    
    if not is_user_registered(user_id):
        await update.message.reply_text(
            "⚠️ Pro použití bota se prosím nejdřív zaregistrujte pomocí `/start VÁŠ_KÓD`",
            parse_mode='Markdown'
        )
        return
    
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

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages with smart KB selection"""
    username = update.effective_user.username
    user_id = update.effective_user.id
    
    if not is_user_registered(user_id):
        await update.message.reply_text(
            "⚠️ Pro použití bota se prosím nejdřív zaregistrujte pomocí `/start VÁŠ_KÓD`",
            parse_mode='Markdown'
        )
        logger.warning(f"⚠️ Unregistered user tried to message: {username} (ID: {user_id})")
        return
    
    message_text = update.message.text
    logger.info(f"📩 Received message from {username}: {message_text[:50]}...")
    
    await update.message.chat.send_action("typing")
    
    try:
        # Select relevant knowledge base
        relevant_kb = get_relevant_kb(message_text)
        
        # Strict enforcement prefix
        strict_prefix = """
⚠️ KRITICKÉ INSTRUKCE - DODRŽUJ PŘÍSNĚ:
1. Odpovídej POUZE na základě KNOWLEDGE BASE níže
2. NIKDY nepoužívej informace ze svého tréninku
3. NIKDY nevymýšlej termíny nebo postupy které nejsou v knowledge base
4. Pokud něco není v KB → řekni to upřímně
5. Nepoužívej fráze: "obecně se doporučuje", "profesionálové používají", "standardní postup je"
6. Používej POUZE terminologii z knowledge base (ne "compound", "cut and polish", atd.)
7. PŘED odpovědí zkontroluj: Je to SKUTEČNĚ v knowledge base?
"""
        
        # Call Claude API with only relevant KB
        logger.info("🤖 Calling Claude API...")
        response = anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            system=f"{strict_prefix}\n\n{AI_INSTRUCTIONS}\n\n=== KNOWLEDGE BASE ===\n\n{relevant_kb}",
            messages=[
                {"role": "user", "content": message_text}
            ]
        )
        
        bot_response = response.content[0].text
        logger.info(f"✅ Claude response: {len(bot_response)} chars")
        
        # Log conversation
        await log_conversation(user_id, username, message_text, bot_response)
        
        # Send response
        await update.message.reply_text(bot_response, parse_mode='Markdown')
        logger.info("📤 Response sent successfully")
        
    except Exception as e:
        logger.error(f"❌ Error processing message: {e}", exc_info=True)
        
        error_msg = "Omlouvám se, něco se pokazilo."
        
        if "429" in str(e) or "rate" in str(e).lower():
            error_msg = "Momentálně je vysoká zátěž. Zkuste to prosím za chvíli."
        elif "401" in str(e) or "authentication" in str(e).lower():
            error_msg = "Problém s API klíčem. Kontaktujte prosím správce."
        
        await update.message.reply_text(error_msg)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle photo messages with optimized KB"""
    username = update.effective_user.username
    user_id = update.effective_user.id
    
    if not is_user_registered(user_id):
        await update.message.reply_text(
            "⚠️ Pro použití bota se prosím nejdřív zaregistrujte pomocí `/start VÁŠ_KÓD`",
            parse_mode='Markdown'
        )
        logger.warning(f"⚠️ Unregistered user tried to send photo: {username} (ID: {user_id})")
        return
    
    photo = update.message.photo[-1]
    caption = update.message.caption or "Analyzuj tuto fotku auta a poraď mi co s tím."
    logger.info(f"📸 Received photo from {username}")
    
    await update.message.chat.send_action("typing")
    
    try:
        # Download photo
        logger.info("⬇️ Downloading photo...")
        photo_file = await photo.get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        
        # Convert to base64
        photo_base64 = base64.b64encode(photo_bytes).decode('utf-8')
        logger.info(f"📦 Photo size: {len(photo_base64)} chars")
        
        # Use minimal KB for photos (just FREE topics to save tokens)
        minimal_kb = KB_CACHE.get('free', '')
        
        # Strict enforcement prefix
        strict_prefix = """
⚠️ KRITICKÉ INSTRUKCE - DODRŽUJ PŘÍSNĚ:
1. Odpovídej POUZE na základě KNOWLEDGE BASE níže
2. NIKDY nepoužívej informace ze svého tréninku
3. NIKDY nevymýšlej termíny nebo postupy které nejsou v knowledge base
4. Pokud něco není v KB → řekni to upřímně
5. Používej POUZE terminologii z knowledge base
"""
        
        # Call Claude API with image
        logger.info("🤖 Calling Claude API with image...")
        response = anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            system=f"{strict_prefix}\n\n{AI_INSTRUCTIONS}\n\n=== KNOWLEDGE BASE ===\n\n{minimal_kb}",
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
        logger.info(f"✅ Photo analysis complete: {len(bot_response)} chars")
        
        # Log conversation
        await log_conversation(user_id, username, f"[PHOTO] {caption}", bot_response)
        
        # Send response
        await update.message.reply_text(bot_response, parse_mode='Markdown')
        logger.info("📤 Photo analysis sent successfully")
        
    except Exception as e:
        logger.error(f"❌ Error processing photo: {e}", exc_info=True)
        
        error_msg = "Omlouvám se, něco se pokazilo při analýze fotky."
        
        if "429" in str(e) or "rate" in str(e).lower():
            error_msg = "Momentálně je vysoká zátěž. Zkuste to prosím za chvíli."
        elif "image" in str(e).lower() or "size" in str(e).lower():
            error_msg = "Fotka je příliš velká. Zkuste menší rozlišení."
        
        await update.message.reply_text(error_msg)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    logger.error(f"❌ Update {update} caused error {context.error}", exc_info=context.error)

def main():
    """Start the bot"""
    logger.info("="*60)
    logger.info("🚀 Starting AutoDetailing Bot...")
    logger.info("="*60)
    
    if not TELEGRAM_BOT_TOKEN:
        logger.error("❌ TELEGRAM_BOT_TOKEN not found!")
        return
    
    if not ANTHROPIC_API_KEY:
        logger.error("❌ ANTHROPIC_API_KEY not found!")
        return
    
    logger.info(f"🔑 Token: {TELEGRAM_BOT_TOKEN[:10]}...")
    logger.info(f"🔑 API key: {ANTHROPIC_API_KEY[:20]}...")
    logger.info(f"📚 KB files loaded: {len(KB_CACHE)}")
    logger.info(f"🎫 Beta codes: MVBOT26, VIPYOU26")
    logger.info(f"📝 Conversation logging: {'ENABLED' if LOG_CONVERSATIONS else 'DISABLED'}")
    
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("feedback", feedback_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_error_handler(error_handler)
    
    logger.info("="*60)
    logger.info("✅ BOT IS RUNNING!")
    logger.info("="*60)
    logger.info("💡 Logs are being saved to Railway stdout")
    logger.info("💡 View logs in Railway: Deployments → View Logs")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()