# -*- coding: utf-8 -*-
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

count = 0
history = {}
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



def generate_sound_effect(text: str, output_path: str):
    try:
        print("Generating sound effects...")
        result = elevenlabs.text_to_sound_effects.convert(
            text="Все звуки, описывающий данную обстановку: " + text[0:300],
            duration_seconds=10,
            prompt_influence=0.3,
        )

        with open(output_path, "wb") as f:
            for chunk in result:
                f.write(chunk)

        print(f"Audio saved to {output_path}")
    except Exception as e:
        logging.error(f"Error generating sound effect: {e}")


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

    def generate(self, prompt, model, images=1, width=1024, height=1024):
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
        return data['uuid']

    def check_generation(self, request_id, attempts=10, delay=10):
        while attempts > 0:
            response = requests.get(self.URL + 'key/api/v1/text2image/status/' + request_id, headers=self.AUTH_HEADERS)
            data = response.json()
            if data['status'] == 'DONE':
                return data['images']

            attempts -= 1
            time.sleep(delay)


def generate_image(prompt):
    api = Text2ImageAPI('https://api-key.fusionbrain.ai/', 'api-key', 'secret-key')
    model_id = api.get_model()
    uuid = api.generate(prompt, model_id)
    images = api.check_generation(uuid)
    print(images)
    image_base64 = images[0]
    image_data = base64.b64decode(image_base64)

    timestamp = int(time.time())
    image_path = f"static/image_{timestamp}.jpg"

    with open("static/image.jpg", "wb") as file:
        file.write(image_data)
    return image_path

def speak(text):
    response = elevenlabs.text_to_speech.convert(
        voice_id="2EiwWnXFnvU5JabPnv8n",
        output_format="mp3_22050_32",
        text=text,
        model_id="eleven_turbo_v2_5",  # use the turbo model for low latency
        voice_settings=VoiceSettings(
            stability=0.0,
            similarity_boost=1.0,
            style=0.0,
            use_speaker_boost=True,
        ),
    )
    # Generating a unique file name for the output MP3 file
    save_file_path = "static/voice.mp3"

    # Writing the audio to a file
    with open(save_file_path, "wb") as f:
        for chunk in response:
            if chunk:
                f.write(chunk)

    print(f"{save_file_path}: A new audio file was saved successfully!")


@app.route('/')
def index():
    return send_from_directory('.', 'index.html')



@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)


