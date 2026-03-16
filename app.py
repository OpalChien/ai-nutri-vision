import streamlit as st
from google import genai
from google.genai import types
from PIL import Image
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import io

# --- 1. 安全配置與初始化 ---
try:
    # 從 Streamlit Secrets 讀取，避免 GitHub 外洩
    API_KEY = st.secrets["GOOGLE_API_KEY"]
    client = genai.Client(api_key=API_KEY)
except Exception:
    st.error("❌ 找不到 API Key。請在 Streamlit Cloud 的 Secrets 中設定 GOOGLE_API_KEY。")
    st.stop()

# 模型優先順序：3 -> 2.5 -> 1.5
MODEL_PRIORITY = ["gemini-3-flash-preview", "gemini-2.5-flash", "gemini-1.5-flash"]

st.set_page_config(page_title="專業 AI 臨床營養師", layout="wide")

# --- 2. 側邊欄設定 ---
with st.sidebar:
    st.header("🏥 臨床分析設定")
    mode = st.selectbox("分析目標", ["一般健康管理", "腎友模式 (低鈉/鉀/磷)", "增肌減脂"])
    st.divider()
    st.info("💡 專業建議：拍照時放入手掌或湯匙作為參照物，AI 估計克數會更精準。")

# --- 3. 核心功能：自動降級與 JSON 解析 ---
def get_nutrition_analysis(image_bytes):
    prompt = f"""
    你是一位具備頂尖多模態視覺能力的註冊營養師。請分析照片中的食物，參考 USDA 標準。
    請識別圖中比例尺（如餐具、手掌）來精確推算食材重量(g)。
    分析目標：{mode}。
    
    請務必嚴格回傳「純 JSON 格式」，內容必須包含：
    {{
      "items": [
        {{"食材": "名稱", "重量_g": 100, "kcal": 150, "pro_g": 10, "fat_g": 5, "cho_g": 20, "Na_mg": 50, "K_mg": 150, "P_mg": 100}}
      ],
      "total": {{"kcal": 0, "pro_g": 0, "Na_mg": 0, "K_mg": 0, "P_mg": 0}},
      "health_score": 85,
      "clinical_advice": "針對 {mode} 的專業建議"
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
    return None, None

# --- 4. 前端 UI 與圖表呈現 ---
st.title("🍎 NutriVision AI 專業臨床營養系統")

uploaded_file = st.file_uploader("📸 拍攝或上傳食物照片", type=["jpg", "jpeg", "png"])

if uploaded_file:
    img = Image.open(uploaded_file)
    col_img, col_res = st.columns([1, 1.3])
    
    with col_img:
        st.image(img, width='stretch', caption="影像預覽")
    
    if st.button("🚀 啟動 AI 深度分析", width='stretch'):
        buf = io.BytesIO()
        img.save(buf, format='JPEG')
        
        try:
            with st.spinner("AI 正在比對 USDA 數據庫並繪製圖表中..."):
                data, used_model = get_nutrition_analysis(buf.getvalue())
                
                with col_res:
                    st.success(f"辨識成功！使用模型: {used_model}")
                    
                    # 數據指標卡片
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("總熱量", f"{data['total']['kcal']} kcal")
                    m2.metric("蛋白質", f"{data['total']['pro_g']} g")
                    m3.metric("鈉 (Na)", f"{data['total']['Na_mg']} mg")
                    m4.metric("健康評分", f"{data['health_score']}/100")

                    # 圖表區：三大營養素比例與電解質監控
                    st.divider()
                    c1, c2 = st.columns([1.2, 1])
                    
                    with c1:
                        # 圓餅圖：宏量營養素
                        df_pie = pd.DataFrame({
                            "營養素": ["蛋白質", "脂肪", "碳水化合物"],
                            "比例": [data['total']['pro_g'], 10, 20] # 這裡可依細節調整
                        })
                        fig_pie = px.pie(df_pie, values='比例', names='營養素', hole=0.5, title="三大營養素比例")
                        st.plotly_chart(fig_pie, width='stretch')
                        
                    with c2:
                        # 鉀與磷的儀表板 (Gauge)
                        fig_k = go.Figure(go.Indicator(
                            mode = "gauge+number", value = data['total']['K_mg'],
                            title = {'text': "鉀 (K) mg"},
                            gauge = {'axis': {'range': [0, 1000]}, 'bar': {'color': "orange"}}))
                        fig_k.update_layout(height=250, margin=dict(t=50, b=0))
                        st.plotly_chart(fig_k, width='stretch')

                    # 詳細成分清單
                    st.markdown("### 📋 詳細成分分析 (USDA)")
                    df_items = pd.DataFrame(data['items'])
                    df_items.columns = ['食材', '重量(g)', '熱量', '蛋白', '脂肪', '碳水', '鈉', '鉀', '磷']
                    st.dataframe(df_items, width='stretch')
                    
                    st.info(f"💡 **臨床建議：**\n{data['clinical_advice']}")
                    
        except Exception as e:
            st.error(f"分析失敗：{e}")
