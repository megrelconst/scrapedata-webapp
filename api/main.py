from fastapi import FastAPI
from pydantic import BaseModel
from scraper.scraper import scrape_domain, save_data_to_json
import json
import os
import logging
from openai import OpenAI

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
    save_data_to_json(data)
    
    return {"message": "Scraping completed successfully.", "pages_scraped": len(data)}

# Request model for query
class QueryRequest(BaseModel):
    prompt: str

# Function to extract relevant context from scraped data based on the query
def get_relevant_context(scraped_data, prompt):
    context = ""
    for item in scraped_data:
        # Search titles, headings, and paragraphs for relevance to the prompt
        if prompt.lower() in item.get('title', '').lower():
            context += f"Title: {item['title']}\n"
        if any(prompt.lower() in heading.lower() for heading in item.get('headings', {}).values()):
            context += f"Headings: {item['headings']}\n"
        relevant_paragraphs = [p for p in item.get('paragraphs', []) if prompt.lower() in p.lower()]
        if relevant_paragraphs:
            context += f"Paragraphs: {relevant_paragraphs}\n"
        # Limit the size of the context to avoid exceeding token limits
        if len(context) > 2000:
            break
    return context if context else "No relevant context found."

# Endpoint to query OpenAI with a prompt based on scraped data
@app.post("/query")
def query_openai(request: QueryRequest):
    try:
        # Load scraped data
        try:
            with open("scraped_data.json", "r", encoding="utf-8") as f:
                scraped_data = json.load(f)
        except FileNotFoundError:
            return {"error": "No scraped data found."}

        # Get relevant context from the scraped data
        context = get_relevant_context(scraped_data, request.prompt)

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
        return {"response": completion.choices[0].message}

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