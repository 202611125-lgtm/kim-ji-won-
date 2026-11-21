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

tab1, tab2, tab3 = st.tabs(["📖 실험 개요", "🌡️ 환경 데이터", "📊 생육 결과"])

with tab1:
    try:
        st.header("🌱 실험 개요")
        st.write("**연구 배경 및 목적**")
        st.write(
            "극지식물은 추운 환경에서도 잘 자라는 식물로, 날씨(온도·습도 등) 변화에 따라 "
            "개체마다 자라는 정도가 달라집니다. 이 대시보드는 우리 학교 극지식물의 "
            "환경 조건과 개체별 생육 차이를 한눈에 비교하기 위해 만들었습니다."
        )
        st.write("**연구 가설**")
        st.write(
            "- 온도가 적당할 때 극지식물의 생장이 더 활발할 것이다.  |  "
            "- 습도가 높을수록 개체별 생중량 차이가 클 것이다.  |  "
            "- 잎 수·지상부 길이가 길수록 생중량이 클 것이다."
        )
        st.info("위 가설은 예시입니다. 선생님의 실험 가설로 바꿔서 사용해보세요.")

        st.write("**주요 통계 용어**")
        st.write(
            "- 평균: 여러 값의 중간 크기  |  표준편차: 값들이 평균에서 얼마나 퍼져 있는지  |  "
            "CV(변동계수): 표준편차를 평균으로 나눈 값  |  상관계수: 두 변수가 함께 변하는지(-1~1)"
        )

        st.write("**데이터 요약**")
        summary_rows = [["학교명", school_name]]
        if env_df is not None and not env_df.empty:
            summary_rows += [
                ["측정 기간", f"{env_df['time'].min():%Y-%m-%d} ~ {env_df['time'].max():%Y-%m-%d}"],
                ["환경 측정 항목", ", ".join([c for c in ["temperature", "humidity", "ph", "ec", "water_temp", "co2"] if c in env_df.columns])],
            ]
        if growth_df is not None and not growth_df.empty:
            summary_rows += [
                ["총 개체 수", f"{len(growth_df)} 개체"],
                ["생육 측정 항목", ", ".join([c for c in ["잎 수", "지상부 길이", "지하부 길이", "생중량", "지상부 질량", "지하부 질량"] if c in growth_df.columns])],
            ]
        st.table(pd.DataFrame(summary_rows, columns=["구분", "내용"]))

        st.write("**주요 지표 카드**")
        c1, c2, c3, c4 = st.columns(4)
        if growth_df is not None and not growth_df.empty and "생중량" in growth_df.columns:
            c1.metric("총 개체수", f"{len(growth_df)} 개체")
            c4.metric("평균 생중량", f"{growth_df['생중량'].dropna().mean():.3f} g")
        else:
            c1.metric("총 개체수", "—")
            c4.metric("평균 생중량", "—")
        if env_df is not None and not env_df.empty and "temperature" in env_df.columns:
            c2.metric("평균 온도", f"{env_df['temperature'].mean():.1f} °C")
        else:
            c2.metric("평균 온도", "—")
        if env_df is not None and not env_df.empty and "humidity" in env_df
