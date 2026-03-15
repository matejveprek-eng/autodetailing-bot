import os
import logging
import json
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.request import HTTPXRequest
from anthropic import Anthropic
from dotenv import load_dotenv
import base64

# Load environment variables
load_dotenv()

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
LOG_CONVERSATIONS = os.getenv('LOG_CONVERSATIONS', 'true').lower() == 'true'

# Setup logging - clean and readable
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Suppress noisy loggers - NO MORE SPAM!
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
logging.getLogger("telegram.ext").setLevel(logging.WARNING)
logging.getLogger("anthropic").setLevel(logging.WARNING)

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
        logger.warning(f"⚠️ KB file not found: {filename}")
        return ""
    except Exception as e:
        logger.error(f"❌ Error loading {filename}: {e}")
        return ""

def load_ai_instructions():
    """Load AI instructions from file"""
    try:
        with open('AI_INSTRUKCE.md', 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        logger.error("❌ AI_INSTRUKCE.md not found!")
        return "Jsi profesionální autodetailing asistent s 17letou praxí. Komunikuješ česky a pomáháš s péčí o auta."
    except Exception as e:
        logger.error(f"❌ Error loading AI instructions: {e}")
        return "Jsi profesionální autodetailing asistent s 17letou praxí."

# Load resources at startup
logger.info("📚 Loading knowledge base files...")
for key, filename in KB_FILES.items():
    KB_CACHE[key] = load_kb_file(filename)
    logger.info(f"   ✅ {key}: {len(KB_CACHE[key])} chars")

logger.info("📋 Loading AI instructions...")
AI_INSTRUCTIONS = load_ai_instructions()
logger.info(f"   ✅ AI instructions: {len(AI_INSTRUCTIONS)} chars")

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
        'interiér': ['interiér', 'sedačk', 'kůže', 'kobere', 'tepován', 'vysáv', 'volant', 'displej', 'klimatizac', 'zápach', 'smrd', 'kouř', 'kouřák', 'kouření'],
        'sezóna': ['jaro', 'jar', 'zima', 'zim', 'nový vůz', 'používaný', 'sezón'],
        'mytí': ['dekontaminace', 'hmyz', 'smůla', 'mytí', 'myj', 'umýt', 'čištění', 'lepidlo', 'samolepka', 'nálepka', 'lakovna', 'lakovn'],
    }
    
    # Find best match
    for category, words in keywords.items():
        if any(word in message_lower for word in words):
            logger.info(f"🎯 Selected KB: {category}")
            return KB_CACHE.get(category, KB_CACHE['free'])
    
    # Default to free topics
    logger.info("🎯 Selected KB: free (default)")
    return KB_CACHE['free']

async def log_conversation(user_id, username, message, response):
    """Log conversation for analysis - SUPER VISIBLE VERSION"""
    if not LOG_CONVERSATIONS:
        return
    
    try:
        # MEGA VISIBLE LOG BLOCK
        logger.info("")
        logger.info("━" * 80)
        logger.info("━" * 80)
        logger.info("                    📝 NOVÁ KONVERZACE 📝")
        logger.info("━" * 80)
        logger.info(f"👤 UŽIVATEL: {username}")
        logger.info(f"🆔 USER ID: {user_id}")
        logger.info("─" * 80)
        logger.info(f"💬 DOTAZ:")
        logger.info(f"   {message[:300]}{'...' if len(message) > 300 else ''}")
        logger.info("─" * 80)
        logger.info(f"🤖 ODPOVĚĎ:")
        logger.info(f"   {response[:300]}{'...' if len(response) > 300 else ''}")
        logger.info("─" * 80)
        logger.info(f"📊 STATISTIKY: Dotaz {len(message)} znaků | Odpověď {len(response)} znaků")
        logger.info("━" * 80)
        logger.info("━" * 80)
        logger.info("")
        
        # Also save to file (backup)
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
        logger.error(f"❌ CHYBA PŘI LOGOVÁNÍ: {e}", exc_info=True)

def is_user_registered(user_id):
    """Check if user is registered"""
    return user_id in REGISTERED_USERS