@app.route('/chat', methods=['POST'])
def chat():
    global response, response2, answer, characters, history, count
    logging.debug(f"Current count value: {count}")
    user_message = request.json.get('message')

    data = request.get_json()
    sounds_enabled = data.get('soundsEnabled')  # Получаем значение soundsEnabled из запроса
    images_enabled = data.get('imagesEnabled')
    voice_enabled = data.get('voiceEnabled')
    user_message = data.get('message')

    answer = user_message
    if count == 0:
        count += 1
        logging.debug(f"Count incremented to: {count}")
        # Генерация начала сюжета
        response = g4f.ChatCompletion.create(
            model="gpt-4o",
            messages=[{"role": "user",
                       "content":
                           'Создай список из 2 элементов, ТОЛЬКО СПИСОК []: Придумай начало сюжета про "Подземелья и драконы", где далее будет развилка, это не должен быть просто какой-нибудь особняк, каждый раз придумывай что-то новое. Это страшный квест, тебе нужно добавить вопрос (описывая обстановку большим и подробным текстом), имменно в виде строки, не предлагай свои варианты, что ему выбрать, пользователь сам напишет ответ. Ничего не пиши кроме 1 строки. Не должно быть по типу: куда повернешь или что ты думаешь или что бы там находилось? Ты сам должен говорить, что происходит вокруг, а пользователя спрашивать, что ему делать (не "Что ты будешь делать: бежать или остановиться", а просто "Что ты будешь делать?" - это писать не надо (НЕ НАДО ПИСАТЬ "ЧТО ВЫ БУДЕТЕ ДЕЛАТЬ") Должна быть логическая цепочка с действиями игроков, которая имеет смысл в последующем, хоть что пользователь скажет, на основе этого бот должен отвечать с учетом сказанного пользователем и обязательно ОБЯЗАТЕЛЬНО, БЕЗ ЭТОГО НИКАК изменять ситуацию в зависимости от этого с участием сказанного пользователем, даже если это никак не относится к обстановке, например взять пушку, заминировать здание, призвать стаю зомби, и т.д., а не просто повторять сказанное или описывать обстановку или как описывает твои чувства. Это сообщение будет 1 элементом списка. 2 элемент - словарь всеми характеристиками действующих персонажей (в том числе и главного героя), не обязательно враждебных, но не должно быть сопровождающего, персонажи должны быть вообще разные: здоровье, сила, защита, энергия, интеллект, все действующие персонажи и их характеристики, словарем в виде {1 персонаж : {"здоровье": 50, "сила": 10, "защита": 10, "энергия": 20, "интеллект": 2}}'}],
            provider="Pizzagpt"
        )
        response = eval(response)

        response2 = response
        print(response)

        bot_message = response[0]
        characters = response[1]
        if sounds_enabled:
            generate_sound_effect(bot_message, os.path.join(app.static_folder, "output.mp3"))
        if images_enabled:
            generate_image(bot_message)
        if voice_enabled:
            speak(bot_message)
        return jsonify({'message': response[0], 'characters': characters})
    else:
        history[response2[0]] = answer
        response2 = g4f.ChatCompletion.create(
            model="gpt-4o",
            messages=[{"role": "user",
                       "content":
                           f'Создай список из 2 элементов, ТОЛЬКО СПИСОК [], не надо писать python: Есть сюжет про "Подземелья и драконы", до этого было выбрано "{history}", последеннее, что человек ответил на вопрос "{response}", было "{answer}". Это страшный квест, тебе нужно добавить вопрос (описывая обстановку большим и подробным текстом), имменно в виде строки, не предлагай свои варианты, пользователь сам напишет ответ. Ничего не пиши кроме 1 строки. Не должно быть по типу: куда повернешь или что ты думаешь или что бы там находилось? Ты сам должен говорить, что происходит вокруг, а пользователя спрашивать, что ему делать (не "Что ты будешь делать: бежать или остановиться", а просто "Что ты будешь делать?" - это писать не надо (НЕ НАДО ПИСАТЬ ЧТО "ВЫ БУДЕТЕ ДЕЛАТЬ") Должна быть логическая цепочка с действиями игроков, которая имеет смысл в последующем, хоть что пользователь скажет, на основе этого бот должен отвечать с учетом сказанного пользователем и обязательно ОБЯЗАТЕЛЬНО, БЕЗ ЭТОГО НИКАК, изменять ситуацию в зависимости от этого с участием сказанного пользователем, ЭТО ОБЯЗАТЕЛЬНО, даже если это никак не относится к обстановке, например взять пушку, заминировать здание, призвать стаю зомби, запустить огненный смерч, создать снежное море и т.д., а не просто повторять сказанное или описывать обстановку или как описывает твои чувства. Это сообщение будет 1 элементом списка. 2 элемент - словарь всеми характеристиками действующих персонажей (в том числе и главного героя), не обязательно враждебных, но не должно быть сопровождающего, персонажи должны быть вообще разные (хоть гоблины, хоть драконы, хоть рыцари, хоть торговцы): здоровье, сила, защита, энергия, интеллект, все действующие персонажи и их характеристики, словарем в виде {"{1 персонаж : {здоровье: 50, сила: 10, защита: 10, энергия: 20, интеллект: 2}}"}, если какой-то персонаж добавился в ситуацию, то добавляй его в словарь. Характеристики изменяются от ситуации (Например: выстрелили, и здоровье или защита уменьшилась. Энергия уменьшается, когда он атакует, здоровье отнимается после того, как вся защита разрушена). Текущие характеристики: {response2[1]}'}],
            provider="Pizzagpt"
        )
        response2 = eval(response2)

        print(response2)
        characters = response2[1]
        bot_message = response2[0]
        characters = {k: v for k, v in characters.items() if v.get('здоровье', 0) > 0}

        if sounds_enabled:
            generate_sound_effect(bot_message, os.path.join(app.static_folder, "output.mp3"))

        if images_enabled:
            generate_image(bot_message)

        if voice_enabled:
            speak(bot_message)

        return jsonify({'message': response2[0], 'characters': characters})


if __name__ == '__main__':
    app.run(debug=True)
