# TELEGRAM BOT - SETUP GUIDE

## 📋 PŘEHLED

Tento návod vás provede kompletním nastavením Telegram bota pro autodetailing asistenta.

**Co bot umí:**
- ✅ Odpovídá na otázky o péči o auto
- ✅ Analyzuje fotky aut (škrábance, fleky, poškození...)
- ✅ Poskytuje návody krok za krokem
- ✅ Varuje před chybami
- ✅ Zaznamenává konverzace pro analýzu

---

## 🛠️ CO BUDETE POTŘEBOVAT

### 1. Účty
- ✅ Telegram účet (zdarma)
- ✅ Anthropic API klíč (Claude) - https://console.anthropic.com
- ✅ Hosting (Railway/Render/Heroku) - má free tier

### 2. Technické
- ✅ Python 3.9+ 
- ✅ Základní znalost command line
- ✅ Git (volitelné, ale usnadní to)

### 3. Knowledge Base soubory
- ✅ FREE_Zakladni_mytí.md
- ✅ PREMIUM_01_Exterier_mytí_dekontaminace.md
- ✅ PREMIUM_02_Exterier_lesteni_opravy.md
- ✅ PREMIUM_03_Exterier_osetreni.md
- ✅ PREMIUM_04_Interier.md
- ✅ PREMIUM_05_Sezonni_priprava.md
- ✅ AI_INSTRUKCE.md

---

## 🚀 KROK 1: VYTVOŘENÍ TELEGRAM BOTA

### A) Najděte BotFather

1. Otevřete Telegram
2. Vyhledejte: **@BotFather**
3. Napište: `/start`

### B) Vytvořte nového bota

```
/newbot
```

**BotFather se zeptá:**
```
Alright, a new bot. How are we going to call it? 
Please choose a name for your bot.
```

**Odpovězte (příklad):**
```
AutoDetailing Asistent Beta
```

**BotFather se zeptá na username:**
```
Good. Now let's choose a username for your bot. 
It must end in `bot`.
```

**Odpovězte (příklad):**
```
autodetailing_beta_bot
```

### C) Uložte si API token

BotFather vám pošle zprávu:
```
Done! Congratulations on your new bot...

Use this token to access the HTTP API:
1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ1234567890

For a description of the Bot API, see this page: ...
```

⚠️ **Uložte si ten token! Budete ho potřebovat.**

---

## 🔑 KROK 2: ZÍSKÁNÍ CLAUDE API KLÍČE

### A) Zaregistrujte se na Anthropic

1. Jděte na: https://console.anthropic.com
2. Vytvořte účet
3. Přidejte platební metodu (budete muset)

### B) Vytvořte API klíč

1. V console klikněte na **API Keys**
2. Klikněte **Create Key**
3. Pojmenujte: "Telegram Bot"
4. Zkopírujte klíč

⚠️ **Uložte si klíč! Už ho neuvidíte.**

**Cena:** ~$3-15/měsíc pro beta test (20-30 uživatelů)

---

## 💻 KROK 3: STAŽENÍ A NASTAVENÍ KÓDU

### A) Naklonujte repository (nebo stáhněte ZIP)

```bash
git clone https://github.com/VÁŠ_USERNAME/autodetailing-bot.git
cd autodetailing-bot
```

**Nebo vytvořte novou složku:**
```bash
mkdir autodetailing-bot
cd autodetailing-bot
```

### B) Vytvořte Python virtual environment

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# NEBO
venv\Scripts\activate  # Windows
```

### C) Nainstalujte dependencies

Vytvořte `requirements.txt`:
```
python-telegram-bot==20.7
anthropic==0.18.1
python-dotenv==1.0.0
aiofiles==23.2.1
```

Nainstalujte:
```bash
pip install -r requirements.txt
```

### D) Vytvořte `.env` soubor

```bash
# .env
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ1234567890
ANTHROPIC_API_KEY=sk-ant-api03-abcd...
ALLOWED_USERS=user1,user2,user3  # Telegram usernames beta testerů
LOG_CONVERSATIONS=true
```

⚠️ **NIKDY NEcommitujte .env do Gitu!**

Přidejte do `.gitignore`:
```
.env
venv/
__pycache__/
*.pyc
logs/
```

---

## 📝 KROK 4: HLAVNÍ BOT KÓD

Vytvořte `bot.py`:

```python
import os
import logging
import json
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from anthropic import Anthropic
from dotenv import load_dotenv
import aiofiles

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
            with open(f'knowledge_base/{filename}', 'r', encoding='utf-8') as f:
                knowledge_base += f"\n\n=== {filename} ===\n\n"
                knowledge_base += f.read()
        except FileNotFoundError:
            logger.warning(f"Knowledge base file not found: {filename}")
    
    return knowledge_base

