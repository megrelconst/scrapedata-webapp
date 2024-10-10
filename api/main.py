from fastapi import FastAPI
from scraper.scraper import scrape_domain, save_data_to_json
import json

app = FastAPI()

# Load default configuration from config.json
def load_config():
    with open("config.json", "r") as f:
        return json.load(f)

config = load_config()

# Root endpoint to handle requests to the base URL
@app.get("/")
def read_root():
    return {"message": "Welcome to the Scrape Data Web App! Use /scrape to start scraping."}

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
