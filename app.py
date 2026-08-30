import streamlit as st
import os
from create_sample import create_sample
from create_template import create_template
from create_sim_template import create_sim_template

SAMPLE_PATH = "sample_data/ornek_veri.xlsx"
TEMPLATE_PATH = "sample_data/sablon.xlsx"
SIM_TEMPLATE_PATH = "sample_data/simulasyon_sablon.xlsx"

@st.cache_resource
def _init_files():
    os.makedirs("sample_data", exist_ok=True)
    if not os.path.exists(SAMPLE_PATH):
        create_sample(SAMPLE_PATH)
    create_template(TEMPLATE_PATH)
    create_sim_template(SIM_TEMPLATE_PATH)

_init_files()

st.set_page_config(
    page_title="Portföy Destek Optimizasyonu",
    page_icon="🏦",
    layout="wide",
    menu_items={"Get Help": None, "Report a bug": None, "About": None},
)

st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    header [data-testid="stToolbar"] {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

st.title("Portföy Destek Dağıtım Optimizasyonu")
st.markdown("""
Soldan sayfa seçin:

- **Optimizasyon** — veri yükle, parametre ayarla, optimize et
- **Simülasyon Analizi** — optimizasyon öncesi ve sonrası gerçek performansı karşılaştır
""")
