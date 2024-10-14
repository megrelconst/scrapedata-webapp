from fastapi import FastAPI
from pydantic import BaseModel
from scraper.scraper import scrape_domain, save_data_to_json
import json
import os
import logging
from openai import OpenAI
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

# Create an instance of FastAPI
app = FastAPI()

# Set up OpenAI client
client = OpenAI()

# Set up logging
logging.basicConfig(level=logging.INFO)

# Load default configuration from config.json
def load_config():
    with open("config.json", "r") as f:
        return json.load(f)

config = load_config()

# Function to generate embeddings using OpenAI API
def generate_embedding(text):
    response = client.embeddings.create(
        input=text,
        model="text-embedding-ada-002"
    )
    return response['data'][0]['embedding']

# Root endpoint to handle requests to the base URL
@app.get("/")
def read_root():
    return {"message": "Welcome to the Scrape Data Web App! Use /scrape to start scraping."}

# Endpoint to scrape data
@app.get("/scrape")
def scrape(max_depth: int = 2):
    # Use the default URL from the configuration file
    url = config.get("default_url")
    
    # Ensure a URL is provided in the configuration file
    if not url:
        return {"error": "No default URL specified in config.json"}

    # Scrape the domain
    data = scrape_domain(url, max_depth=max_depth)

    # Deduplicate and organize data
    unique_data = {
        "titles": set(),
        "headings": set(),
        "paragraphs": set(),
        "links": set()
    }

    for item in data:
        if 'title' in item and item['title']:
            unique_data['titles'].add(item['title'])
        if 'headings' in item:
            for heading_list in item['headings'].values():
                if isinstance(heading_list, list):
                    unique_data['headings'].update(heading_list)
                elif isinstance(heading_list, str):
                    unique_data['headings'].add(heading_list)
        if 'paragraphs' in item:
            unique_data['paragraphs'].update(item['paragraphs'])
        if 'links' in item:
            unique_data['links'].update(item['links'])

    # Convert sets back to lists for JSON serialization
    for key in unique_data:
        unique_data[key] = list(unique_data[key])

    # Generate embeddings for the paragraphs, titles, and headings
    embedded_data = []
    for key in ["titles", "headings", "paragraphs"]:
        for text in unique_data[key]:
            embedding = generate_embedding(text)
            embedded_data.append({
                "text": text,
                "embedding": embedding,
                "type": key
            })

    # Save deduplicated, organized, and embedded data
    with open("embedded_data.json", "w", encoding="utf-8") as f:
        json.dump(embedded_data, f, ensure_ascii=False, indent=4)
    
    return {"message": "Scraping completed successfully.", "pages_scraped": len(data)}

# Request model for query
class QueryRequest(BaseModel):
    prompt: str

# Function to find the most relevant context based on query embeddings
def get_relevant_context(embedded_data, query_embedding, top_k=3):
    # Extract embeddings and texts
    embeddings = [np.array(item['embedding']) for item in embedded_data]
    texts = [item['text'] for item in embedded_data]

    # Calculate cosine similarity between query embedding and stored embeddings
    similarities = cosine_similarity([query_embedding], embeddings)[0]

    # Get top_k most similar texts
    top_indices = np.argsort(similarities)[-top_k:]
    relevant_context = "\n".join([texts[i] for i in reversed(top_indices)])

    return relevant_context

# Endpoint to query OpenAI with a prompt
@app.post("/query")
def query_openai(request: QueryRequest):
    try:
        # Load embedded data
        try:
            with open("embedded_data.json", "r", encoding="utf-8") as f:
                embedded_data = json.load(f)
        except FileNotFoundError:
            return {"error": "No embedded data found."}

        # Generate embedding for the query
        query_embedding = generate_embedding(request.prompt)

        # Get relevant context using embeddings
        context = get_relevant_context(embedded_data, query_embedding)

        # Update the prompt to include the relevant context
        messages = [
            {"role": "system", "content": "You are a helpful assistant. Use only the given context to answer questions, and if the information is not available, say 'I don't have the information in my dataset.'"},
            {"role": "user", "content": f"Context: {context}\n\nQuestion: {request.prompt}"}
        ]

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages
        )
        logging.info(f"OpenAI Response: {completion}")  # Log the full response from OpenAI for debugging
        return {"response": completion.choices[0].message.content}
    except KeyError as e:
        logging.error(f"KeyError accessing response content: {str(e)}")
        return {"error": f"KeyError: {str(e)}"}
    except Exception as e:
        logging.error(f"Exception occurred: {str(e)}")
        return {"error": str(e)}

# Endpoint to get the scraped data
@app.get("/scraped-data")
def get_scraped_data():
    try:
        with open("scraped_data.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except FileNotFoundError:
        return {"error": "No scraped data found."}

# Temporary endpoint to check if the API key is set
@app.get("/check-api-key")
def check_api_key():
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        return {"message": "API key is set correctly."}
    else:
        return {"error": "API key is not set."}
