import io
import os
import json
import zipfile
import datetime
import wave  # Added for wrapping raw PCM in WAV
from typing import List, Tuple, Dict

import requests
import streamlit as st
from streamlit.runtime.secrets import StreamlitSecretNotFoundError


# =========================
# 1) CONFIG & AUTH
# =========================

def get_secret(key: str, default: str = "") -> str:
    """
    Try Streamlit secrets.toml first, fall back to environment variables.
    Works both on Streamlit Cloud and on Render.
    """
    try:
        return st.secrets[key]
    except (KeyError, StreamlitSecretNotFoundError):
        return os.getenv(key, default)

ELEVEN_API_KEY = get_secret("ELEVEN_API_KEY")
APP_USER = get_secret("APP_USER", "team")
APP_PASS = get_secret("APP_PASS", "strong_password")

if not ELEVEN_API_KEY:
    st.error("ELEVEN_API_KEY is not set. Add it in Render Environment or Streamlit secrets.")
    st.stop()

# Simple in-app login
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
                st.rerun()
            else:
                st.error("Invalid credentials")
    st.stop()

# Fetch subscription tier (cached in session state)
def get_subscription_tier():
    url = "https://api.elevenlabs.io/v1/user/subscription"
    headers = {"xi-api-key": ELEVEN_API_KEY}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            return data.get("tier", "unknown").lower()
        else:
            return "unknown"
    except Exception:
        return "unknown"

if "subscription_tier" not in st.session_state:
    st.session_state["subscription_tier"] = get_subscription_tier()

tier = st.session_state["subscription_tier"]
supports_pcm = tier in ["pro", "scale", "business", "enterprise"]


# =========================
# 2) DOMAIN DATA
# =========================

