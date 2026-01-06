import streamlit as st
from typing import Tuple

def sidebar_creator_picker(creators) -> str:
    st.sidebar.title("Creators")
    choices = {meta["display"]: key for key, meta in creators.items()}
    label = st.sidebar.selectbox("Choose a creator", list(choices.keys()))
    return choices[label]

def section_voice_picker(creator_key: str, creators) -> Tuple[str, str]:
    meta = creators[creator_key]
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

def clear_all_uploads():
    # Force the file_uploader to reset by changing its key
    st.session_state["uploader_key"] += 1
    # rerun() inside callback is optional — Streamlit reruns automatically
    st.rerun()
