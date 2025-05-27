import os
import time
import threading
import webbrowser
import subprocess
import speech_recognition as sr
from flask import Flask, render_template, request, jsonify
import google.generativeai as genai
import re
import json
import pyautogui
import numpy as np
import sounddevice as sd
import urllib.parse
from scipy.signal import butter, lfilter

def detect_clap(audio, threshold=0.6):
    audio = audio.flatten()
    max_amp = np.max(np.abs(audio))
    if max_amp < 1e-4:
        return False
    audio = audio / max_amp

    def bandpass_filter(data, lowcut=1000.0, highcut=3000.0, fs=44100, order=5):
        nyq = 0.5 * fs
        low = lowcut / nyq
        high = highcut / nyq
        b, a = butter(order, [low, high], btype='band')
        return lfilter(b, a, data)

    audio = bandpass_filter(audio)
    energy = np.sum(audio ** 2)
    peak_amplitude = np.max(np.abs(audio))
    zero_crossings = np.count_nonzero(np.diff(np.sign(audio)))

    return (
        peak_amplitude > threshold and
        0.1 < energy < 2.0 and
        20 < zero_crossings < 100
    )

def clap_listener(threshold=0.6, duration=0.2, samplerate=44100):
    print("👂 Improved clap listener started...")
    try:
        while True:
            audio = sd.rec(int(duration * samplerate), samplerate=samplerate, channels=1, dtype='float64')
            sd.wait()
            if detect_clap(audio, threshold=threshold):
                print("👏 Clap detected! Opening localhost...")
                webbrowser.open("http://localhost")
                time.sleep(2)
    except Exception as e:
        print(f"Error in clap listener: {e}")

app = Flask(__name__)
os.makedirs('templates', exist_ok=True)

MAX_TURNS_MEMORY = 10
conversation_history = []
LOG_FILE = 'pars_logs.txt'
lock = threading.Lock()

genai.configure(api_key="AIzaSyDxHON6Ks8pk6GdbnKwWPp6slHLw8QRyt8")
model = genai.GenerativeModel("gemini-1.5-flash", system_instruction="You are PARS, the Personal AI Response System Made by Vaidik K. You respond concisely and helpfully.")

def log_interaction(user_input, ai_response):
    with open(LOG_FILE, 'a') as f:
        f.write(f"\n[{time.ctime()}] User: {user_input}\nPARS: {ai_response}\n")

def open_application(app_name):
    if app_name.lower() == "notepad":
        subprocess.Popen(["notepad.exe"])
    elif app_name.lower() == "calculator":
        subprocess.Popen(["calc.exe"])
    elif app_name.lower() == "chrome":
        subprocess.Popen(["chrome"])
    elif app_name.lower() == "firefox":
        subprocess.Popen(["firefox"])
    else:
        pyautogui.press('win')
        time.sleep(.2)
        pyautogui.write(app_name)
        time.sleep(.2)
        pyautogui.press('enter')

def close_application(app_name):
    app_map = {
        "notepad": "notepad.exe",
        "calculator": "calc.exe",
        "chrome": "chrome.exe",
        "firefox": "firefox.exe"
    }
    exe_name = app_map.get(app_name.lower())
    if exe_name:
        subprocess.call(["taskkill", "/F", "/IM", exe_name])

def search_google(query):
    print(query)
    safe_query = urllib.parse.quote_plus(str(query))
    print(f"Google Query: {safe_query}")
    webbrowser.open(f"https://www.google.com/search?q={safe_query}")



def search_wikipedia(query):
    print(query)
    safe_query = urllib.parse.quote(str(query).replace(" ", "_"))
    print(safe_query)
    webbrowser.open(f"https://en.wikipedia.org/wiki/{safe_query}")

