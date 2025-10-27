import io
import os
import json
import zipfile
import datetime
from typing import List, Tuple, Dict

import requests
import streamlit as st


# =========================
# 1) CONFIG & AUTH
# =========================

def get_secret(key: str, default: str = "") -> str:
    # Prefer Streamlit secrets; fallback to env var; else default
    return st.secrets.get(key, os.getenv(key, default))

ELEVEN_API_KEY = get_secret("ELEVEN_API_KEY")
APP_USER = get_secret("APP_USER", "team")
APP_PASS = get_secret("APP_PASS", "strong_password")

if not ELEVEN_API_KEY:
    st.error("ELEVEN_API_KEY is not set. Add it to .streamlit/secrets.toml (or environment).")
    st.stop()

# Simple gate (Streamlit doesn't have built-in Basic Auth)
if "auth_ok" not in st.session_state:
    st.session_state.auth_ok = False

if not st.session_state.auth_ok:
    with st.form("login", clear_on_submit=False):
        st.subheader("Login")
        u = st.text_input("Username", value="", key="u")
        p = st.text_input("Password", value="", type="password", key="p")
        ok = st.form_submit_button("Enter")
        if ok:
            if u == APP_USER and p == APP_PASS:
                st.session_state.auth_ok = True
                st.experimental_rerun()
            else:
                st.error("Invalid credentials")
    st.stop()


# =========================
# 2) DOMAIN DATA
# =========================

# --- Celine: FR / DE / IT (3 voices each) ---
CELINE_VOICES: Dict[str, Dict] = {
    # French
    "fr_corentin": {
        "display": "Corentin",
        "id": "IHngRooVccHyPqB4uQkG",
        "settings": {"similarity_boost": 0.8, "stability": 0.5, "style": 0.2, "use_speaker_boost": True},
        "model_id": "eleven_multilingual_sts_v2",
        "lang": "French",
    },
    "fr_alexis": {
        "display": "Alexis",
        "id": "oEfxSRLn5LTuBsthD6tN",
        "settings": {"similarity_boost": 0.6, "stability": 0.7, "style": 0.4, "use_speaker_boost": True},
        "model_id": "eleven_multilingual_sts_v2",
        "lang": "French",
    },
    "fr_alexandre_boutin": {
        "display": "Alexandre Boutin",
        "id": "IPgYtHTNLjC7Bq7IPHrm",
        "settings": {"similarity_boost": 0.9, "stability": 0.3, "style": 0.1, "use_speaker_boost": True},
        "model_id": "eleven_multilingual_sts_v2",
        "lang": "French",
    },
    # German
    "de_ben": {
        "display": "Ben",
        "id": "aTTiK3YzK3dXETpuDE2h",
        "settings": {"similarity_boost": 0.8, "stability": 0.5, "style": 0.2, "use_speaker_boost": True},
        "model_id": "eleven_multilingual_sts_v2",
        "lang": "German",
    },
    "de_juan_schubert": {
        "display": "Juan Schubert",
        "id": "lx8LAX2EUAKftVz0Dk5z",
        "settings": {"similarity_boost": 0.6, "stability": 0.7, "style": 0.4, "use_speaker_boost": True},
        "model_id": "eleven_multilingual_sts_v2",
        "lang": "German",
    },
    "de_stefan_sport": {
        "display": "Stefan Sport",
        "id": "ElaIVWtKNkyhZOf2vCbL",
        "settings": {"similarity_boost": 0.9, "stability": 0.3, "style": 0.1, "use_speaker_boost": True},
        "model_id": "eleven_multilingual_sts_v2",
        "lang": "German",
    },
    # Italian
    "it_piero_italia": {
        "display": "Piero Italia",
        "id": "slEjHpiFudesZaivDTNt",
        "settings": {"similarity_boost": 0.8, "stability": 0.5, "style": 0.2, "use_speaker_boost": True},
        "model_id": "eleven_multilingual_sts_v2",
        "lang": "Italian",
    },
    "it_salvo_caruso": {
        "display": "Salvo Caruso",
        "id": "mJSddcekWUkB3BOnjPFb",
        "settings": {"similarity_boost": 0.6, "stability": 0.7, "style": 0.4, "use_speaker_boost": True},
        "model_id": "eleven_multilingual_sts_v2",
        "lang": "Italian",
    },
    "it_voce_minatore_audiolibro": {
        "display": "voce minatore audiolibro",
        "id": "F9w7aaEjfT09qV89OdY8",
        "settings": {"similarity_boost": 0.9, "stability": 0.3, "style": 0.1, "use_speaker_boost": True},
        "model_id": "eleven_multilingual_sts_v2",
        "lang": "Italian",
    },
}

