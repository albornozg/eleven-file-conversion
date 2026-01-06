# Global constants for the app

OUTPUT_FORMAT_MAP = {
    ".mp3 (44.1 kHz / 128 kbps)": ("mp3_44100_128", ".mp3"),
    ".wav (44.1 kHz PCM)": ("pcm_44100", ".wav"),
}

# Define max batch size (adjust based on testing; start conservative)
MAX_BATCH_BYTES = 200 * 1024 * 1024  # 200 MB safe limit for inputs