CELINE_VOICES: Dict[str, Dict] = {
    # French
    "fr_corentin": {
        "display": "Michiel",
        "id": "IHngRooVccHyPqB4uQkG",
        "settings": {"similarity_boost": 0.0, "stability": 0.5, "style": 0.0, "use_speaker_boost": False},
        "model_id": "eleven_multilingual_sts_v2",
        "lang": "French",
    },
    "fr_alexis": {
        "display": "Abel",
        "id": "oEfxSRLn5LTuBsthD6tN",
        "settings": {"similarity_boost": 0.0, "stability": 0.5, "style": 0.0, "use_speaker_boost": False},
        "model_id": "eleven_multilingual_sts_v2",
        "lang": "French",
    },
    "fr_alexandre_boutin": {
        "display": "Koen",
        "id": "IPgYtHTNLjC7Bq7IPHrm",
        "settings": {"similarity_boost": 0.0, "stability": 0.5, "style": 0.0, "use_speaker_boost": False},
        "model_id": "eleven_multilingual_sts_v2",
        "lang": "French",
    },
    "fr_Dmitry": {
        "display": "Martijn",
        "id": "kwajW3Xh5svCeKU5ky2S",
        "settings": {"similarity_boost": 0.0, "stability": 0.5, "style": 0.0, "use_speaker_boost": False},
        "model_id": "eleven_multilingual_sts_v2",
        "lang": "French",
    },

    # German
    "de_ben": {
        "display": "Michiel",
        "id": "aTTiK3YzK3dXETpuDE2h",
        "settings": {"similarity_boost": 0.0, "stability": 0.5, "style": 0.0, "use_speaker_boost": False},
        "model_id": "eleven_multilingual_sts_v2",
        "lang": "German",
    },
    "de_juan_schubert": {
        "display": "Abel",
        "id": "lx8LAX2EUAKftVz0Dk5z",
        "settings": {"similarity_boost": 0.0, "stability": 0.5, "style": 0.0, "use_speaker_boost": False},
        "model_id": "eleven_multilingual_sts_v2",
        "lang": "German",
    },
    "de_stefan_sport": {
        "display": "Martijn",
        "id": "ElaIVWtKNkyhZOf2vCbL",
        "settings": {"similarity_boost": 0.0, "stability": 0.5, "style": 0.0, "use_speaker_boost": False},
        "model_id": "eleven_multilingual_sts_v2",
        "lang": "German",
    },
    "de_Reeloverlay": {
        "display": "Koen",
        "id": "OukEAqLfTzpM37uFE5LT",
        "settings": {"similarity_boost": 0.0, "stability": 0.5, "style": 0.0, "use_speaker_boost": False},
        "model_id": "eleven_multilingual_sts_v2",
        "lang": "German",
    },

    # Italian
    "it_piero_italia": {
        "display": "Michiel",
        "id": "slEjHpiFudesZaivDTNt",
        "settings": {"similarity_boost": 0.0, "stability": 0.5, "style": 0.0, "use_speaker_boost": False},
        "model_id": "eleven_multilingual_sts_v2",
        "lang": "Italian",
    },
    "it_salvo_caruso": {
        "display": "Abel",
        "id": "mJSddcekWUkB3BOnjPFb",
        "settings": {"similarity_boost": 0.0, "stability": 0.5, "style": 0.0, "use_speaker_boost": False},
        "model_id": "eleven_multilingual_sts_v2",
        "lang": "Italian",
    },
    "it_voce_minatore_audiolibro": {
        "display": "Koen",
        "id": "F9w7aaEjfT09qV89OdY8",
        "settings": {"similarity_boost": 0.0, "stability": 0.5, "style": 0.0, "use_speaker_boost": False},
        "model_id": "eleven_multilingual_sts_v2",
        "lang": "Italian",
    },
    "it_ricasco": {
        "display": "Martijn",
        "id": "G1QO6RfZl0zS1DpKDReq",
        "settings": {"similarity_boost": 0.0, "stability": 0.5, "style": 0.0, "use_speaker_boost": False},
        "model_id": "eleven_multilingual_sts_v2",
        "lang": "Italian",
    },

    # Korean
    "ko_kkc_shorts": {
        "display": "Michiel",
        "id": "mgugV8tLa3KQE4mfYTw5",
        "settings": {"similarity_boost": 0.0, "stability": 0.5, "style": 0.0, "use_speaker_boost": False},
        "model_id": "eleven_multilingual_sts_v2",
        "lang": "Korean",
    },
    "ko_min_ho": {
        "display": "Abel",
        "id": "U1cJYS4EdbaHmfR7YzHd",
        "settings": {"similarity_boost": 0.0, "stability": 0.5, "style": 0.0, "use_speaker_boost": False},
        "model_id": "eleven_multilingual_sts_v2",
        "lang": "Korean",
    },
    "ko_taemin": {
        "display": "Koen",
        "id": "Ir7oQcBXWiq4oFGROCfj",
        "settings": {"similarity_boost": 0.0, "stability": 0.5, "style": 0.0, "use_speaker_boost": False},
        "model_id": "eleven_multilingual_sts_v2",
        "lang": "Korean",
    },
    "ko_joonpark": {
        "display": "Martijn",
        "id": "7Nah3cbXKVmGX7gQUuwz",
        "settings": {"similarity_boost": 0.0, "stability": 0.5, "style": 0.0, "use_speaker_boost": False},
        "model_id": "eleven_multilingual_sts_v2",
        "lang": "Korean",
    },

    # Polish
    "pl_krzysiek": {
        "display": "Michiel",
        "id": "ZUdFQHf8lAj4o7hiHvbE",
        "settings": {"similarity_boost": 0.0, "stability": 0.5, "style": 0.0, "use_speaker_boost": False},
        "model_id": "eleven_multilingual_sts_v2",
        "lang": "Polish",
    },
    "pl_tomasz_kowalsky": {
        "display": "Abel",
        "id": "JWUOwsYG4XgR9Od3eeon",
        "settings": {"similarity_boost": 0.0, "stability": 0.5, "style": 0.0, "use_speaker_boost": False},
        "model_id": "eleven_multilingual_sts_v2",
        "lang": "Polish",
    },
    "pl_piotr_pro_lp": {
        "display": "Koen",
        "id": "gFl0NeqphJUaoBLtWrqM",
        "settings": {"similarity_boost": 0.0, "stability": 0.5, "style": 0.0, "use_speaker_boost": False},
        "model_id": "eleven_multilingual_sts_v2",
        "lang": "Polish",
    },
    "pl_konwersacyjny_kalmil": {
        "display": "Martijn",
        "id": "mr1ubFaLs5xVrh1EqWtc",
        "settings": {"similarity_boost": 0.0, "stability": 0.5, "style": 0.0, "use_speaker_boost": False},
        "model_id": "eleven_multilingual_sts_v2",
        "lang": "Polish",
    },

    # Tamil
    "ta_maneesh": {
        "display": "Michiel",
        "id": "pTM0m0egrCpo5i9b1gpo",
        "settings": {"similarity_boost": 0.0, "stability": 0.5, "style": 0.0, "use_speaker_boost": False},
        "model_id": "eleven_multilingual_sts_v2",
        "lang": "Tamil",
    },
    "ta_bhuvan": {
        "display": "Abel",
        "id": "9Ats6C5UrhVXzgyVbnh3",
        "settings": {"similarity_boost": 0.0, "stability": 0.5, "style": 0.0, "use_speaker_boost": False},
        "model_id": "eleven_multilingual_sts_v2",
        "lang": "Tamil",
    },
    "ta_ramaa": {
        "display": "Koen",
        "id": "8J24wCDJGSNy9xjbiMla",
        "settings": {"similarity_boost": 0.0, "stability": 0.5, "style": 0.0, "use_speaker_boost": False},
        "model_id": "eleven_multilingual_sts_v2",
        "lang": "Tamil",
    },
    "ta_kathiravan": {
        "display": "Martijn",
        "id": "oJtqFwbHKS0pFD03MNRd",
        "settings": {"similarity_boost": 0.0, "stability": 0.5, "style": 0.0, "use_speaker_boost": False},
        "model_id": "eleven_multilingual_sts_v2",
        "lang": "Tamil",
    },

    # Thai
    "th_michiel": {
        "display": "Michiel",
        "id": "D0zfVvTrOu5S1yl4OIwg",
        "settings": {"similarity_boost": 0.0, "stability": 0.5, "style": 0.0, "use_speaker_boost": False},
        "model_id": "eleven_multilingual_sts_v2",
        "lang": "Thai",
    },
    "th_young_male1": {
        "display": "Abel",
        "id": "VEx62MzkotIbEtPQV0Uc",
        "settings": {"similarity_boost": 0.0, "stability": 0.5, "style": 0.0, "use_speaker_boost": False},
        "model_id": "eleven_multilingual_sts_v2",
        "lang": "Thai",
    },
    "th_young_male2": {
        "display": "Koen",
        "id": "VEx62MzkotIbEtPQV0Uc",
        "settings": {"similarity_boost": 0.0, "stability": 0.5, "style": 0.0, "use_speaker_boost": False},
        "model_id": "eleven_multilingual_sts_v2",
        "lang": "Thai",
    },
    "th_young_male3": {
        "display": "Martijn",
        "id": "VEx62MzkotIbEtPQV0Uc",
        "settings": {"similarity_boost": 0.0, "stability": 0.5, "style": 0.0, "use_speaker_boost": False},
        "model_id": "eleven_multilingual_sts_v2",
        "lang": "Thai",
    },
}

