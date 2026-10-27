# -*- coding: utf-8 -*-
import json
import os
from http.server import BaseHTTPRequestHandler
from google import genai
from google.genai import types

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        response_bytes = json.dumps({"status": "API de pl(ai)lister activa"}, ensure_ascii=False).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(response_bytes)))
        self.end_headers()
        self.wfile.write(response_bytes)

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
                err_bytes = json.dumps({"error": "Falta GEMINI_API_KEY en las variables de entorno de Vercel"}, ensure_ascii=False).encode('utf-8')
                self.send_response(500)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('Content-Length', str(len(err_bytes)))
                self.end_headers()
                self.wfile.write(err_bytes)
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

            parsed_data = json.loads(response.text)
            response_bytes = json.dumps(parsed_data, ensure_ascii=False).encode('utf-8')

            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(response_bytes)))
            self.end_headers()
            self.wfile.write(response_bytes)

        except Exception as e:
            err_bytes = json.dumps({"error": str(e)}, ensure_ascii=False).encode('utf-8')
            self.send_response(500)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(err_bytes)))
            self.end_headers()
            self.wfile.write(err_bytes)