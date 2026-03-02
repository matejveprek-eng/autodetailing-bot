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
        "- Nebo pošlete fot
