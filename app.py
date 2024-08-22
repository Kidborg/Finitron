# -*- coding: utf-8 -*-
import io
from elevenlabs import VoiceSettings
import sys
import logging
from flask import Flask, render_template, request, jsonify, send_from_directory, url_for
from flask_cors import CORS
from g4f.client import Client
import g4f
from elevenlabs.client import ElevenLabs
import base64
import json
import time
import os
import requests

characters = {}

# Configure logging
logging.basicConfig(level=logging.DEBUG)

sys.path.append('/root/venv/lib/python3.10/site-packages/')

app = Flask(__name__, static_folder='static')
CORS(app)
application = app
client = Client()

elevenlabs = ElevenLabs(api_key='api-key')

@app.route('/image.jpg')
def serve_image():
    return send_from_directory('static', 'image.jpg')


def generate_sound_effect(text: str):
    try:
        print("Generating sound effects...")
        response = elevenlabs.text_to_sound_effects.convert(
            text="Все звуки, описывающий данную обстановку: " + text[0:300],
            duration_seconds=10,
            prompt_influence=0.3,
        )

        result = io.BytesIO()
        for chunk in response:
            result.write(chunk)

        result.seek(0)

        return base64.b64encode(result.read())
    except Exception as e:
        logging.error(f"Error generating sound effect: {e}")
        return bytes()


class Text2ImageAPI:

    def __init__(self, url, api_key, secret_key):
        self.URL = url
        self.AUTH_HEADERS = {
            'X-Key': f'Key {api_key}',
            'X-Secret': f'Secret {secret_key}',
        }

    def get_model(self):
        response = requests.get(self.URL + 'key/api/v1/models', headers=self.AUTH_HEADERS)
        data = response.json()
        return data[0]['id']

    def generate(self, prompt, model, images=1, width=756, height=756):
        params = {
            "type": "GENERATE",
            "numImages": images,
            "width": width,
            "height": height,
            "generateParams": {
                "query": f"{prompt}"
            }
        }

        data = {
            'model_id': (None, model),
            'params': (None, json.dumps(params), 'application/json')
        }
        response = requests.post(self.URL + 'key/api/v1/text2image/run', headers=self.AUTH_HEADERS, files=data)
        data = response.json()
        print(response.json())
        return data['uuid']

    def check_generation(self, request_id):
        response = requests.get(self.URL + 'key/api/v1/text2image/status/' + request_id, headers=self.AUTH_HEADERS)
        data = response.json()
        if data['status'] == 'DONE':
            return data['images']
        else:
            return None


def generate_image(prompt):
    api = Text2ImageAPI('https://api-key.fusionbrain.ai/', 'api-key', 'secret-key')
    model_id = api.get_model()
    uuid = api.generate(prompt, model_id)
    return uuid

def check_image(uuid):
    api = Text2ImageAPI('https://api-key.fusionbrain.ai/', 'api-key', 'secret-key')
    images = api.check_generation(uuid)
    if (images == None):
        return None
    image_base64 = images[0]
    return image_base64

def speak(text):
    try:
        response = elevenlabs.text_to_speech.convert(
            voice_id="2EiwWnXFnvU5JabPnv8n",
            output_format="mp3_22050_32",
            text=text,
            model_id="eleven_turbo_v2_5",  # use the turbo model for low latency
            voice_settings = VoiceSettings(
                stability=0.0,
                similarity_boost=1.0,
                style=0.0,
                use_speaker_boost=True,
            ),
        )

        result = io.BytesIO()
        for chunk in response:
            result.write(chunk)

        result.seek(0)

        return base64.b64encode(result.read())
    except Exception as e:
        logging.error(f"Error generating voice: {e}")
        return bytes()

def generate_text(model, message):
    try:
        response = None
        match model:
            case "gpt-4o-mini":
                response = g4f.ChatCompletion.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user",
                                "content": message }]
                )
            case "blackbox":
                response = g4f.ChatCompletion.create(
                    model="gpt-4o",
                    messages=[{"role": "user",
                                "content": message }],
                    provider="Blackbox"
                )
            case "pizzagpt":
                response = g4f.ChatCompletion.create(
                    model="gpt-4o",
                    messages=[{"role": "user",
                                "content": message }],
                    provider="Pizzagpt"
                )
            case "ddg":
                response = g4f.ChatCompletion.create(
                    model="gpt-4o",
                    messages=[{"role": "user",
                                "content": message }],
                    provider="DDG"
                )
            case _:
                response = g4f.ChatCompletion.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user",
                                "content": message }],
                )

        return eval(response)
    except Exception as e:
        logging.error(f"Error generating text with {model}: {e}")
        return ["Ошибка при генерации события, повторите ответ или выберите другую модель нейросети", ""]


@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

