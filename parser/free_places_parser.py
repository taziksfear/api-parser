import asyncio
import json
from playwright.async_api import async_playwright
import logging
from openai import OpenAI
import os
from dotenv import load_dotenv
import requests
import httpx

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Configure proxy for OpenAI
proxy_url = "http://45.140.143.77:18080"
proxies = {
    "http://": proxy_url,
    "https://": proxy_url
}

http_client = httpx.Client(proxies=proxies)

client = OpenAI(
    api_key=os.getenv("GPT_TOKEN"),
    http_client=http_client
)

CONFIG = {
    "Бакалавриат": {
        "url": "https://sfedu.ru/www/stat_pages22.show?p=ABT/N8206/P",
        "selectors": {
            "name": "td.column0.style18.s",
            "free_places": ["td.column3.style10.n", "td.column7.style10.n"],
            "city": "td.column11.style18.s"
        }
    },
    "Магистратура": {
        "url": "https://sfedu.ru/www/stat_pages22.show?p=ABT/N8207/P",
        "selectors": {
            "name": "td.column0.style8.s",
            "free_places": ["td.column3.style9.n", "td.column5.style11.n"],
            "city": "td.column8.style8.s"
        }
    },
    "Аспирантура": {
        "url": "https://sfedu.ru/www/stat_pages22.show?p=ABT/N8210/P",
        "selectors": {
            "name": "td.column0.style1.s",
            "free_places": ["td.column3.style3.n", "td.column5.style4.n"],
            "city": "td.column8.style2.s"
        }
    },
    "СПО": {
        "url": "https://sfedu.ru/www/stat_pages22.show?p=ABT/N8209/P",
        "selectors": {
            "name": "td.column1.style4.s",
            "free_places": ["td.column4.style5.n", "td.column5.style5.n"],
            "city": "td.column8.style5.s"
        }
    }
}

async def parse_page(category):
    config = CONFIG[category]
    results = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        try:
            await page.goto(config["url"], timeout=60000)
            await page.wait_for_selector('tbody[itemprop="priemKolTarget"]', timeout=30000)
            
            rows = await page.query_selector_all('tbody[itemprop="priemKolTarget"] tr')
            
            for row in rows:
                try:
                    city = await row.query_selector(config["selectors"]["city"])
                    city = await city.inner_text() if city else ""
                    
                    if "ростов-на-дону" not in city.lower():
                        continue
                        
                    name = await row.query_selector(config["selectors"]["name"])
                    name = await name.inner_text() if name else ""
                    
                    places = []
                    for selector in config["selectors"]["free_places"]:
                        element = await row.query_selector(selector)
                        if element:
                            places.append(await element.inner_text())
                    
                    results.append({
                        "category": category,
                        "name": name.strip(),
                        "free_places": " / ".join(places),
                        "city": city.strip()
                    })
                    
                except Exception as e:
                    logging.error(f"Error parsing row: {e}")
                    continue
                
        except Exception as e:
            logging.error(f"Error loading page {config['url']}: {e}")
            return []
        finally:
            await browser.close()
    
    return results

async def main():
    while True:
        all_data = []
        for category in CONFIG:
            try:
                data = await parse_page(category)
                all_data.extend(data)
                logging.info(f"Получено {len(data)} записей для {category}")
                await asyncio.sleep(5)
            except Exception as e:
                logging.error(f"Ошибка при обработке {category}: {e}")

        with open("free_places.json", "w", encoding="utf-8") as f:
            json.dump(all_data, f, ensure_ascii=False, indent=4)

        try:
            response = requests.post(
                "http://localhost:7270/free-places",
                json=all_data,
                proxies={"http": proxy_url, "https": proxy_url},
                timeout=10
            )
            response.raise_for_status()
            logging.info("Данные успешно отправлены на API")
        except Exception as e:
            logging.error(f"Ошибка отправки данных на API: {e}")

        await asyncio.sleep(172800) #это 2 дня если че

if __name__ == "__main__":
    asyncio.run(main())
