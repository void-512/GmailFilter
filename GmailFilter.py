from getMailList import get_gmail_service, list_messages
from printEmail import print_message_details, display_full_message
from keywordFilter import filter_messages_by_keywords, load_from_json

def get_matching_messages(service):
    messages = list_messages(service)

    include_all_compiled, exclude_any_compiled = load_from_json("keywords.json")
    if not include_all_compiled and not exclude_any_compiled:
        print("No keywords loaded")
        return []

    matching_id_list = filter_messages_by_keywords(service, include_all_compiled, exclude_any_compiled)

    return matching_id_list

if __name__ == '__main__':
    service = get_gmail_service()
    matching_id_list = get_matching_messages(service)

    #for msg_id in matching_id_list:
        # print_message_details(service, msg_id)
    display_full_message(service, matching_id_list[1]) 
    print(f"Found {len(matching_id_list)} matching messages.")
