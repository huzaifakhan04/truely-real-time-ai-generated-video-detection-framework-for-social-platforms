import streamlit as st
import tempfile
import os
from model import run

def main():
    st.set_page_config(page_title="AI-Generated Video Detection Tool", layout="wide")
    st.title("AI-Generated Video Detection Tool")
    st.markdown("""
    Upload a video to detect if it contains AI-generated content.
    The system will analyze facial consistency and provide a detection score.
    """)
    uploaded_file = st.file_uploader("Choose a video file", type=["mp4", "avi", "mov", "mkv"])
    if uploaded_file is not None:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_file:
            tmp_file.write(uploaded_file.read())
            input_path = tmp_file.name
        output_path = input_path.replace(".mp4", "_output.mp4")
        with st.spinner("Processing video..."):
            fake_score = run(input_path, output_path)
            st.subheader("Detection Results")
            column_one, column_two = st.columns(2)
            with column_one:
                if fake_score > 50:
                    st.error(f"⚠️ This video is likely fake ({fake_score}% confidence)")
                else:
                    st.success(f"✅ This video is likely real ({100-fake_score}% confidence)")
                st.markdown("""
                ### How it works:
                - The system analyzes facial consistency between frames.
                - Sudden changes in facial features indicate potential AI manipulation.
                - The detection score is based on the number of frames flagged as suspicious.
                - A score above 50% suggests a high likelihood of AI-generated content.
                - Red bounding boxes highlight frames flagged as suspicious.
                """)
            with column_two:
                st.video(output_path)
        os.unlink(input_path)

if __name__ == "__main__":
    main()