def register_user(user_id):
    """Register a new user"""
    REGISTERED_USERS.add(user_id)
    logger.info(f"📋 Celkem registrovaných uživatelů: {len(REGISTERED_USERS)}")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command with beta code registration"""
    username = update.effective_user.username
    user_id = update.effective_user.id
    
    # Check if user provided beta code
    if not context.args or len(context.args) == 0:
        # Check if already registered
        if is_user_registered(user_id):
            welcome_back_message = (
                "👋 Vítejte zpět!\n\n"
                "**Zkuste třeba:**\n"
                "• Jak správně umýt auto?\n"
                "• Jak odstranit škrábance z laku?\n"
                "• Co dělat se zápachem v interiéru?\n"
                "• Jak aplikovat vosk nebo keramiku?\n"
                "• Pošlete fotku problému na voze\n\n"
                "Nebo se zeptejte na cokoliv! 🚗"
            )
            await update.message.reply_text(welcome_back_message, parse_mode='Markdown')
            logger.info(f"🔄 Vracející se user: {username} (ID: {user_id})")
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
        logger.info(f"🚫 Neregistrovaný user: {username} (ID: {user_id})")
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
        logger.warning(f"⚠️ Neplatný kód: {username} (ID: {user_id}) použil: {beta_code}")
        return
    
    # Register user
    register_user(user_id)
    
    # Successful registration!
    logger.info("")
    logger.info("🎉" * 40)
    logger.info(f"🎉 NOVÁ REGISTRACE! User: {username} | ID: {user_id} | Kód: {beta_code}")
    logger.info("🎉" * 40)
    logger.info("")
    
    # NEW IMPROVED Welcome message with starter questions
    welcome_message = (
        "🎉 **Registrace úspěšná!**\n\n"
        "Jsem tu, abych vám pomohl s péčí o vaše auto!\n\n"
        "**💡 Zkuste mě třeba:**\n\n"
        "**Základy:**\n"
        "• Jak správně umýt auto?\n"
        "• Jak mám vyčistit interiér?\n\n"
        "**Problémy:**\n"
        "• Jak odstranit škrábance?\n"
        "• Co dělat se zápachem v autě?\n"
        "• Jak vyčistit fleky na sedačkách?\n\n"
        "**Pokročilé:**\n"
        "• Jak aplikovat vosk nebo keramiku?\n"
        "• Jak funguje strojní leštění?\n\n"
        "**📸 Nebo:**\n"
        "Prostě mi pošlete **fotku problému** a já vám poradím!\n\n"
        "Napište cokoliv co vás zajímá 👇"
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
        logger.warning(f"⚠️ Neregistrovaný user zkusil poslat zprávu: {username} (ID: {user_id})")
        return
    
    message_text = update.message.text
    logger.info(f"📩 Zpráva od {username}: {message_text[:80]}{'...' if len(message_text) > 80 else ''}")
    
    await update.message.chat.send_action("typing")
    
    try:
        # Select relevant knowledge base
        relevant_kb = get_relevant_kb(message_text)
        
        # NEW STRICT PREFIX - Anti-hallucination with transparency
        strict_prefix = """
⚠️ KRITICKÉ INSTRUKCE - PŘEČTI POZORNĚ:

TVOJE KNOWLEDGE BASE obsahuje OVĚŘENÉ postupy z PRAXE.
NA INTERNETU je spousta BULLSHIT návodů které v praxi nefungují.

PROTO:

1. POUŽÍVEJ POUZE informace z KNOWLEDGE BASE níže
   - Pokud je postup v KB → vysvětli ho DETAILNĚ
   - Pokud NENÍ v KB → PŘIZNEJ TO upřímně

2. NIKDY nevymýšlej:
   - Produkty které nejsou v KB (ne "kabinový filtr", "čistič s knotem", atd.)
   - Kroky které nejsou v KB
   - "Vylepšování" KB vlastními znalostmi

3. BUĎ TRANSPARENTNÍ:
   - Když něco NENÍ v KB → řekni: "Toto v návodech nemám přesně popsané"
   - Nabídni: "Můžu zkusit poradit obecně, ale nebude to ověřené praxí"

4. BUĎ VÝŘEČNÝ ale POCTIVÝ:
   - ✅ Detailní vysvětlení
   - ✅ Zdůvodnění PROČ
   - ✅ Praktické tipy z KB
   - ✅ Varování před chybami
   - ❌ Bullshit z internetu
   - ❌ Vymýšlení

5. NIKDY nepoužívej fráze:
   - "obecně se doporučuje"
   - "profesionálové používají"
   - "standardní postup je"
   → Toto jsou signály že vymýšlíš!

KONTROLA PŘED ODPOVĚDÍ:
✓ Je KAŽDÝ produkt/krok z KB?
✓ Pokud něco nevím → přiznávám to?
✓ Nepoužívám bullshit z internetu?

Pamatuj: LEPŠÍ říct "nevím" než uvést uživatele v omyl!
"""
        
        # Call Claude API with only relevant KB
        logger.info("🤖 Volám Claude API...")
        response = anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            system=f"{strict_prefix}\n\n{AI_INSTRUCTIONS}\n\n=== KNOWLEDGE BASE ===\n\n{relevant_kb}",
            messages=[
                {"role": "user", "content": message_text}
            ]
        )
        
        bot_response = response.content[0].text
        logger.info(f"✅ Claude odpověděl: {len(bot_response)} znaků")
        
        # Log conversation
        await log_conversation(user_id, username, message_text, bot_response)
        
        # Send response
        await update.message.reply_text(bot_response, parse_mode='Markdown')
        logger.info("📤 Odpověď odeslána")
        
    except Exception as e:
        logger.error(f"❌ CHYBA při zpracování zprávy: {e}", exc_info=True)
        
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
        logger.warning(f"⚠️ Neregistrovaný user zkusil poslat fotku: {username} (ID: {user_id})")
        return
    
    photo = update.message.photo[-1]
    caption = update.message.caption or "Analyzuj tuto fotku auta a poraď mi co s tím."
    logger.info(f"📸 Fotka od {username}")
    
    await update.message.chat.send_action("typing")
    
    try:
        # Download photo
        logger.info("⬇️ Stahuji fotku...")
        photo_file = await photo.get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        
        # Convert to base64
        photo_base64 = base64.b64encode(photo_bytes).decode('utf-8')
        logger.info(f"📦 Fotka: {len(photo_base64)} znaků base64")
        
        # Use minimal KB for photos (just FREE topics to save tokens)
        minimal_kb = KB_CACHE.get('free', '')
        
        # Strict enforcement prefix for photos
        strict_prefix = """
