import re
from printEmail import print_message_details
from getMailList import get_gmail_service, list_messages
from keywordFilter import filter_messages_by_keywords, load_keywords

if __name__ == '__main__':
    service = get_gmail_service()
    messages = list_messages(service)
    keywords = load_keywords()
    if not keywords:
        print("No keywords loaded")
        exit(1)

    pattern = re.compile(r"|".join(re.escape(k) for k in keywords), re.IGNORECASE)

    matching_id_list = filter_messages_by_keywords(service, pattern)
    for msg_id in matching_id_list:
        print_message_details(service, msg_id)
    
    print(f"Found {len(matching_id_list)} matching messages.")

