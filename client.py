import io
import os
import json
import zipfile
import datetime
import wave
from typing import List, Tuple, Dict

import requests

from config import ELEVEN_API_KEY

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
