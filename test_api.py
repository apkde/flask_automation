import google.generativeai as genai

api_key = "AIzaSyAmePiKBLndKTyHq-AmCrgWZtUB9OgvOZw"
genai.configure(api_key=api_key)
model = genai.GenerativeModel('gemini-pro')

try:
    response = model.generate_content("Hello")
    print("Success:", response.text)
except Exception as e:
    print("Error:", str(e)) 