# Load AI instructions
def load_ai_instructions():
    """Load AI instructions from file"""
    try:
        with open('AI_INSTRUKCE.md', 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        logger.error("AI_INSTRUKCE.md not found!")
        return "Jsi autodetailing asistent."

KNOWLEDGE_BASE = load_knowledge_base()
AI_INSTRUCTIONS = load_ai_instructions()

# Conversation logging
async def log_conversation(user_id, username, message, response):
    """Log conversation for analysis"""
    if not LOG_CONVERSATIONS:
        return
    
    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'user_id': user_id,
        'username': username,
        'message': message,
        'response': response
    }
    
    log_dir = 'logs'
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = f"{log_dir}/conversations_{datetime.now().strftime('%Y%m')}.jsonl"
    async with aiofiles.open(log_file, 'a', encoding='utf-8') as f:
        await f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')

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
            "Omlouv  m se, tato beta verze je dostupná pouze pro vybrané testery.\n\n"
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
    
    # Send typing indicator
    await update.message.chat.send_action("typing")
    
    try:
        # Call Claude API
        response = anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            system=f"{AI_INSTRUCTIONS}\n\n=== KNOWLEDGE BASE ===\n\n{KNOWLEDGE_BASE}",
            messages=[
                {"role": "user", "content": message_text}
            ]
        )
        
        bot_response = response.content[0].text
        
        # Log conversation
        await log_conversation(user_id, username, message_text, bot_response)
        
        # Send response
        await update.message.reply_text(bot_response, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error processing message: {e}")
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
    
    # Send typing indicator
    await update.message.chat.send_action("typing")
    
    try:
        # Download photo
        photo_file = await photo.get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        
        # Convert to base64
        import base64
        photo_base64 = base64.b64encode(photo_bytes).decode('utf-8')
        
        # Call Claude API with image
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
        
        # Log conversation
        await log_conversation(user_id, username, f"[PHOTO] {caption}", bot_response)
        
        # Send response
        await update.message.reply_text(bot_response, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error processing photo: {e}")
        await update.message.reply_text(
            "Omlouvám se, něco se pokazilo při analýze fotky. Zkuste to prosím znovu."
        )

# Main function
def main():
    """Start the bot"""
    # Create application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("feedback", feedback_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    
    # Start bot
    logger.info("Bot started!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
```

---

## 📁 KROK 5: STRUKTURA SLOŽEK

Vytvořte tuto strukturu:

```
autodetailing-bot/
├── bot.py
├── requirements.txt
├── .env
├── .gitignore
├── AI_INSTRUKCE.md
├── knowledge_base/
│   ├── FREE_Zakladni_mytí.md
│   ├── PREMIUM_01_Exterier_mytí_dekontaminace.md
│   ├── PREMIUM_02_Exterier_lesteni_opravy.md
│   ├── PREMIUM_03_Exterier_osetreni.md
│   ├── PREMIUM_04_Interier.md
│   └── PREMIUM_05_Sezonni_priprava.md
└── logs/ (vytvoří se automaticky)
```

---

## 🧪 KROK 6: LOKÁLNÍ TESTOVÁNÍ

```bash
# Aktivujte virtual environment
source venv/bin/activate  # Linux/Mac
# nebo
venv\Scripts\activate  # Windows

# Spusťte bota
python bot.py
```

**Výstup by měl být:**
```
2024-03-01 20:00:00 - __main__ - INFO - Bot started!
```

**Otevřete Telegram a:**
1. Najděte svého bota (username který jste vytvořili)
2. Napište `/start`
3. Zkuste poslat otázku: "Jak umýt auto?"
4. Zkuste poslat fotku

---

## ☁️ KROK 7: HOSTING (DEPLOY)

Bot musí běžet 24/7. Doporučuji **Railway** (má free tier).

### A) Zaregistrujte se na Railway

1. Jděte na: https://railway.app
2. Sign up (GitHub účtem)

### B) Vytvořte nový projekt

1. Klikněte "New Project"
2. Vyberte "Deploy from GitHub repo"
3. Připojte svůj repository

### C) Nastavte environment variables

V Railway projektu:
1. Klikněte na "Variables"
2. Přidejte:
   - `TELEGRAM_BOT_TOKEN`
   - `ANTHROPIC_API_KEY`
   - `ALLOWED_USERS`
   - `LOG_CONVERSATIONS`

### D) Přidejte Procfile

Vytvořte `Procfile` (bez přípony):
```
worker: python bot.py
```

### E) Deploy

```bash
git add .
git commit -m "Initial commit"
git push
```

Railway automaticky deployne! ✅

---

## 📊 KROK 8: MONITORING & ANALYTICS

### A) Sledování logů

**Lokálně:**
```bash
tail -f logs/conversations_202403.jsonl
```

**Na Railway:**
- Klikněte na projekt
- Záložka "Logs"

### B) Analýza konverzací

Vytvořte `analyze_logs.py`:

```python
import json
from collections import Counter
from datetime import datetime

def analyze_conversations(log_file):
    """Analyze conversation logs"""
    
    conversations = []
    with open(log_file, 'r', encoding='utf-8') as f:
        for line in f:
            conversations.append(json.loads(line))
    
    # Basic stats
    print(f"📊 STATISTIKY")
    print(f"Celkem konverzací: {len(conversations)}")
    print(f"Unikátních uživatelů: {len(set(c['username'] for c in conversations))}")
    
    # Top users
    user_counts = Counter(c['username'] for c in conversations)
    print(f"\n👥 TOP UŽIVATELÉ:")
    for user, count in user_counts.most_common(5):
        print(f"  {user}: {count} zpráv")
    
    # Common keywords
    all_messages = ' '.join(c['message'].lower() for c in conversations)
    keywords = ['leštění', 'vosk', 'mytí', 'čištění', 'nano', 'keramika', 'škrábance']
    keyword_counts = {kw: all_messages.count(kw) for kw in keywords}
    
    print(f"\n🔥 TOP TÉMATA:")
    for kw, count in sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {kw}: {count}x")

if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print("Usage: python analyze_logs.py logs/conversations_202403.jsonl")
    else:
        analyze_conversations(sys.argv[1])
```

Spusťte:
```bash
python analyze_logs.py logs/conversations_202403.jsonl
```

---

## 🎯 KROK 9: POZVÁNÍ BETA TESTERŮ

### A) Vytvořte pozvánku

```
🚗 **AutoDetailing Asistent - Beta Test**

Ahoj!

Vytvořil jsem AI asistenta pro péči o auta a hledám testery.

**Co umí:**
✅ Poradí s mytím, leštěním, ošetřením
✅ Analyzuje fotky problémů (škrábance, fleky...)
✅ Navrhne postup krok za krokem

**Beta test:**
🎁 Zdarma po dobu 1-2 měsíců
📊 Pomůžeš mi vylepšit službu

**Jak se zapojit:**
1. Přidej bota: @autodetailing_beta_bot
2. Napiš /start
3. Zkus ho otestovat!

Tvoje zpětná vazba je super důležitá. Děkuji! 🙏
```

### B) Přidejte uživatele do .env

```
ALLOWED_USERS=user1,user2,user3,...
```

Restartujte bota.

---

## 🐛 TROUBLESHOOTING

### Bot neodpovídá

**Zkontrolujte:**
```bash
# Lokálně
python bot.py
# Hledejte chyby v konzoli

# Na Railway
# Logs tab → hledejte ERROR
```

### Claude API chyby

**429 - Rate limit:**
- Příliš mnoho requestů
- Počkejte minutu

**401 - Unauthorized:**
- Špatný API klíč
- Zkontrolujte .env

### Fotky se neanalyzují

**Zkontrolujte:**
- Model podporuje vision: `claude-sonnet-4-20250514` ✅
- Base64 encoding funguje
- Photo size není moc velký (< 5MB)

---

## 💰 NÁKLADY

**Anthropic Claude API:**
- Input: $3 / 1M tokenů
- Output: $15 / 1M tokenů
- Průměrná konverzace: ~2000 tokenů
- **Odhad:** $3-15/měsíc pro 20-30 beta testerů

**Railway Hosting:**
- Free tier: 500 hodin/měsíc ($5 kredit)
- **Odhad:** Zdarma nebo $5/měsíc

**Celkem:** ~$5-20/měsíc během beta testu

---

## 📈 DALŠÍ KROKY

### Po beta testu:

1. **Analýza feedbacku**
   - Co fungovalo?
   - Co vylepšit?
   - Chybějící témata?

2. **Opravy a vylepšení**
   - Update knowledge base
   - Vylepšit AI instrukce
   - Přidat chybějící funkce

3. **Launch strategie**
   - Web interface?
   - Nebo pokračovat s Telegram?
   - Monetizace?

4. **Produktový katalog**
   - Přidat affiliate odkazy
   - Doporučení produktů

---

## ✅ CHECKLIST

Před spuštěním beta testu:

- [ ] Bot vytvořen v BotFather
- [ ] Claude API klíč získán
- [ ] Kód stažen/vytvořen
- [ ] Knowledge base nahrána
- [ ] .env správně nastaven
- [ ] Lokální test prošel
- [ ] Deployed na Railway/Render
- [ ] Beta testeri pozváni
- [ ] Monitoring nastaven

---

## 🆘 POMOC

Pokud něco nefunguje:
1. Zkontrolujte logs
2. Přečtěte si Troubleshooting sekci
3. Google error message
4. Kontaktujte mě

---

**Hodně štěstí s beta testem! 🚀**