CELINE_SECTIONS = [
    ("French",  ["fr_corentin", "fr_alexis", "fr_alexandre_boutin"]),
    ("German",  ["de_ben", "de_juan_schubert", "de_stefan_sport"]),
    ("Italian", ["it_piero_italia", "it_salvo_caruso", "it_voce_minatore_audiolibro"]),
]

# --- Lexi: Spanish only ---
LEXI_VOICES: Dict[str, Dict] = {
    "es_sam_adam": {
        "display": "Sam Adam",
        "id": "18GZPpJvaVG53Nt3H52N",
        "settings": {"similarity_boost": 0.8, "stability": 0.5, "style": 0.2, "use_speaker_boost": True},
        "model_id": "eleven_multilingual_sts_v2",
        "lang": "Spanish",
    },
    "es_jaider": {
        "display": "Jaider",
        "id": "rpqlUOplj0Q0PIilat8h",
        "settings": {"similarity_boost": 0.7, "stability": 0.6, "style": 0.3, "use_speaker_boost": True},
        "model_id": "eleven_multilingual_sts_v2",
        "lang": "Spanish",
    },
}

LEXI_SECTIONS = [
    ("Spanish", ["es_sam_adam", "es_jaider"]),
]

CREATORS = {
    "celine": {"display": "Celine", "voices": CELINE_VOICES, "sections": CELINE_SECTIONS},
    "lexi":   {"display": "Lexi",   "voices": LEXI_VOICES,   "sections": LEXI_SECTIONS},
}


# =========================
# 3) ELEVENLABS CLIENT
# =========================

def _ext_from_content_type(ct: str) -> str:
    if not ct: return ".audio"
    s = ct.lower()
    if "mpeg" in s: return ".mp3"
    if "wav" in s or "x-wav" in s: return ".wav"
    if "ogg" in s: return ".ogg"
    if "flac" in s: return ".flac"
    return ".audio"

def convert_one(file_bytes: bytes, filename: str, mime: str, voice_cfg: Dict) -> Tuple[bytes, str]:
    """
    Convert a single audio file using ElevenLabs STS.
    Returns (converted_bytes, content_type).
    """
    url = f"https://api.elevenlabs.io/v1/speech-to-speech/{voice_cfg['id']}"
    headers = {"xi-api-key": ELEVEN_API_KEY}
    files = {"audio": (filename, io.BytesIO(file_bytes), mime or "application/octet-stream")}
    data = {
        "voice_settings": json.dumps(voice_cfg["settings"]),
        "model_id": voice_cfg.get("model_id", "eleven_multilingual_sts_v2"),
    }
    r = requests.post(url, headers=headers, files=files, data=data, timeout=300)
    if r.status_code != 200:
        raise RuntimeError(f"{r.status_code}: {r.text}")
    return r.content, r.headers.get("content-type", "application/octet-stream")

def convert_batch(files: List[Tuple[bytes, str, str]], voice_cfg: Dict) -> bytes:
    """
    Convert multiple files and return a ZIP (bytes).
    `files` is a list of tuples: (file_bytes, filename, mime)
    """
    buf = io.BytesIO()
    errors = []
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_bytes, filename, mime in files:
            base = os.path.splitext(filename)[0] or "file"
            try:
                out_bytes, ct = convert_one(file_bytes, filename, mime, voice_cfg)
                ext = _ext_from_content_type(ct)
                zf.writestr(f"{base}_converted{ext}", out_bytes)
            except Exception as e:
                errors.append(f"{filename}: {e}")
        if errors:
            report = "Some files failed to convert:\n\n" + "\n".join(errors) + "\n"
            zf.writestr("_errors.txt", report)
    buf.seek(0)
    return buf.read()


# =========================
# 4) UI HELPERS
# =========================

