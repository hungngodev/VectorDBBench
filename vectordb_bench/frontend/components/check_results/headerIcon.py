from vectordb_bench.frontend.config.styles import HEADER_ICON
import base64
from pathlib import Path
from PIL import Image
from io import BytesIO


def drawHeaderIcon(st):
    # Load logo - convert local image to base64
    logo_src = HEADER_ICON
    if not HEADER_ICON.startswith("http"):
        try:
            # Path is relative to vectordb_bench package directory
            package_dir = Path(__file__).parent.parent.parent.parent  # Up to vectordb_bench/
            logo_path = package_dir / HEADER_ICON
            
            img = Image.open(logo_path)
            buffered = BytesIO()
            img.save(buffered, format="PNG")
            logo_src = f"data:image/png;base64,{base64.b64encode(buffered.getvalue()).decode()}"
        except Exception as e:
            # Fallback to original if loading fails
            logo_src = HEADER_ICON
    
    st.markdown(
        f"""
    <a href="/vdbbench" target="_self" style="text-decoration: none;">
        <div class="headerIconContainer">
            <img src="{logo_src}" class="headerLogo" alt="VDBBench">
            <span class="headerEdition">UMass Edition</span>
        </div>
    </a>

    <style>
    .headerIconContainer {{
        position: relative;
        top: 0px;
        height: 50px;
        width: 100%;
        border-bottom: 2px solid #881c1c;
        display: flex;
        align-items: center;
        gap: 10px;
        cursor: pointer;
        padding-left: 5px;
    }}
    .headerLogo {{
        height: 40px;
        width: auto;
    }}
    .headerText {{
        font-size: 24px;
        font-weight: 600;
        color: #333;
    }}
    .headerEdition {{
        font-size: 16px;
        font-weight: 500;
        color: #881c1c;
        background-color: rgba(136, 28, 28, 0.1);
        padding: 2px 8px;
        border-radius: 4px;
        border: 1px solid #881c1c;
    }}
    </style>
    """,
        unsafe_allow_html=True,
    )
