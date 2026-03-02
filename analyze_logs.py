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
