import re
import emoji

def clean_text(text):
    # Remove URLs
    text = re.sub(r'http\S+|www.\S+', '', text)

    # Remove emojis
    text = emoji.replace_emoji(text, "")

    # nostr URIs
    nostr_pattern = r'(@|nostr:)(npub|nprofile|note|nevent|naddr)[a-zA-Z0-9]+'
    text = re.sub(nostr_pattern, '', text)

    # Trim extra spaces
    text = re.sub(r'[^\S\r\n]+', ' ', text).strip()

    # Shorten to max 300 chars
    text = text[:300]
    
    return text
