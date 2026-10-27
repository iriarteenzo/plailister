import json
import os
from http.server import BaseHTTPRequestHandler
from google import genai
from google.genai import types

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode('utf-8'))
            
            prompt = data.get('prompt', '')
            count = data.get('count', 15)
            artist_count = data.get('artist_count', 5)
            temperature = data.get('temperature', 0.7)

            api_key = os.environ.get("GEMINI_API_KEY")
            if not api_key:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Falta GEMINI_API_KEY en las variables de entorno de Vercel"}).encode())
                return

            client = genai.Client(api_key=api_key)
            instructions = f"""
Actúa como curador musical experto.
Devuelve únicamente JSON válido con esta estructura estricta:
{{"tracks":[{{"artist":"artista","title":"canción"}}]}}
Genera {count} canciones reales y distintas de aproximadamente {artist_count} artistas diferentes basadas en: {prompt}.
No inventes canciones. Evita duplicados. Sin markdown extra.
"""

            response = client.models.generate_content(
                model="gemini-1.5-flash",
                contents=instructions,
                config=types.GenerateContentConfig(
                    temperature=temperature,
                    response_mime_type="application/json",
                ),
            )

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(response.text.encode('utf-8'))

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
