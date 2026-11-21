# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import numpy as np
import io
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR&display=swap');
    html, body, [class*="css"] {
        font-family: 'Noto Sans KR', 'Malgun Gothic', sans-serif;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------- CSV 읽기 ----------
def read_csv(file):
    """인코딩을 자동으로 맞춰 CSV를 읽습니다 (utf-8-sig → cp949 순서)."""
    data = file.getvalue()
    for enc in ("utf-8-sig", "cp949"):
        try:
            return pd.read_csv(io.BytesIO(data), encoding=enc)
        except Exception:
            pass
    return pd.DataFrame()

# ---------- 열 이름 표준화 ----------
def std_cols(df):
    """학교마다 다른 열 이름을 표준 이름으로 통일합니다."""
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    rename = {}
    for c in df.columns:
        k = c.lower().replace(" ", "")
        if k in ("time", "categories", "시간", "날짜", "datetime", "date"):
            rename[c] = "time"
        elif k in ("temperature", "온도"):
            rename[c] = "temperature"
        elif k in ("humidity", "습도"):
            rename[c] = "humidity"
        elif k == "ph":
            rename[c] = "ph"
        elif k == "ec":
            rename[c] = "ec"
        elif "생중량" in k:
            rename[c] = "생중량"
        elif "잎" in k:
            rename[c] = "잎 수"
        elif "지상부" in k and "길이" in k:
            rename[c] = "지상부 길이"
        elif "지하부" in k and "길이" in k:
            rename[c] = "지하부 길이"
        elif "지상부" in k and ("질량" in k or "무게" in k):
            rename[c] = "지상부 질량"
        elif "지하부" in k and ("질량" in k or "무게" in k):
            rename[c] = "지하부 질량"
        elif "개체" in k:
            rename[c] = "개체번호"
    df = df.rename(columns=rename)

    for c in df.columns:
        if c in ("time", "개체번호"):
            continue
        if not pd.api.types.is_numeric_dtype(df[c]):
            num = pd.to_numeric(
                df[c].astype(str).str.replace(",", "").str.extract(r"(-?\d+\.?\d*)")[0],
                errors="coerce",
            )
            if num.notna().mean() >= 0.5:
                df[c] = num

    if "생중량" not in df.columns and {"지상부 질량", "지하부 질량"} <= set(df.columns):
        df["생중량"] = df["지상부 질량"] + df["지하부 질량"]

    if "time" in df.columns:
        t = df["time"].astype(str).str.strip()
        parsed = pd.to_datetime(t, errors="coerce", format="mixed")
        bad = parsed.isna() & t.str.match(r"^\d{8}_\d{1,2}$")
        if bad.any():
            parts = t[bad].str.split("_", expand=True)
            parsed[bad] = pd.to_datetime(parts[0], format="%Y%m%d") + pd.to_timedelta(parts[1].astype(int), unit="h")
        df["time"] = parsed
    return df

# ---------- 데이터 불러오기 ----------
@st.cache_data
def load_data(file):
    """CSV를 한 번만 읽어 표준화하고 결과를 저장합니다."""
    with st.spinner("CSV를 읽는 중..."):
        return std_cols(read_csv(file))

# ---------- 학교명 (파일명 앞부분에서 자동 추출) ----------
def get_school_name(file):
    """파일명 앞부분을 학교명으로 사용합니다. (하드코딩 금지)"""
    if file is None:
        return "우리 학교"
    return str(file.name).split("_")[0].replace(".csv", "").replace(".CSV", "")

env_file = st.sidebar.file_uploader("환경 CSV", type="csv")
growth_file = st.sidebar.file_uploader("생육 CSV", type="csv")

env_df = None
growth_df = None

if env_file is not None:
    env_df = load_data(env_file)
if growth_file is not None:
    growth_df = load_data(growth_file)

school_name = get_school_name(env_file) if env_file is not None else get_school_name(growth_file)

# ---------- 생육 측정 항목 선택 ----------
measure_cols = st.sidebar.multiselect(
    "생육 측정 항목 선택",
    ["잎 수", "지상부 길이", "지하부 길이", "생중량"],
    default=["잎 수", "지상부 길이", "지하부 길이", "생중량"],
)

tab1, tab2, tab3 = st.tabs(["📖 실험 소개", "📋 데이터 요약", "📊 결과 분석"])

with tab1:
    try:
        st.title("송도고등학교 그린 1팀 그린란드고추냉이의 생중량 차이 분석을 통한 지상부 길이와 지하부 길이의 상관관계 파악")
        st.header("🌱 실험 목적")
        st.write(
            "같은 스마트팜 환경에서 자라더라도 식물 개체마다 생중량 차이가 크게 나타나는지 확인하고, "
            "지상부 길이가 길수록 지하부 길이도 함께 길어지는지를 비교하기 위해 탐구합니다."
        )
        st.header("🔬 가설")
        st.write(
            "같은 스마트팜에서 재배해도 개체마다 생중량의 차이가 클 것이며, "
            "지상부 길이가 길수록 지하부 길이도 길 것인가?"
        )
        st.info("위 가설은 예시입니다. 실험 보고서에 맞게 내용을 바꿔서 사용해보세요.")
        st.header("📊 주요 통계 용어")
        st.write(
            "- 평균: 여러 값의 중간 크기  |  표준편차: 값들이 평균에서 얼마나 퍼져 있는지  |  "
            "CV(변동계수): 표준편차를 평균으로 나눈 값  |  상관계수: 두 변수가 함께 변하는지(-1~1)"
        )
    except Exception as e:
        st.warning(f"⚠️ 이 부분은 데이터 형식 때문에 표시하지 못했어요: {e}")

with tab2:
    try:
        st.header("📋 각종 데이터 표")
        if env_df is None or env_df.empty:
            st.info("환경 데이터가 아직 업로드되지 않았어요. 사이드바에서 환경 CSV를 올려주세요.")
        else:
            env_num = [c for c in ["temperature", "humidity", "ph", "ec"] if c in env_df.columns]
            if env_num:
                st.subheader("환경 데이터 요약 (평균·최소·최대)")
                summ = env_df[env_num].agg(["mean", "min", "max"]).T
                summ.columns = ["평균", "최소", "최대"]
                st.dataframe(summ, width="stretch")

            if "time" in env_df.columns and "temperature" in env_df.columns:
                d = env_df.dropna(subset=["time", "temperature"]).copy()
                d["날짜"] = d["time"].dt.date
                daily = d.groupby("날짜")["temperature"].mean().reset_index()
                st.subheader("일별 평균 온도")
                st.dataframe(daily, width="stretch")

        if growth_df is None or growth_df.empty:
            st.info("생육 데이터가 아직 업로드되지 않았어요. 사이드바에서 생육 CSV를 올려주세요.")
        else:
            st.subheader("생육 데이터 요약")
            grow_num = [c for c in ["잎 수", "지상부 길이", "지하부 길이", "생중량", "지상부 질량", "지하부 질량"] if c in growth_df.columns]
            if grow_num:
                gsumm = growth_df[grow_num].agg(["mean", "std", "min", "max"]).T
                gsumm.columns = ["평균", "표준편차", "최소", "최대"]
                st.dataframe(gsumm, width="stretch")

            st.subheader("개체별 생육 표")
            show = ["개체번호"]
            for c in ["잎 수", "지상부 길이", "지하부 길이", "생중량", "지상부 질량", "지하부 질량"]:
                if c in growth_df.columns:
                    show.append(c)
            st.dataframe(growth_df[show], width="stretch")

            with st.expander("생육 데이터 원본 테이블"):
                st.dataframe(growth_df, width="stretch")
                csv_growth = growth_df.to_csv(index=False).encode("utf-8-sig")
                st.download_button("생육 CSV 다운로드", csv_growth, file_name=growth_file.name, mime="text/csv")

            with st.expander("환경 데이터 원본 테이블"):
                st.dataframe(env_df, width="stretch")
                csv_env = env_df.to_csv(index=False).encode("utf-8-sig")
                st.download_button("환경 CSV 다운로드", csv_env, file_name=env_file.name, mime="text/csv")
    except Exception as e:
        st.warning(f"⚠️ 이 부분은 데이터 형식 때문에 표시하지 못했어요: {e}")

with tab3:
    try:
        st.header("📊 결과 분석")
        if growth_df is None or growth_df.empty:
            st.info("생육 데이터가 아직 업로드되지 않았어요. 사이드바에서 생육 CSV를 올려주세요.")
        else:
            st.subheader("🥇 개체별 생중량 막대그래프")
            w = growth_df["생중량"].dropna() if "생중량" in growth_df.columns else pd.Series(dtype=float)
            if len(w) >= 1:
                q75 = w.quantile(0.75)
                q25 = w.quantile(0.25)
                growth_df["색상"] = "전체"
                growth_df.loc[growth_df["생중량"] >= q75, "색상"] = "상위 25%"
                growth_df.loc[growth_df["생중량"] <= q25, "색상"] = "하위 25%"
                fig = px.bar(growth_df, x="개체번호", y="생중량", color="색상", title="개체별 생중량 (상위·하위 25% 강조)")
                fig.update_layout(font=dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif"))
                st.plotly_chart(fig, width="stretch")
            else:
                st.info("생중량 데이터가 없어서 막대그래프를 표시할 수 없어요.")

            st.subheader("🌱 지상부 길이와 지하부 길이의 관계")
            if "지상부 길이" in growth_df.columns and "지하부 길이" in growth_df.columns:
                d = growth_df[["지상부 길이", "지하부 길이"]].dropna()
                if len(d) >= 2:
                    coef = np.polyfit(d["지상부 길이"], d["지하부 길이"], 1)
                    trend = np.poly1d(coef)
                    xs = np.linspace(d["지상부 길이"].min(), d["지상부 길이"].max(), 100)
                    r = d["지상부 길이"].corr(d["지하부 길이"])
                    fig = px.scatter(d, x="지상부 길이", y="지하부 길이", title=f"지상부 길이 vs 지하부 길이 (r = {r:.2f})")
                    fig.add_trace(go.Scatter(x=xs, y=trend(xs), mode="lines", name="추세선"))
                    fig.update_layout(font=dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif"))
                    st.plotly_chart(fig, width="stretch")
                else:
                    st.info("지상부 길이와 지하부 길이 데이터가 2개 이상 없어서 산점도를 표시할 수 없어요.")
            else:
                st.info("지상부 길이 또는 지하부 길이 열이 없어서 산점도를 표시할 수 없어요.")
    except Exception as e:
        st.warning(f"⚠️ 이 부분은 데이터 형식 때문에 표시하지 못했어요: {e}")
