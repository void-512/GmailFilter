from getMailList import get_gmail_service, list_messages
from filters import filter_messages_by_keywords, load_from_json
from insightDB import read_matches, display_matches
from config import DB_PATH

if __name__ == '__main__':
    service = get_gmail_service()
    messages = list_messages(service)

    include_all_compiled, exclude_any_compiled, order_id_patterns = load_from_json("keywords.json")
    if not include_all_compiled and not exclude_any_compiled:
        print("No keywords loaded")
        exit(1)

    filter_messages_by_keywords(service, include_all_compiled, exclude_any_compiled, order_id_patterns)

    matches = read_matches()
    display_matches(matches)