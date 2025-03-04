import json
from DatabaseHandler import DatabaseHandler
from openai_service import ChatGPT
from config import COLLECTION

def display_more_details(case):
    """
    Prints additional details about a case, excluding '_id' and 'map_id'.
    """
    print("\n--- More Details ---")
    for key, value in case.items():
        if key not in ["_id", "map_id"]:
            print(f"{key}: {value}")
    print("--- End Details ---\n")


def main():
    # List available configurations from COLLECTION.
    keys = list(COLLECTION.keys())
    print("Available configurations:")
    for i, key in enumerate(keys, start=1):
        doc_type = COLLECTION[key].get("document_type", "Unknown")
        print(f"{i}: {doc_type}")
    
    # Let the user choose a configuration by number.
    try:
        selected_num = int(input("Enter configuration number: ").strip())
        if selected_num < 1 or selected_num > len(keys):
            raise ValueError("Selection out of range")
    except Exception as e:
        print("Invalid configuration number. Defaulting to 1.")
        selected_num = 1

    config = COLLECTION[keys[selected_num - 1]]
    print(f"Using configuration: {config['document_type']}")
    print("Selected configuration details:")
    print(json.dumps(config, indent=4))
    
    # Instantiate the DatabaseHandler and ChatGPT service.
    db_handler = DatabaseHandler(config)
    chat_service = ChatGPT(db_handler.db)
    
    last_query_results = None
    current_idx = 0
    
    while True:
        user_input = input("Enter a query, 'next' for next result, 'more' for details, or 'exit': ").strip().lower()
        if user_input == "exit":
            break
        elif user_input == "next":
            if not last_query_results:
                print("No previous query found. Please enter a new query first.")
                continue
            if current_idx >= len(last_query_results):
                print("No more results for this query. Enter a new query.")
                continue
            case, similarity = last_query_results[current_idx]
            current_idx += 1
        elif user_input == "more":
            if not last_query_results or current_idx == 0:
                print("No result available for more details. Enter a query first.")
                continue
            # Show details for the last returned case (previous index).
            case, similarity = last_query_results[current_idx - 1]
            display_more_details(case)
            continue
        else:
            # Process a new query.
            print("Processing query...")
            last_query_results, processed = db_handler.process_query(user_input)
            if not processed:
                print("Daily search limit reached. Exiting.")
                break
            if not last_query_results:
                print("No results found. Try another query.")
                continue
            current_idx = 0
            case, similarity = last_query_results[current_idx]
            current_idx += 1

        # Generate and display a summary for the current case.
        summary = chat_service.summarize_cases(case)
        print(f"\nSummary (Similarity: {similarity:.2f}):\n{summary}\n")
    db_handler.close() # Close the connection
    print("Goodbye!")

if __name__ == "__main__":
    main()
