# main.py
from db import process_query
from chatgpt import summarize_cases
import openai
from config import OPENAI_API_KEY
openai.api_key = OPENAI_API_KEY

def display_more_details(case):
    """
    Prints additional details about a case.
    """
    print("\n--- More Details ---")
    print(f"Version ID: {case.get('version_id')}")
    print(f"Type: {case.get('type')}")
    print(f"Jurisdiction: {case.get('jurisdiction')}")
    print(f"Source: {case.get('source')}")
    print(f"Citation: {case.get('citation')}")
    print(f"URL: {case.get('url')}")
    print("Full Text:")
    print(case.get("text"))
    print("--- End Details ---\n")

def main():
    # Variables to hold the last query's results and the current index.
    last_query_results = None
    current_idx = 0

    while True:
        user_input = input("Enter a query, type 'next' for the next case, 'more' for the details or 'exit' to quit: ").strip()
        if user_input.lower() == "exit":
            break
        elif user_input.lower() == "next":
            # If the user types 'next', check if we have a previous query's results.
            if last_query_results is None:
                print("No previous query found. Please enter a new query first.")
                continue
            if current_idx >= len(last_query_results):
                print("No more cases available for the current query. Please enter a new query.")
                last_query_results = None
                current_idx = 0
                continue
            case, similarity = last_query_results[current_idx]
        elif user_input.lower() =="more":
            display_more_details(case)
        # If the user types "next", the outer loop will use that in the next iteration."
        else:
            # New query entered: process and reset the results.
            last_query_results,query_processed = process_query(user_input)
            current_idx = 0
            if not query_processed:
                print("Daily search limit reached. Please try again tomorrow.")
                break
            if not last_query_results:
                print("No cases matched your query sufficiently.")
                continue
            case, similarity = last_query_results[current_idx]

        # If the case is a list, extract the first dictionary.
        if isinstance(case, list):
            if len(case) > 0:
                case = case[0]
            else:
                print("Encountered an empty case list. Skipping.")
                continue

        # Generate summary for the current case.
        summary = summarize_cases(case, similarity)
        print(f"\nSummary for Case {current_idx + 1} (Similarity: {similarity:.2f}):")
        print(summary)
        current_idx += 1


    print("Goodbye!")

if __name__ == "__main__":
    main()