⚠️ KRITICKÉ INSTRUKCE:
1. Odpovídej POUZE na základě KNOWLEDGE BASE níže
2. NIKDY nepoužívej informace ze svého tréninku
3. NIKDY nevymýšlej termíny nebo postupy které nejsou v knowledge base
4. Pokud něco není v KB → řekni to upřímně
5. Používej POUZE terminologii z knowledge base
"""
        
        # Call Claude API with image
        logger.info("🤖 Volám Claude API s fotkou...")
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
        logger.info(f"✅ Analýza fotky hotová: {len(bot_response)} znaků")
        
        # Log conversation
        await log_conversation(user_id, username, f"[FOTKA] {caption}", bot_response)
        
        # Send response
        await update.message.reply_text(bot_response, parse_mode='Markdown')
        logger.info("📤 Analýza fotky odeslána")
        
    except Exception as e:
        logger.error(f"❌ CHYBA při analýze fotky: {e}", exc_info=True)
        
        error_msg = "Omlouvám se, něco se pokazilo při analýze fotky."
        
        if "429" in str(e) or "rate" in str(e).lower():
            error_msg = "Momentálně je vysoká zátěž. Zkuste to prosím za chvíli."
        elif "image" in str(e).lower() or "size" in str(e).lower():
            error_msg = "Fotka je příliš velká. Zkuste menší rozlišení."
        
        await update.message.reply_text(error_msg)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    logger.error(f"❌ ERROR: {context.error}", exc_info=context.error)

def main():
    """Start the bot"""
    print("=" * 100)
    print("🚀🚀🚀 BOT STARTING 🚀🚀🚀")
    print("=" * 100)
    
    logger.info("")
    logger.info("=" * 80)
    logger.info("🚀 SPOUŠTÍM AUTODETAILING BOTA...")
    logger.info("=" * 80)
    
    if not TELEGRAM_BOT_TOKEN:
        print("❌❌❌ TELEGRAM_BOT_TOKEN CHYBÍ! ❌❌❌")
        logger.error("❌ TELEGRAM_BOT_TOKEN nenalezen!")
        return
    
    if not ANTHROPIC_API_KEY:
        print("❌❌❌ ANTHROPIC_API_KEY CHYBÍ! ❌❌❌")
        logger.error("❌ ANTHROPIC_API_KEY nenalezen!")
        return
    
    print(f"✅ Telegram token: {TELEGRAM_BOT_TOKEN[:10]}...")
    print(f"✅ Anthropic API key: {ANTHROPIC_API_KEY[:20]}...")
    
    logger.info(f"🔑 Telegram token: {TELEGRAM_BOT_TOKEN[:10]}...")
    logger.info(f"🔑 Anthropic API key: {ANTHROPIC_API_KEY[:20]}...")
    logger.info(f"📚 Načteno KB souborů: {len(KB_CACHE)}")
    logger.info(f"🎫 Beta kódy: MVBOT26, VIPYOU26")
    logger.info(f"📝 Logování konverzací: {'ZAPNUTO' if LOG_CONVERSATIONS else 'VYPNUTO'}")
    
    print("🔧 Creating application with longer timeout for Railway...")
    
    # Create request with longer timeout for Railway network
    request = HTTPXRequest(
        connection_pool_size=8,
        connect_timeout=30.0,
        read_timeout=30.0,
        write_timeout=30.0,
        pool_timeout=30.0
    )
    
    application = Application.builder()\
        .token(TELEGRAM_BOT_TOKEN)\
        .request(request)\
        .build()
    
    print("📝 Adding handlers...")
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("feedback", feedback_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_error_handler(error_handler)
    
    logger.info("=" * 80)
    logger.info("✅ BOT BĚŽÍ!")
    logger.info("=" * 80)
    logger.info("💡 Logy jsou v Railway → Deployments → View Logs")
    logger.info("💡 httpx spam je VYPNUTÝ - vidíte jen důležité události")
    logger.info("")
    
    print("=" * 100)
    print("🎉🎉🎉 BOT JE RUNNING - POLLING STARTED 🎉🎉🎉")
    print("=" * 100)
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
