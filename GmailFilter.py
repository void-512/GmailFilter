import re
from printEmail import print_message_details
from getMailList import get_gmail_service, list_messages
from keywordFilter import filter_messages_by_keywords, load_keywords, filter_messages_by_keywords_v2
from keywordLoader import load_from_json

def get_matching_messages(service):
    messages = list_messages(service)
    keywords = load_keywords()
    if not keywords:
        print("No keywords loaded")
        return []

    pattern = re.compile(r"|".join(re.escape(k) for k in keywords), re.IGNORECASE)

    matching_id_list = filter_messages_by_keywords(service, pattern)
    return matching_id_list

def get_matching_messages_v2(service):
    messages = list_messages(service)

    include_all_compiled, exclude_any_compiled = load_from_json("keywords.json")
    if not include_all_compiled and not exclude_any_compiled:
        print("No keywords loaded")
        return []

    matching_id_list = filter_messages_by_keywords_v2(service, include_all_compiled, exclude_any_compiled)

    return matching_id_list

if __name__ == '__main__':
    service = get_gmail_service()
    matching_id_list = get_matching_messages_v2(service)

    for msg_id in matching_id_list:
        print_message_details(service, msg_id)
    
    print(f"Found {len(matching_id_list)} matching messages.")
