from bs4 import BeautifulSoup
import requests
import json
import os
from openai import OpenAI
from datetime import datetime

# Set up OpenAI client
client = OpenAI()

# Load configuration from config.json
def load_config():
    with open("config.json", "r") as f:
        return json.load(f)

# Function to generate embeddings using OpenAI API
def generate_embedding(text):
    response = client.embeddings.create(
        input=text,
        model="text-embedding-3-small"
    )
    return response['data'][0]['embedding']

# Scrape a single website page
def scrape_website(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # Extracting structured data
        data = {
            "url": url,
            "timestamp": datetime.now().isoformat(),  # Add timestamp to record when the page was scraped
            "title": soup.title.string if soup.title else "",
            "headings": {
                "h1": [h1.get_text(strip=True) for h1 in soup.find_all('h1')],
                "h2": [h2.get_text(strip=True) for h2 in soup.find_all('h2')],
                "h3": [h3.get_text(strip=True) for h3 in soup.find_all('h3')],
            },
            "paragraphs": [p.get_text(strip=True) for p in soup.find_all('p')],
            "lists": {
                "unordered": [[li.get_text(strip=True) for li in ul.find_all('li')] for ul in soup.find_all('ul')],
                "ordered": [[li.get_text(strip=True) for li in ol.find_all('li')] for ol in soup.find_all('ol')],
            },
            "links": [a['href'] for a in soup.find_all('a', href=True) if a['href'].startswith("http")],
        }

        return data

    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

# Scrape the entire domain up to a certain depth
def scrape_domain(domain_url, max_depth=None):
    config = load_config()
    if max_depth is None:
        max_depth = config.get("max_depth", 2)  # Load max_depth from config.json, default to 2 if not specified

    visited = set()
    to_visit = [domain_url]
    scraped_data = []
    embedded_data = []

    current_depth = 0

    while to_visit and current_depth < max_depth:
        next_to_visit = []
        for url in to_visit:
            if url not in visited:
                visited.add(url)
                data = scrape_website(url)
                if isinstance(data, dict) and "url" in data:
                    scraped_data.append(data)
                    # Collect more links to scrape
                    next_to_visit.extend(data.get("links", []))

                    # Generate embeddings for title, headings, paragraphs
                    if data.get("title"):
                        embedded_data.append({
                            "text": data["title"],
                            "embedding": generate_embedding(data["title"]),
                            "type": "title"
                        })
                    for heading_list in data.get("headings", {}).values():
                        for heading in heading_list:
                            embedded_data.append({
                                "text": heading,
                                "embedding": generate_embedding(heading),
                                "type": "heading"
                            })
                    for paragraph in data.get("paragraphs", []):
                        embedded_data.append({
                            "text": paragraph,
                            "embedding": generate_embedding(paragraph),
                            "type": "paragraph"
                        })

        to_visit = next_to_visit
        current_depth += 1

    # Save the scraped data and embeddings
    save_data_to_json(scraped_data)
    with open("embedded_data.json", "w", encoding="utf-8") as f:
        json.dump(embedded_data, f, ensure_ascii=False, indent=4)

    return scraped_data

# Save scraped data to JSON for querying
def save_data_to_json(data, filename="scraped_data.json"):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)