import html
import json
import os
import secrets
import time

import streamlit as st
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from google import genai
from google.genai import types

# =========================================================
# CONFIGURACIÓN
# =========================================================

st.set_page_config(
    page_title="pl(ai)lister",
    page_icon="♪",
    layout="wide",
    initial_sidebar_state="expanded",
)

DEFAULT_MODEL = "gemini-1.5-flash"
SPOTIFY_SCOPES = "playlist-modify-public playlist-modify-private"

def get_secret(key, default=""):
    try:
        return st.secrets.get(key, default) or default
    except Exception:
        return os.getenv(key, default) or default

GEMINI_API_KEY = get_secret("GEMINI_API_KEY")
GEMINI_MODEL = get_secret("GEMINI_MODEL", DEFAULT_MODEL)

SPOTIFY_CLIENT_ID = get_secret("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = get_secret("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = get_secret(
    "SPOTIFY_REDIRECT_URI",
    "http://localhost:8501",
).rstrip("/")

# =========================================================
# DISEÑO CSS
# =========================================================

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Google+Sans:wght@400;500;600;700&display=swap');

:root {
    --bg: #121212;
    --surface: #1E1E1E;
    --surface-hover: #292929;
    --border: #383838;
    --text: #F5F5F5;
    --muted: #A7A7A7;
    --green: #1ED760;
    --green-hover: #3BE477;
    --green-text: #07150B;
    --font: "Google Sans", Arial, sans-serif;
    --radius: 16px;
    --radius-pill: 999px;
    --control-height: 46px;
}

html, body, [class*="css"], .stApp {
    font-family: var(--font) !important;
    background: var(--bg);
    color: var(--text);
}

header[data-testid="stHeader"] { background: transparent; }
#MainMenu, footer { visibility: hidden; }

.block-container {
    max-width: 880px;
    padding: 28px 28px 32px !important;
}

h1 { font-size: clamp(30px, 4vw, 40px) !important; font-weight: 600 !important; }
.muted { color: var(--muted); font-size: 14px; }
.eyebrow { color: var(--green); font-size: 11px; font-weight: 700; letter-spacing: 1.3px; text-transform: uppercase; margin-bottom: 10px; }

.brand {
    display: flex; align-items: center; gap: 4px; margin-bottom: 28px;
    color: var(--text); font-size: 26px; font-weight: 700; letter-spacing: -1.2px;
}
.brand-ai {
    display: inline-flex; align-items: center; justify-content: center;
    width: 24px; height: 24px; border: 2px solid var(--green); border-radius: 50%;
    color: var(--green); font-size: 10px;
}

section[data-testid="stSidebar"] {
    background: #090909;
    border-right: 1px solid #292929;
}
section[data-testid="stSidebar"] > div { padding: 24px 18px; }

.stButton > button, .stLinkButton > a, div[data-testid="stFormSubmitButton"] button {
    display: flex; align-items: center; justify-content: center;
    min-height: var(--control-height) !important; height: var(--control-height);
    padding: 0 18px !important; border: 1px solid var(--border) !important;
    border-radius: var(--radius-pill) !important; background: var(--surface-hover) !important;
    color: var(--text) !important; font-weight: 600 !important; text-decoration: none !important;
}
.stButton > button[kind="primary"], div[data-testid="stFormSubmitButton"] button {
    background: var(--green) !important; border-color: var(--green) !important; color: var(--green-text) !important;
}

div[data-testid="stTextArea"] textarea {
    background: var(--surface) !important; color: var(--text) !important;
    border: 1px solid var(--border) !important; border-radius: 12px !important; padding: 14px !important;
}
div[data-testid="stTextArea"] label { display: none !important; }

.composer {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 20px; padding: 18px; margin: 24px 0 16px;
}
.track-row {
    display: flex; align-items: center; gap: 14px; padding: 14px 4px; border-bottom: 1px solid #303030;
}
.result-card {
    background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 22px; margin: 16px 0;
}
</style>
""", unsafe_allow_html=True)

# =========================================================
# FUNCIONES DE APOYO Y SPOTIFY
# =========================================================

def brand():
    st.markdown('<div class="brand">pl<span class="brand-ai">ai</span>lister</div>', unsafe_allow_html=True)

def spotify_oauth():
    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        return None
    return SpotifyOAuth(
        client_id=SPOTIFY_CLIENT_ID, client_secret=SPOTIFY_CLIENT_SECRET,
        redirect_uri=SPOTIFY_REDIRECT_URI, scope=SPOTIFY_SCOPES, cache_path=None, open_browser=False
    )

def spotify_client():
    token = st.session_state.get("spotify_token")
    if not token: return None
    oauth = spotify_oauth()
    if not oauth: return None
    if token.get("expires_at", 0) < time.time() + 60:
        try:
            token = oauth.refresh_access_token(token.get("refresh_token"))
            st.session_state.spotify_token = token
        except Exception:
            st.session_state.pop("spotify_token", None)
            return None
    return spotipy.Spotify(auth=token["access_token"])

def spotify_connect_button():
    oauth = spotify_oauth()
    if not oauth:
        st.caption("Configura Spotify en Secrets.")
        return
    if not st.session_state.get("oauth_state"):
        st.session_state.oauth_state = secrets.token_urlsafe(24)
    url = html.escape(oauth.get_authorize_url(state=st.session_state.oauth_state), quote=True)
    st.markdown(f'<a href="{url}" target="_self" style="display:flex;align-items:center;justify-content:center;gap:10px;height:46px;padding:0 16px;background:#1ED760;color:#07150B;border-radius:999px;text-decoration:none;font-weight:600">Conectar con Spotify</a>', unsafe_allow_html=True)

# =========================================================
# GENERACIÓN CON GEMINI
# =========================================================

def generate_tracks(prompt, count, artist_count, temperature):
    if not GEMINI_API_KEY:
        raise ValueError("Falta configurar GEMINI_API_KEY en los Secrets.")

    client = genai.Client(api_key=GEMINI_API_KEY)
    instructions = f"""
Actúa como curador musical experto.
Devuelve únicamente JSON válido con esta estructura estricta:
{{"tracks":[{{"artist":"artista","title":"canción"}}]}}
Genera {count} canciones reales y distintas de aproximadamente {artist_count} artistas diferentes basadas en: {prompt}.
No inventes canciones. Evita duplicados. Sin markdown extra.
"""

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=instructions,
        config=types.GenerateContentConfig(
            temperature=temperature,
            response_mime_type="application/json",
        ),
    )

    try:
        data = json.loads(response.text or "")
    except json.JSONDecodeError as exc:
        raise ValueError("La respuesta de la IA no devolvió un JSON válido.") from exc

    tracks, seen = [], set()
    for item in data.get("tracks", []):
        if not isinstance(item, dict): continue
        artist, title = str(item.get("artist", "")).strip(), str(item.get("title", "")).strip()
        key = (artist.casefold(), title.casefold())
        if artist and title and key not in seen:
            tracks.append({"artist": artist, "title": title})
            seen.add(key)
        if len(tracks) == count: break

    if len(tracks) < count:
        raise ValueError(f"Solo se obtuvieron {len(tracks)} de {count} canciones.")
    return tracks

def find_spotify_tracks(sp, tracks):
    found, missing, seen_uris = [], [], set()
    progress = st.progress(0, text="Buscando en Spotify…")
    for i, track in enumerate(tracks):
        try:
            result = sp.search(q=f'track:"{track["title"]}" artist:"{track["artist"]}"', type="track", limit=3)
            items = result.get("tracks", {}).get("items", [])
            if not items:
                result = sp.search(q=f'{track["title"]} {track["artist"]}', type="track", limit=3)
                items = result.get("tracks", {}).get("items", [])
            match = next((item for item in items if item["uri"] not in seen_uris), None)
            if match:
                seen_uris.add(match["uri"])
                found.append({
                    "title": match["name"],
                    "artist": ", ".join(a["name"] for a in match.get("artists", [])),
                    "album": match.get("album", {}).get("name", ""),
                    "uri": match["uri"],
                    "url": match.get("external_urls", {}).get("spotify", ""),
                })
            else:
                missing.append(track)
        except Exception:
            missing.append(track)
        progress.progress((i + 1) / max(len(tracks), 1))
    progress.empty()
    return found, missing

# =========================================================
# ESTADO E INTERFAZ
# =========================================================

DEFAULTS = {"step": "create", "count": 15, "artist_count": 5, "temperature": 0.7, "history": [], "tracks": [], "resolved": [], "missing": []}
for k, v in DEFAULTS.items(): st.session_state.setdefault(k, v)

def reset_app():
    for k in ("tracks", "resolved", "missing", "playlist_name", "playlist_url", "review_text"):
        st.session_state.pop(k, None)
    st.session_state.step = "create"

@st.dialog("Ajustes", width="small")
def settings_dialog():
    st.slider("Cantidad de canciones", 5, 30, key="count")
    st.slider("Cantidad de artistas", 1, 10, key="artist_count")
    st.slider("Creatividad", 0.0, 1.0, step=0.1, key="temperature")
    if st.button("Guardar", type="primary", use_container_width=True): st.rerun()

with st.sidebar:
    brand()
    if st.button("＋ Nueva playlist", type="primary", use_container_width=True):
        reset_app(); st.rerun()
    st.divider()
    if spotify_client():
        st.markdown('<p style="color:#1ED760;font-weight:600">● Conectado a Spotify</p>', unsafe_allow_html=True)
        if st.button("Desconectar", use_container_width=True):
            st.session_state.pop("spotify_token", None); st.rerun()
    else:
        spotify_connect_button()

# FLUJO PRINCIPAL
if st.session_state.step == "create":
    brand()
    st.markdown('<div class="eyebrow">Descubrimiento musical con IA</div>', unsafe_allow_html=True)
    st.title("¿Qué quieres escuchar?")
    st.markdown('<p class="muted">Describe tu ambiente, género o época musical.</p>', unsafe_allow_html=True)
    
    st.markdown('<div class="composer">', unsafe_allow_html=True)
    st.text_area("Prompt", key="prompt_input", height=120, placeholder="Ej.: Rock alternativo de los 2000, oscuro y enérgico...")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("⚙ Ajustes", use_container_width=True): settings_dialog()
    with col2:
        generate = st.button("Generar playlist ↗", type="primary", use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    if generate:
        prompt = st.session_state.get("prompt_input", "").strip()
        if not prompt:
            st.warning("Escribe una descripción.")
        else:
            try:
                with st.spinner("Creando selección musical..."):
                    st.session_state.tracks = generate_tracks(prompt, st.session_state.count, st.session_state.artist_count, st.session_state.temperature)
                st.session_state.step = "review"
                st.rerun()
            except Exception as e:
                st.error(f"Error al generar: {e}")

elif st.session_state.step == "review":
    brand()
    st.title("Revisa tu selección")
    st.text_area("Edita si lo deseas (Artista - Canción)", value="\n".join(f'{t["artist"]} - {t["title"]}' for t in st.session_state.tracks), height=300, key="review_text")
    
    c1, c2 = st.columns(2)
    with c1:
        if st.button("← Volver", use_container_width=True): st.session_state.step = "create"; st.rerun()
    with c2:
        if st.button("Buscar en Spotify ↗", type="primary", use_container_width=True):
            edited = []
            for line in st.session_state.review_text.splitlines():
                if " - " in line:
                    art, tit = line.split(" - ", 1)
                    edited.append({"artist": art.strip(), "title": tit.strip()})
            if not spotify_client():
                st.warning("Conecta Spotify primero.")
            else:
                found, missing = find_spotify_tracks(spotify_client(), edited)
                st.session_state.resolved, st.session_state.missing = found, missing
                st.session_state.step = "export"
                st.rerun()

elif st.session_state.step == "export":
    brand()
    st.title("Exportar a Spotify")
    resolved = st.session_state.resolved
    st.markdown(f'<p class="muted">{len(resolved)} canciones listas para exportar.</p>', unsafe_allow_html=True)
    
    with st.form("export_form"):
        pl_name = st.text_input("Nombre de la playlist", value="Mi playlist con pl(ai)lister")
        privacy = st.radio("Privacidad", ["Privada", "Pública"], horizontal=True)
        submitted = st.form_submit_button("Crear en Spotify", type="primary", use_container_width=True)

    if submitted:
        sp = spotify_client()
        if not sp:
            st.error("Spotify desconectado.")
        else:
            user = sp.current_user()
            pl = sp.user_playlist_create(user=user["id"], name=pl_name, public=(privacy == "Pública"))
            uris = [t["uri"] for t in resolved]
            sp.playlist_add_items(pl["id"], uris[:100])
            st.session_state.playlist_name = pl_name
            st.session_state.playlist_url = pl.get("external_urls", {}).get("spotify", "")
            st.session_state.step = "success"
            st.rerun()

elif st.session_state.step == "success":
    brand()
    st.title("¡Playlist creada con éxito! 🎉")
    st.markdown(f'<div class="result-card"><h3>{html.escape(st.session_state.get("playlist_name", ""))}</h3></div>', unsafe_allow_html=True)
    if st.session_state.get("playlist_url"):
        st.link_button("Abrir en Spotify ↗", st.session_state.get("playlist_url"), type="primary", use_container_width=True)
    if st.button("Crear otra playlist", use_container_width=True):
        reset_app(); st.rerun()
