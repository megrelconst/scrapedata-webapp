from fastapi import FastAPI
from pydantic import BaseModel
from scraper.scraper import scrape_domain, save_data_to_json
import json
import os
import openai
import logging
from openai import OpenAI

client = OpenAI()

# Create an instance of FastAPI
app = FastAPI()

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

# Endpoint to query OpenAI with a prompt
@app.post("/query")
def query_openai(request: QueryRequest):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",  # Updated model based on the latest OpenAI documentation
            messages=[
                {"role": "user", "content": request.prompt}
            ],
            max_tokens=100,
            temperature=0.7  # Added temperature parameter
        )
        logging.info(f"OpenAI Response: {response}")  # Log the full response from OpenAI for debugging
        # Corrected the way the response is accessed based on the latest OpenAI response structure
        return {"response": response['choices'][0]['message']['content'].strip()}
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
    api_key = openai.api_key
    if api_key:
        return {"message": "API key is set correctly."}
    else:
        return {"error": "API key is not set."}