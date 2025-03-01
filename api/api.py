from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
import httpx
import time
from datetime import datetime
from typing import Dict, List
import logging
import json
import os
from collections import defaultdict
from httpx import Client, Proxy
import requests

proxy_url = "http://45.140.143.77:18080"
proxies = {
    "http": proxy_url,
    "https": proxy_url
}

GPT_TOKEN = os.getenv("GPT_API_KEY")
GPT_URL = "https://api.openai.com/v1/chat/completions"

app = FastAPI()
MAX_HISTORY_LENGTH = 100

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

dialog_history = defaultdict(list)

HISTORY_FILE = "dialog_history.json"

def load_dialog_history():
    if not os.path.exists(HISTORY_FILE):
        logging.info("Файл истории диалогов не найден. Создан пустой файл.")
        with open(HISTORY_FILE, "w", encoding="utf-8") as file:
            json.dump({}, file, ensure_ascii=False, indent=4)
        return {}

    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as file:
            history = json.load(file)
            for user_id, messages in history.items():
                dialog_history[int(user_id)] = [
                    (datetime.fromisoformat(msg[0]), msg[1]) for msg in messages
                ]
        logging.info("История диалогов загружена из файла.")
        return history
    except json.JSONDecodeError as e:
        logging.error(f"Ошибка при загрузке истории диалогов из файла: {e}")
        return {}
    except Exception as e:
        logging.error(f"Неизвестная ошибка при загрузке истории диалогов: {e}")
        return {}

def save_dialog_history():
    history_to_save = {
        user_id: [(msg[0].isoformat(), msg[1]) for msg in messages]
        for user_id, messages in dialog_history.items()
    }
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as file:
            json.dump(history_to_save, file, ensure_ascii=False, indent=4)
        logging.info("История диалогов сохранена в файл.")
    except Exception as e:
        logging.error(f"Ошибка при сохранении истории диалогов в файл: {e}")

load_dialog_history()

@app.post("/generate-response")
async def generate_response(data: dict = Body(...)):
    user_id = data.get("user_id")
    message = data.get("message")
    
    if not user_id or not message:
        raise HTTPException(status_code=400, detail="user_id и message обязательны")

    context_data = load_dialog_history()
    current_time = datetime.now()
    dialog_history[user_id].append((current_time, f"Пользователь: {message}"))

    if len(dialog_history[user_id]) > MAX_HISTORY_LENGTH:
        dialog_history[user_id].pop(0)
        logging.info(f"История диалога для пользователя {user_id} обрезана до {MAX_HISTORY_LENGTH} сообщений.")

    context = "\n".join([msg for _, msg in dialog_history[user_id]])

    prompt = f"""
        Контекст предыдущих сообщений:
        {context}
        Вопрос пользователя: {message}
        """    

    start_time = time.time()

    response_text = "Произошла ошибка при обработке запроса."

    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {GPT_TOKEN}"
        }

        data = {
            "model": "gpt-4",
            "messages": [
                {"role": "system", "content": "Ты Умный ассистент Южного федерального университета. в твои задачи входит полная поддержка студентов в процессе освоения. Отвечай кратко, но емко. в твою базу знаний входит информация с открытых источников и материалы, которые могут быть полезны студентам."},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 200,
            "temperature": 0.7
        }
        response = requests.post(GPT_URL, headers=headers, json=data, proxies=proxies)
        response.raise_for_status()
        result = response.json()
        response_text = result["choices"][0]["message"]["content"].strip()
        print("Ответ от GPT-4:", response_text)
    except requests.exceptions.HTTPError as e:
        print(f"Ошибка HTTP: {e}")
    except Exception as e:
        print(f"Ошибка: {e}")

    dialog_history[user_id].append((current_time, f"Ассистент: {response_text}"))
    # Убираем префикс "Ассистент:" из ответа, если он есть
    if response_text.startswith("Ассистент:"):
        response_text = response_text.replace("Ассистент:", "").strip()

    save_dialog_history()

    return {"response": response_text}

@app.post("/parsed-news")
async def parsed_news(data: dict = Body(...)):
    try:
        with open("parsed_news.json", "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=4)
        return {"message": "Parsed news saved successfully."}
    except Exception as e:
        logging.error(f"Error saving parsed news: {e}")
        raise HTTPException(status_code=500, detail="Failed to save parsed news")
    
@app.post("/free-places")
async def save_free_places(data: dict = Body(...)):
    # Сохраняйте данные в файл или БД
    with open("free_places.json", "w") as f:
        json.dump(data, f)
    return {"status": "success"}



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=7270)
