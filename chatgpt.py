#  chatgpt.py
import openai
from config import OPENAI_API_KEY

openai.api_key = OPENAI_API_KEY

def summarize_cases(case, similarity=None):
    """
    Summarizes a single case document using ChatGPT.
    The case should be a dictionary containing at least a 'text' field.
    Optionally, a similarity score can be provided.
    """
    context = f"Case Text:\n{case.get('text')}"
    if similarity is not None:
        context += f"\nSimilarity: {similarity:.2f}"
    
    prompt = f"Summarize the following case and highlight the top insights:\n\n{context}\n\nSummary:"
    
    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=500
    )
    summary = response.choices[0].message.content.strip()
    return summary

def rephrase_query(query, avoid_list):
    """
    Rephrases the input query using ChatGPT to generate a more effective version,
    while avoiding any phrases provided in avoid_list.
    """
    avoid_text = ""
    if avoid_list:
        avoid_text = "\nAvoid using any of the following phrases: " + ", ".join(avoid_list)
    
    prompt = (
        f"Rephrase the following query to improve its clarity and effectiveness:\n\n"
        f"Query: {query}\n"
        f"{avoid_text}\n\n"
        f"Rephrased Query:"
    )
    
    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=50
    )
    rephrased_query = response.choices[0].message.content.strip()
    return rephrased_query