CELINE_SECTIONS = [
    ("French",  ["fr_corentin", "fr_alexis", "fr_alexandre_boutin", "fr_Dmitry"]),
    ("German",  ["de_ben", "de_juan_schubert", "de_stefan_sport", "de_Reeloverlay"]),
    ("Italian", ["it_piero_italia", "it_salvo_caruso", "it_voce_minatore_audiolibro", "it_ricasco"]),
    ("Korean",  ["ko_kkc_shorts", "ko_min_ho", "ko_taemin", "ko_joonpark"]),
    ("Polish",  ["pl_krzysiek", "pl_tomasz_kowalsky", "pl_piotr_pro_lp", "pl_konwersacyjny_kalmil"]),
    ("Tamil",   ["ta_maneesh", "ta_bhuvan", "ta_ramaa", "ta_kathiravan"]),
    ("Thai",    ["th_michiel", "th_young_male1", "th_young_male2", "th_young_male3"]),
]

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
    if not ct:
        return ".audio"
    s = ct.lower()
    if "mpeg" in s:
        return ".mp3"
    if "wav" in s or "x-wav" in s:
        return ".wav"
    if "ogg" in s:
        return ".ogg"
    if "flac" in s:
        return ".flac"
    return ".audio"

def _ext_from_ct_or_fallback(ct: str, desired: str) -> str:
    """
    Prefer the server-declared content-type when it's clearly mp3 or wav.
    Otherwise, use the user-selected desired extension.
    """
    s = (ct or "").lower()
    if "mpeg" in s:
        return ".mp3"
    if "wav" in s or "x-wav" in s:
        return ".wav"
    return desired