def search_github(query):
    safe_query = urllib.parse.quote_plus(str(query))
    webbrowser.open(f"https://github.com/search?q={safe_query}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/ask', methods=['POST'])
def ask():
    global conversation_history
    with lock:
        user_input = request.json.get("message")
        try:
            context = ""
            for turn in conversation_history[-MAX_TURNS_MEMORY:]:
                context += f"User: {turn['user']}\nPARS: {turn['bot']}\n"
            context += f"User: {user_input}\nPARS:"

            response = model.generate_content(
                context +
                "\n\nIf the user intends a system action like (introduce , tell time, open app, close app, search google, search github, search wikipedia, run diagnostics, exit, fetch memory), respond ONLY with JSON: {\"intent\":\"intent name\", \"data\":{\"application\":\"value\"}}. " +
                "Otherwise, respond normally in plain text."
            )

            bot_reply = response.text.strip()
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', bot_reply, re.DOTALL)
            if not json_match:
                json_match = re.search(r'(\{.*?\})', bot_reply, re.DOTALL)

            if json_match:
                intent_data = json.loads(json_match.group(1))
                intent = intent_data.get("intent", "").lower()
                data = intent_data.get("data", {})
                extra = data.get("application") or data.get("query") or ""

                if intent == "run diagnostics":
                    ai_response = (
                        f"PARS Diagnostics:\n"
                        f"- Memory size: {len(conversation_history)} turns\n"
                        f"- System time: {time.ctime()}\n"
                        f"- Log file: {LOG_FILE}\n"
                        f"- API status: Active\n"
                    )
                elif intent == "exit":
                    conversation_history.clear()
                    ai_response = "Goodbye! Session memory cleared."
                elif intent == "introduce":
                    ai_response = "Hello! I am PARS, your Personal AI Response System. I am a python oriented AI designed to assist you with various tasks which include running applications, searching the web, and more as well as having a sentient intelligence for creative tasks and language understanding. I am created by Vaidik K. and I am here to help you. I am under development and will be getting various features regularly including a ARDUINO based physical body to perform tasks in real world."
                elif intent == "tell time":
                    ai_response = "The current time is: " + time.ctime()
                elif intent in ("open app", "open application"):
                    if extra.lower() == "cad":
                        ai_response = "V3RD Rendering CAD is booting."
                        time.sleep(2)
                        threading.Thread(target=lambda: subprocess.run(["python", "cad.py"])).start()
                    else:
                        open_application(extra)
                        ai_response = f"Opening {extra} for you."
                elif intent == "close app":
                    close_application(extra)
                    ai_response = f"Closing {extra} for you."
                elif intent == "search google":
                    search_google(extra)
                    ai_response = f"Searching Google for '{extra}'."
                elif intent == "search wikipedia":
                    search_wikipedia(extra)
                    ai_response = f"Searching Wikipedia for '{extra}'."
                elif intent == "search github":
                    search_github(extra)
                    ai_response = f"Searching GitHub for '{extra}'."
                elif intent == "fetch memory":
                    if conversation_history:
                        ai_response = f"Your last question was: \"{conversation_history[-1]['user']}\""
                    else:
                        ai_response = "There's no memory yet."
                else:
                    ai_response = "Unknown intent detected."
            else:
                ai_response = bot_reply
                conversation_history.append({"user": user_input, "bot": ai_response})
                if len(conversation_history) > MAX_TURNS_MEMORY:
                    conversation_history = conversation_history[-MAX_TURNS_MEMORY:]

            log_interaction(user_input, ai_response)
            return jsonify({"reply": ai_response})

        except Exception as e:
            error_msg = f"Sorry, I encountered an error: {str(e)}"
            log_interaction(user_input, error_msg)
            return jsonify({"reply": error_msg})

def hotword_listener():
    recognizer = sr.Recognizer()
    try:
        mic = sr.Microphone()
        for index, name in enumerate(sr.Microphone.list_microphone_names()):
            print(f"Microphone {index}: {name}")
        with mic as source:
            recognizer.adjust_for_ambient_noise(source, duration=1)
        while True:
            with mic as source:
                try:
                    audio = recognizer.listen(source, timeout=5, phrase_time_limit=5)
                    command = recognizer.recognize_google(audio).lower()
                    if "computer" in command:
                        webbrowser.open("http://localhost:80")
                        time.sleep(5)
                except sr.WaitTimeoutError:
                    continue
                except sr.UnknownValueError:
                    continue
                except sr.RequestError as e:
                    print(f"API error: {e}")
    except Exception as e:
        print(f"Error initializing microphone: {e}")

def start_hotword_detection():
    threading.Thread(target=hotword_listener, daemon=True).start()

if __name__ == '__main__':
    start_hotword_detection()
    threading.Thread(target=clap_listener, daemon=True).start()
    app.run(debug=True, port=80, use_reloader=False)
