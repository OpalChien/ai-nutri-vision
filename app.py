import streamlit as st
from google import genai
from google.genai import types
from PIL import Image
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import io

# --- 1. 安全配置 ---
# 這裡改用 Streamlit 的 Secrets 功能，不要直接寫死字串
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
    client = genai.Client(api_key=API_KEY)
except Exception:
    st.error("請在 Streamlit Secrets 中設定 GOOGLE_API_KEY")
    st.stop()

# 旗艦模型順位
MODEL_PRIORITY = ["gemini-3-flash-preview", "gemini-2.5-flash", "gemini-1.5-flash"]

st.set_page_config(page_title="專業 AI 臨床營養師", layout="wide")

# --- 2. 核心分析邏輯 ---
def get_nutrition_analysis(image_bytes, mode):
    prompt = f"""
    你是一位臨床營養師。請分析照片食物並參考 USDA 標準。
    辨識比例尺推算克數。分析模式：{mode}。
    嚴格回傳純 JSON：
    {{
      "items": [{{"食材": "名稱", "重量_g": 0, "kcal": 0, "pro_g": 0, "Na_mg": 0, "K_mg": 0, "P_mg": 0}}],
      "total": {{"kcal": 0, "pro_g": 0, "Na_mg": 0, "K_mg": 0, "P_mg": 0}},
      "health_score": 85,
      "clinical_advice": "建議"
    }}
    """
    for model_id in MODEL_PRIORITY:
        try:
            response = client.models.generate_content(
                model=model_id,
                contents=[prompt, types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")]
            )
            res_text = response.text.strip()
            start = res_text.find("{")
            end = res_text.rfind("}") + 1
            return json.loads(res_text[start:end]), model_id
        except Exception as e:
            if "429" in str(e): continue
            else: raise e

# --- 3. UI 介面 ---
st.title("🍎 NutriVision AI 臨床級分析")

with st.sidebar:
    mode = st.selectbox("分析重點", ["一般健康", "腎友模式 (低鈉/鉀/磷)", "增肌減脂"])

uploaded_file = st.file_uploader("📸 上傳食物照片", type=["jpg", "jpeg", "png"])

if uploaded_file:
    img = Image.open(uploaded_file)
    if st.button("🚀 啟動 AI 深度掃描", width='stretch'):
        buf = io.BytesIO()
        img.save(buf, format='JPEG')
        try:
            data, used_model = get_nutrition_analysis(buf.getvalue(), mode)
            st.success(f"辨識完成 (Model: {used_model})")
            
            # 儀表板顯示
            col1, col2, col3 = st.columns(3)
            col1.metric("總熱量", f"{data['total']['kcal']} kcal")
            col2.metric("蛋白質", f"{data['total']['pro_g']} g")
            col3.metric("健康評分", f"{data['health_score']}")

            st.write("📋 **USDA 數據明細**")
            st.dataframe(pd.DataFrame(data['items']), width='stretch')
            st.info(f"💡 **營養師建議：** {data['clinical_advice']}")
        except Exception as e:
            st.error(f"分析失敗：{e}")