def _build_url(voice_id: str, output_format: str) -> str:
    base = f"https://api.elevenlabs.io/v1/speech-to-speech/{voice_id}"
    return f"{base}?output_format={output_format}"

def convert_one(file_bytes: bytes, filename: str, mime: str, voice_cfg: Dict, output_format: str) -> Tuple[bytes, str]:
    """
    Convert a single file via ElevenLabs STS. Sends output_format as a QUERY PARAM.
    """
    headers = {"xi-api-key": ELEVEN_API_KEY}
    files = {"audio": (filename, io.BytesIO(file_bytes), mime or "application/octet-stream")}
    data = {
        "voice_settings": json.dumps(voice_cfg["settings"]),
        "model_id": voice_cfg.get("model_id", "eleven_multilingual_sts_v2"),
    }

    url = _build_url(voice_cfg["id"], output_format)
    r = requests.post(url, headers=headers, files=files, data=data, timeout=300)
    if r.status_code != 200:
        raise RuntimeError(f"{r.status_code}: {r.text}")

    out_bytes = r.content
    returned_ct = r.headers.get("content-type", "application/octet-stream")

    # If PCM was requested and we didn't get MP3 back, assume raw PCM and add WAV header
    if output_format.startswith("pcm_") and "mpeg" not in returned_ct.lower():
        try:
            # Parse sample rate from output_format (e.g., "pcm_44100" -> 44100)
            sample_rate = int(output_format.split("_")[1])
        except ValueError:
            sample_rate = 44100  # Fallback
        channels = 1  # Mono (standard for Eleven Labs outputs)
        sampwidth = 2  # 16-bit

        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(sampwidth)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(out_bytes)
        out_bytes = wav_buffer.getvalue()
        ct = "audio/wav"
    else:
        ct = returned_ct

    return out_bytes, ct

def convert_batch(files: List[Tuple[bytes, str, str]], voice_cfg: Dict, output_format: str, default_ext: str, keep_original_name: bool, debug: bool=False) -> bytes:
    """
    Convert multiple files and package them into a ZIP.
    Uses server Content-Type to guess extension; falls back to default_ext.
    """
    buf = io.BytesIO()
    errors = []
    suffix = "" if keep_original_name else "_converted"
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_bytes, filename, mime in files:
            base = os.path.splitext(filename)[0] or "file"
            try:
                out_bytes, ct = convert_one(file_bytes, filename, mime, voice_cfg, output_format)
                ext = _ext_from_ct_or_fallback(ct, default_ext)
                zf.writestr(f"{base}{suffix}{ext}", out_bytes)
                if debug:
                    zf.writestr(f"_debug_{base}.txt", f"requested={output_format}\ncontent_type={ct}\nresolved_ext={ext}\n")
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
    meta = CREATORS[creator_key]
    sections = meta["sections"]
    tabs = st.tabs([title for title, _ in sections])

    for i, (title, voice_keys) in enumerate(sections):
        with tabs[i]:
            st.subheader(title)
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
            if st.button(f"Use '{display_label}' for uploads", key=f"use_{creator_key}_{title}"):
                st.session_state[f"selected_section_{creator_key}"] = title
                st.session_state[f"selected_voice_{creator_key}"] = display_to_key[display_label]

    chosen_section = st.session_state.get(f"selected_section_{creator_key}", sections[0][0])
    chosen_voice = st.session_state.get(f"selected_voice_{creator_key}", sections[0][1][0])
    st.info(f"Active section: **{chosen_section}** · Active voice: **{meta['voices'][chosen_voice]['display']}**")
    return chosen_section, chosen_voice


# =========================
# 5) MAIN UI  (drop-in replacement with filename toggle)
# =========================