def sidebar_creator_picker() -> str:
    st.sidebar.title("Creators")
    choices = {meta["display"]: key for key, meta in CREATORS.items()}
    label = st.sidebar.selectbox("Choose a creator", list(choices.keys()))
    return choices[label]

def section_voice_picker(creator_key: str) -> Tuple[str, str]:
    """
    Returns (section_title, voice_key) chosen by user.
    Renders tabs (one per section) and a radio of voices in each.
    """
    meta = CREATORS[creator_key]
    sections = meta["sections"]
    tabs = st.tabs([title for title, _ in sections])

    chosen_section = None
    chosen_voice = None

    for i, (title, voice_keys) in enumerate(sections):
        with tabs[i]:
            st.subheader(title)
            # map display -> key for that section
            display_to_key = {
                meta["voices"][vk]["display"]: vk
                for vk in voice_keys
            }
            display_label = st.radio(
                "Select a voice",
                list(display_to_key.keys()),
                key=f"{creator_key}_{title}_voice_radio",
                horizontal=True if len(display_to_key) <= 3 else False
            )
            if st.session_state.get(f"selected_section_{creator_key}", None) is None:
                st.session_state[f"selected_section_{creator_key}"] = title
                st.session_state[f"selected_voice_{creator_key}"] = display_to_key[display_label]

            # Let the last interacted tab/voice win
            if st.button(f"Use '{display_label}' for uploads", key=f"use_{creator_key}_{title}"):
                st.session_state[f"selected_section_{creator_key}"] = title
                st.session_state[f"selected_voice_{creator_key}"] = display_to_key[display_label]

    chosen_section = st.session_state.get(f"selected_section_{creator_key}", sections[0][0])
    chosen_voice = st.session_state.get(f"selected_voice_{creator_key}", sections[0][1][0])

    st.info(f"Active section: **{chosen_section}** · Active voice: **{meta['voices'][chosen_voice]['display']}**")
    return chosen_section, chosen_voice


# =========================
# 5) MAIN UI
# =========================

st.title("Voice Converter — Streamlit")
creator_key = sidebar_creator_picker()
creator = CREATORS[creator_key]

st.header(creator["display"])
section_title, voice_key = section_voice_picker(creator_key)
voice_cfg = creator["voices"][voice_key]

st.markdown("---")
st.subheader("Upload audio files")
uploaded = st.file_uploader(
    "Drop or pick 1+ audio files",
    type=None,  # let users upload any audio; you can restrict (e.g., ["mp3","wav","ogg","flac"])
    accept_multiple_files=True,
    help="You can upload a single file (returns one audio) or multiple files (returns a ZIP).",
)

if uploaded:
    # Show a quick summary table
    st.write("Files selected:")
    for f in uploaded:
        st.write(f"- `{f.name}` ({f.type or 'application/octet-stream'})")

    if st.button("Convert"):
        try:
            if len(uploaded) == 1:
                f = uploaded[0]
                with st.spinner("Converting..."):
                    out_bytes, ct = convert_one(f.read(), f.name, f.type, voice_cfg)
                ext = _ext_from_content_type(ct)
                out_name = os.path.splitext(f.name)[0] + "_converted" + ext
                st.success("Done.")
                st.download_button(
                    label=f"Download {out_name}",
                    data=out_bytes,
                    file_name=out_name,
                    mime=ct or "application/octet-stream",
                    use_container_width=True,
                )
            else:
                files = []
                total = len(uploaded)
                prog = st.progress(0, text="Processing batch...")
                for i, f in enumerate(uploaded, start=1):
                    files.append((f.read(), f.name, f.type))
                    prog.progress(i / total, text=f"Processing {i}/{total}")
                with st.spinner("Building ZIP..."):
                    zip_bytes = convert_batch(files, voice_cfg)
                stamp = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
                zip_name = f"{creator_key}_{voice_key}_converted_{stamp}.zip"
                st.success("Batch complete.")
                st.download_button(
                    label=f"Download {zip_name}",
                    data=zip_bytes,
                    file_name=zip_name,
                    mime="application/zip",
                    use_container_width=True,
                )
        except Exception as e:
            st.error(f"Conversion error: {e}")

st.markdown("---")
st.caption("Your API key remains on the server. No uploads are stored; results are returned directly.")
