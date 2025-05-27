import os
import time
import threading
import webbrowser
import speech_recognition as sr
from flask import Flask, render_template, request, jsonify
import google.generativeai as genai

app = Flask(__name__)
os.makedirs('templates', exist_ok=True)

MAX_TURNS_MEMORY = 10
conversation_history = []
LOG_FILE = 'pars_logs.txt'

genai.configure(api_key="AIzaSyAezigkpx3Spkg3WoWBg6GwsVI0BWH6ebc")
model = genai.GenerativeModel("gemini-1.5-flash", system_instruction="You are PARS, the Personal AI Response System Made by Vaidik K. You respond concisely and helpfully.")

def log_interaction(user_input, ai_response):
    with open(LOG_FILE, 'a') as f:
        f.write(f"\n[{time.ctime()}] User: {user_input}\nPARS: {ai_response}\n")

def detect_intent(user_input, intent_label):
    try:
        prompt = f"Does the following message mean the user wants to '{intent_label}'? Only answer yes or no.\nMessage: {user_input}"
        check_response = model.generate_content(prompt)
        return "yes" in check_response.text.lower()
    except:
        return False

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/ask', methods=['POST'])
def ask():
    global conversation_history
    user_input = request.json.get("message")

    try:
        if detect_intent(user_input, "do homework"):
            ai_response = "Sure! What homework do you want me to help with?"

        elif detect_intent(user_input, "run diagnostics"):
            ai_response = (
                f"PARS Diagnostics:\n"
                f"- Memory size: {len(conversation_history)} turns\n"
                f"- System time: {time.ctime()}\n"
                f"- Log file: {LOG_FILE}\n"
                f"- API status: Active\n"
            )

        elif detect_intent(user_input, "exit"):
            ai_response = "Goodbye! Shutting down session memory."
            conversation_history.clear()

        else:
            context = ""
            for turn in conversation_history[-MAX_TURNS_MEMORY:]:
                context += f"User: {turn['user']}\nPARS: {turn['bot']}\n"
            context += f"User: {user_input}\nPARS:"
            response = model.generate_content(context)
            ai_response = response.text.strip()

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
    print("[🎤] Starting hotword detection...")
    recognizer = sr.Recognizer()
    
    try:
        mic = sr.Microphone()
        print("[🎤] Microphone initialized.")
        
        for index, name in enumerate(sr.Microphone.list_microphone_names()):
            print(f"Microphone {index}: {name}")
        
        print("[🎤] Calibrating mic...")
        with mic as source:
            recognizer.adjust_for_ambient_noise(source, duration=1)
            print("[👂] Say 'computer' to activate P.A.R.S.")

        while True:
            with mic as source:
                print("[⏳] Listening for hotword...")
                try:
                    audio = recognizer.listen(source, timeout=5, phrase_time_limit=5)
                    print("[🔊] Audio captured, recognizing...")
                    command = recognizer.recognize_google(audio).lower()
                    print(f"[📢] Heard: {command}")

                    if "computer" in command:
                        print("[✅] Hotword detected! Launching...")
                        webbrowser.open("http://localhost:80")
                        time.sleep(5)
                except sr.WaitTimeoutError:
                    print("[⏳] Timeout, no speech detected.")
                except sr.UnknownValueError:
                    print("[❌] Couldn't understand. Listening again...")
                except sr.RequestError as e:
                    print(f"[❗] API error: {e}")
    except Exception as e:
        print(f"[❗] Error initializing microphone: {e}")
        print("[ℹ️] Running web interface without hotword detection.")

def start_hotword_detection():
    threading.Thread(target=hotword_listener, daemon=True).start()

if __name__ == '__main__':
    start_hotword_detection()
    print("[🚀] Starting Flask server on http://localhost:80")
    app.run(debug=True, port=80, use_reloader=False)