st.title("Voice Converter")
creator_key = sidebar_creator_picker()
creator = CREATORS[creator_key]

st.header(creator["display"])
section_title, voice_key = section_voice_picker(creator_key)
voice_cfg = creator["voices"][voice_key]

st.markdown("---")
st.subheader("Upload audio files")

# --- Rolling key to allow clearing the uploader safely ---
if "uploader_key" not in st.session_state:
    st.session_state["uploader_key"] = 0

def clear_all_uploads():
    # Force the file_uploader to reset by changing its key
    st.session_state["uploader_key"] += 1
    # rerun() inside callback is optional — Streamlit reruns automatically
    st.rerun()

uploaded = st.file_uploader(
    "Drop or pick 1+ audio files",
    type=None,
    accept_multiple_files=True,
    key=f"uploader_{st.session_state['uploader_key']}",  # dynamic key resets widget cleanly
    help="You can upload a single file (returns one audio) or multiple files (returns a ZIP).",
)

# --- Output format selector ---
st.subheader("Output format")

# Map UI label -> ElevenLabs output_format string and preferred file extension
OUTPUT_FORMAT_MAP = {
    ".mp3 (44.1 kHz / 128 kbps)": ("mp3_44100_128", ".mp3"),
    ".wav (44.1 kHz PCM)": ("pcm_44100", ".wav"),
}

available_formats = [k for k in OUTPUT_FORMAT_MAP if supports_pcm or ".mp3" in k]

fmt = st.radio(
    "Choose the format for the converted audio",
    options=available_formats,
    horizontal=True,
    key="out_fmt",
)

if not supports_pcm and tier != "unknown":
    st.warning(f"Your ElevenLabs subscription ({tier.capitalize()}) does not support WAV (PCM) output. Defaulting to MP3. Upgrade to Pro or higher to enable WAV.")
elif tier == "unknown":
    st.warning("Could not determine your ElevenLabs subscription tier. WAV output may not be available. If issues occur, check your plan and try again.")

chosen_output_format, chosen_ext = OUTPUT_FORMAT_MAP[fmt]

# --- Checkbox: keep original filename or add "_converted" ---
keep_original_name = st.checkbox(
    "Keep original filename",
    value=False,
    help="If checked, the converted file will keep the same name as the original file.",
)

# --- Debug panel ---
debug_mode = st.checkbox("Show debug info", value=False, help="Print request/response details")

def _debug(msg: str):
    if debug_mode:
        st.write(msg)

if uploaded:
    st.write("Files selected:")
    for f in uploaded:
        st.write(f"- `{f.name}` ({f.type or 'application/octet-stream'})")

    c1, c2 = st.columns([1, 1])
    convert_clicked = c1.button("Convert", use_container_width=True)
    c2.button("Clear all", type="secondary", on_click=clear_all_uploads, use_container_width=True)

    if convert_clicked:
        try:
            if len(uploaded) == 1:
                f = uploaded[0]
                with st.spinner("Converting..."):
                    out_bytes, ct = convert_one(f.read(), f.name, f.type, voice_cfg, chosen_output_format)

                ext = _ext_from_ct_or_fallback(ct, chosen_ext)
                base_name = os.path.splitext(f.name)[0]
                out_name = f"{base_name}{ext}" if keep_original_name else f"{base_name}_converted{ext}"

                _debug(f"Requested output_format={chosen_output_format}, response Content-Type={ct}, resolved_ext={ext}")

                # Warn if user asked for WAV but API still returned MP3
                if chosen_ext == ".wav" and "mpeg" in (ct or "").lower():
                    st.warning("You selected WAV (PCM), but the API returned MP3. "
                               "This can happen if your ElevenLabs plan does not include PCM/WAV output. Please upgrade your subscription.")

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
                    zip_bytes = convert_batch(files, voice_cfg, chosen_output_format, chosen_ext, keep_original_name, debug=debug_mode)

                stamp = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
                suffix = "" if keep_original_name else "_converted"
                zip_name = f"{creator_key}_{voice_key}{suffix}_{stamp}.zip"

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
st.caption("NOTE: No uploads are stored; results are returned directly.")
