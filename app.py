import datetime
import resource
import streamlit as st

from config import ELEVEN_API_KEY, authenticate, get_tier, supports_pcm_func
from data import CREATORS
from client import convert_one, convert_batch, _ext_from_ct_or_fallback
from utils import sidebar_creator_picker, section_voice_picker, clear_all_uploads
from constants import OUTPUT_FORMAT_MAP, MAX_BATCH_BYTES

if not ELEVEN_API_KEY:
    st.error("ELEVEN_API_KEY is not set. Add it in Render Environment or Streamlit secrets.")
    st.stop()

authenticate()

tier = get_tier()
supports_pcm = supports_pcm_func(tier)

st.title("Voice Converter")
creator_key = sidebar_creator_picker(CREATORS)
creator = CREATORS[creator_key]

st.header(creator["display"])
section_title, voice_key = section_voice_picker(creator_key, CREATORS)
voice_cfg = creator["voices"][voice_key]

st.markdown("---")
st.subheader("Upload audio files")

# --- Rolling key to allow clearing the uploader safely ---
if "uploader_key" not in st.session_state:
    st.session_state["uploader_key"] = 0

uploaded = st.file_uploader(
    "Drop or pick 1+ audio files",
    type=None,
    accept_multiple_files=True,
    key=f"uploader_{st.session_state['uploader_key']}",  # dynamic key resets widget cleanly
    help="You can upload a single file (returns one audio) or multiple files (returns a ZIP).",
)

# --- Output format selector ---
st.subheader("Output format")

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
    # Calculate total batch size before processing
    total_size = sum(f.size for f in uploaded)  # in bytes
    if total_size > MAX_BATCH_BYTES:
        st.error(f"Batch too large ({total_size / 1024 / 1024:.2f} MB). Max allowed: {MAX_BATCH_BYTES / 1024 / 1024} MB to avoid memory crashes. Reduce files or try smaller ones.")
    else:
        st.write("Files selected:")
        for f in uploaded:
            st.write(f"- `{f.name}` ({f.type or 'application/octet-stream'}) ({f.size / 1024 / 1024:.2f} MB)")

        c1, c2 = st.columns([1, 1])
        convert_clicked = c1.button("Convert", use_container_width=True)
        c2.button("Clear all", type="secondary", on_click=clear_all_uploads, use_container_width=True)

        if convert_clicked:
            try:
                # Log starting memory (for debugging/tuning)
                if debug_mode:
                    start_mem = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024 / 1024
                    _debug(f"Starting memory usage: {start_mem:.2f} MB")

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

                # Log ending memory (for debugging/tuning)
                if debug_mode:
                    end_mem = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024 / 1024
                    _debug(f"Ending memory usage: {end_mem:.2f} MB")

            except Exception as e:
                st.error(f"Conversion error: {e}")

st.markdown("---")
st.caption("NOTE: No uploads are stored; results are returned directly.")