@app.route('/get_image', methods=['POST'])
def get_image():
    data = request.get_json()
    user_message = data.get('message')
    uuid = data.get('uuid')
    if (uuid != None):
        image = check_image(uuid)
        if (image == None):
            return jsonify({'is_ready': "False"})
        else:
            return jsonify({'is_ready': "True", 'image': image})
        
    uuid = generate_image(user_message)
    return jsonify({'uuid': uuid})

@app.route('/get_sound', methods=['POST'])
def get_sound():
    data = request.get_json()
    user_message = data.get('message')
    sound = generate_sound_effect(user_message).decode("ascii")
    return jsonify({'sound': sound})

@app.route('/get_voice', methods=['POST'])
def get_voice():
    data = request.get_json()
    user_message = data.get('message')
    voice = speak(user_message).decode("ascii")
    return jsonify({'voice': voice})

@app.route('/chat', methods=['POST'])
def chat():
    global response

    data = request.get_json()
    user_message = data.get('message')

    base_message = 'Это квест, тебе нужно написать вопрос, описывай обстановку длинно и ОЧЕНЬ подробно в виде одной строки, очень важно чтобы было подробно и от третьего лица с описанием места или события. Не предлагай свои варианты. Не должно таких предложений: "куда повернешь" или "что ты думаешь" или "что бы там находилось?". Ты должен сам говорить, что происходит вокруг, а пользователя спрашивать что ему делать (не "Что ты будешь делать: бежать или остановиться", а просто "Что вы будете делать?" (НЕ НАДО ПИСАТЬ "ЧТО ОН БУДЕТ ДЕЛАТЬ", ПИШИ "ЧТО ВЫ БУДЕТЕ ДЕЛАТЬ"), вместо слова "пользователь" используй слово "вы". Должна быть логическая цепочка с действиями игрока, которая имеет смысл, на основе этого ты должен ответить с учетом сказанного ответа и обязательно изменять ситуацию в зависимости от этого с участием ответа, ЭТО ОБЯЗАТЕЛЬНО, даже если это никак не относится к обстановке, например взять пушку, заминировать здание, призвать стаю зомби, запустить огненный смерч, создать снежное море и т.д., а не просто повторять сказанное или описывать обстановку или как описывает твои чувства.'
    message_content = None
    if data.get('hasHistory') == "True":
        history = data.get('history') or ''
        question = data.get('question') or ''
        answer = user_message or ''
        characters = data.get('characters') or ''
        print("history: " + history)
        print("question: " + question)
        print("answer: " + answer)
        print("characters: " + characters)
        message_content = f'Создай список из 2 элементов, ТОЛЬКО СПИСОК [], не надо писать python: Есть сюжет про "Подземелья и драконы", последеннее, что человек ответил на вопрос "{question}", было: "{answer}" ЗАПОМНИ ЭТОТ ОТВЕТ И ПРОДВИГАЙ ИСТОРИЮ В ЗАВИСИМОСТИ ОТ НЕГО.'
        message_content += base_message
        message_content += f' Это сообщение будет 1 элементом списка. 2 элемент - изменённый словарь всех характеристик действующих персонажей (в том числе и главного героя), не обязательно враждебных, но не должно быть сопровождающего, персонажи должны быть разные: здоровье, сила, защита, энергия, интеллект, опиши характеристики словарём, например: {"{1 персонаж : {здоровье: 50, сила: 10, защита: 10, энергия: 20, интеллект: 2}}"}, если какой-то персонаж добавился в ситуацию, то добавляй его в словарь. Характеристики изменяются от ситуации (Например: выстрелили, и здоровье или защита уменьшилась. Энергия уменьшается, когда он атакует, здоровье отнимается после того, как вся защита разрушена). Текущие характеристики, измени их в зависимости от вопроса и ответа, который был дан ранее: {characters}. История события до текущего момента: "{history}"'
    else:
        answer = user_message
        print('answer: ' + answer)
        message_content = f'Создай список из 2 элементов, ТОЛЬКО СПИСОК []: '
        if (answer == ''):
            message_content += f'Придумай начало сюжета про "Подземелья и драконы", где будет развилка, это не должен быть какой-нибудь особняк или мрачный лес, каждый раз придумывай что-то новое.'
        else:
            message_content += f'Пользователь хочет начать сюжет так, не используй слово "я", пиши от третьего лица: {answer}.'
        message_content += base_message
        message_content += f' Это сообщение будет 1 элементом списка. 2 элемент - словарь всеми характеристиками действующих персонажей (в том числе и главного героя), не обязательно враждебных, но не должно быть сопровождающего, персонажи должны быть разные: здоровье, сила, защита, энергия, интеллект, опиши характеристики словарём, например: {"{1 персонаж : {здоровье: 50, сила: 10, защита: 10, энергия: 20, интеллект: 2}"}.'


    model = data.get('model')

    # Генерация начала сюжета
    response = generate_text(model, message_content)

    try:
        bot_message = response[0]
        characters = response[1]
    except Exception as e:
        bot_message = response
        charactes = ''

    return jsonify({'message': bot_message, 'characters': characters})

if __name__ == '__main__':
    app.run(debug=True)
