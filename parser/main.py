import asyncio
import json
from playwright.async_api import async_playwright
import os
import logging
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

API_URL = "http://127.0.0.1:7270/parsed-news"

async def scrape_news_page(news_id):
    url = f'https://sfedu.ru/press-center/news/{news_id}'
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url)

        try:
            await page.wait_for_timeout(5000)
            logging.info(await page.content())
        except Exception as e:
            logging.error(f"Error waiting for page to load: {e}")
            await browser.close()
            return {"error": f"Page load failed: {e}"}

        try:
            title = await page.inner_text('h1')
        except Exception as e:
            logging.error(f"Error extracting title: {e}")
            title = "Title not found"

        try:
            content_div = await page.query_selector('.content')
            content = await content_div.inner_text() if content_div else "Содержимое не найдено."
        except Exception as e:
            logging.error(f"Error extracting content: {e}")
            content = "Content not found"

        await browser.close()

        return {
            'actual_news': {
                'id': news_id,
                'title': title,
                'content': content
            }
        }

async def scrape_page(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url)

        try:
            await page.wait_for_selector('.content_wrapper', timeout=10000)
            content_wrapper = await page.query_selector('.content_wrapper')
            content = await content_wrapper.inner_text() if content_wrapper else "Содержимое не найдено."
        except Exception as e:
            logging.error(f"Error scraping page: {e}")
            content = "Content not found"
        finally:
            await browser.close()

        return content.replace('\n', ' ')

async def scrape_additional_pages(pages):
    results = {}
    for name, url in pages.items():
        content = await scrape_page(url)
        results[name] = {
            'content_wrapper': content
        }
    return results

def save_json_to_file(data, filename='parsed_news.json'):
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        logging.info(f"Данные сохранены в файл: {filename}")
    except IOError as e:
        logging.error(f"Error saving JSON to file: {e}")

def send_to_api(data):
    try:
        logging.info(f"Sending to API: {API_URL} with data: {data}")
        response = requests.post(API_URL, json=data)
        response.raise_for_status()
        logging.info(f"Данные успешно отправлены на API: {data}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Ошибка отправки данных на API: {e}")

async def main():
    news_id = 77181

    while True:
        news = await scrape_news_page(news_id)
        if news and 'error' not in news:
            if news['actual_news']['content'] == "Содержимое не найдено.":
                logging.warning(f"Новость с ID {news_id} не найдена. Ожидание следующей итерации...")
            else:
                logging.info(f"\nНовостные страницы:\nID: {news['actual_news']['id']}, Title: {news['actual_news']['title']}, Content: {news['actual_news']['content']}")
                send_to_api(news)
                news_id += 1 
        else:
            logging.warning(f'Не найдена страница новостей под ID: {news_id}')
            
        save_json_to_file(news)
        await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())