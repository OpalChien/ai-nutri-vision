import streamlit as st
from google import genai
from google.genai import types
from PIL import Image
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import io

# --- 1. 核心配置 ---
API_KEY = "AIzaSyCO9IbkHhetykll8248OL28gOsj5VqVEE0"
client = genai.Client(api_key=API_KEY)

# 根據您可用的清單，設定最強的模型優先順序
MODEL_PRIORITY = [
    "gemini-3-flash-preview", 
    "gemini-2.5-flash", 
    "gemini-2.0-flash"
]

st.set_page_config(page_title="專業 AI 臨床營養師", layout="wide")

# --- 2. 側邊欄：功能設定 ---
with st.sidebar:
    st.header("🏥 臨床模式設定")
    # 考量到您正在進行的 ADPKD/CKD 專案
    mode = st.selectbox("分析重點", ["一般健康管理", "腎友模式 (低鈉/低鉀/低磷)", "增肌減脂 (高蛋白)"])
    st.divider()
    st.markdown("""
    **💡 專業小撇步：**
    拍攝時在盤子旁放一個**手掌**、**湯匙**或**原子筆**，AI 會根據其比例更精準地推算食物克數。
    """)
    st.image("https://img.icons8.com/clouds/100/000000/healthy-food.png", width=100)

# --- 3. 核心功能：自動切換模型與深度辨識 ---
def get_nutrition_analysis(image_bytes):
    # 這是最強的 Prompt 工程，確保符合 USDA 並精準計算電解質
    prompt = f"""
    你是一位具備頂尖多模態視覺能力的臨床註冊營養師。請分析照片中的食物並參考 USDA 標準。
    
    分析規範：
    1. 識別照片中的比例尺（如餐具、手掌）來精確推算食材重量(g)。
    2. 目前模式為：『{mode}』。
    3. 嚴格以「純 JSON 格式」回傳，不含 Markdown 標籤。
    
    JSON 結構：
    {{
      "items": [
        {{"食材": "名稱", "重量_g": 100, "熱量_kcal": 150, "蛋白質_g": 10, "脂肪_g": 5, "碳水_g": 20, "鈉_mg": 50, "鉀_mg": 150, "磷_mg": 100}}
      ],
      "total": {{"熱量": 0, "蛋白質": 0, "鈉": 0, "鉀": 0, "磷": 0}},
      "health_score": 85,
      "clinical_advice": "專業評語"
    }}
    """
    
    last_err = None
    for model_id in MODEL_PRIORITY:
        try:
            response = client.models.generate_content(
                model=model_id,
                contents=[prompt, types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")]
            )
            res_text = response.text.strip()
            # 提取 JSON 內容
            start = res_text.find("{")
            end = res_text.rfind("}") + 1
            return json.loads(res_text[start:end]), model_id
        except Exception as e:
            last_err = e
            if "429" in str(e): # 額度滿了換下一個
                continue
            else:
                break
    raise last_err

# --- 4. 前端 UI ---
st.title("🍎 NutriVision AI 專業臨床掃描")
st.caption(f"目前權限已啟動：{', '.join(MODEL_PRIORITY)}")

uploaded_file = st.file_uploader("📸 拍攝或上傳食物照片", type=["jpg", "jpeg", "png"])

if uploaded_file:
    img = Image.open(uploaded_file)
    col1, col2 = st.columns([1, 1.3])
    
    with col1:
        st.image(img, width='stretch', caption="上傳的餐點")
    
    if st.button("🚀 啟動深度營養分析", width='stretch'):
        buf = io.BytesIO()
        img.save(buf, format='JPEG')
        
        try:
            with st.spinner("正在調度旗艦級模型並檢索 USDA 數據..."):
                data, used_model = get_nutrition_analysis(buf.getvalue())
                
                with col2:
                    st.success(f"辨識完成！ (調度模型: {used_model})")
                    
                    # 數據指標卡片
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("總熱量", f"{data['total']['熱量']} kcal")
                    m2.metric("蛋白質", f"{data['total']['蛋白質']} g")
                    m3.metric("鈉 (Na)", f"{data['total']['鈉']} mg")
                    m4.metric("評分", f"{data['health_score']}/100")

                    # 腎友專屬圖表 (鉀與磷)
                    c1, c2 = st.columns(2)
                    with c1:
                        fig_k = go.Figure(go.Indicator(
                            mode = "gauge+number", value = data['total']['鉀'],
                            title = {'text': "鉀 (K) mg"},
                            gauge = {'axis': {'range': [0, 1000]}, 'bar': {'color': "#FFA500"}}))
                        fig_k.update_layout(height=280, margin=dict(t=50, b=0))
                        st.plotly_chart(fig_k, width='stretch')
                    with c2:
                        fig_p = go.Figure(go.Indicator(
                            mode = "gauge+number", value = data['total']['磷'],
                            title = {'text': "磷 (P) mg"},
                            gauge = {'axis': {'range': [0, 800]}, 'bar': {'color': "#FF4B4B"}}))
                        fig_p.update_layout(height=280, margin=dict(t=50, b=0))
                        st.plotly_chart(fig_p, width='stretch')

                    # 詳細成分明細
                    st.markdown("### 📋 USDA 完整數據清單")
                    st.dataframe(pd.DataFrame(data['items']), width='stretch')
                    
                    st.info(f"💡 **營養師建議：**\n{data['clinical_advice']}")
                    
        except Exception as e:
            st.error(f"分析失敗：{e}")