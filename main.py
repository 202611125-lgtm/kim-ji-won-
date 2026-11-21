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

        if env_df is not None and not env_df.empty and "temperature" in env_df.columns:
            c2.metric("평균 온도", f"{env_df['temperature'].mean():.1f} °C")
        else:
            c2.metric("평균 온도", "—")

        if env_df is not None and not env_df.empty and "humidity" in env_df.columns:
            c3.metric("평균 습도", f"{env_df['humidity'].mean():.1f} %")
        else:
            c3.metric("평균 습도", "—")

        if growth_df is not None and not growth_df.empty and "생중량" in growth_df.columns:
            c1.metric("총 개체수", f"{len(growth_df)} 개체")
            c4.metric("평균 생중량", f"{growth_df['생중량'].dropna().mean():.3f} g")
        else:
            c1.metric("총 개체수", "—")
            c4.metric("평균 생중량", "—")
    except Exception as e:
        st.warning(f"⚠️ 이 부분은 데이터 형식 때문에 표시하지 못했어요: {e}")

with tab2:
    try:
        st.header("🌡️ 환경 데이터")
        if env_df is None or env_df.empty:
            st.info("환경 데이터가 아직 업로드되지 않았어요. 사이드바에서 환경 CSV를 올려주세요.")
        else:
            env_num = [c for c in ["temperature", "humidity", "ph", "ec"] if c in env_df.columns]
            if env_num:
                st.subheader("환경 요약 (평균·최소·최대)")
                summ = env_df[env_num].agg(["mean", "min", "max"]).T
                summ.columns = ["평균", "최소", "최대"]
                st.dataframe(summ, width="stretch")
            else:
                st.info("온도·습도·pH·EC 같은 숫자 환경 열이 없어서 요약을 표시할 수 없어요.")

            if "time" in env_df.columns and "temperature" in env_df.columns:
                d = env_df.dropna(subset=["time", "temperature"]).copy()
                d["날짜"] = d["time"].dt.date
                daily_t = d.groupby("날짜")["temperature"].mean().reset_index()
                fig_t = px.line(daily_t, x="날짜", y="temperature", title="일별 평균 온도 변화")
                fig_t.update_layout(font=dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif"))
                st.plotly_chart(fig_t, width="stretch")

            if "time" in env_df.columns and "humidity" in env_df.columns:
                d = env_df.dropna(subset=["time", "humidity"]).copy()
                d["날짜"] = d["time"].dt.date
                daily_h = d.groupby("날짜")["humidity"].mean().reset_index()
                fig_h = px.line(daily_h, x="날짜", y="humidity", title="일별 평균 습도 변화")
                fig_h.update_layout(font=dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif"))
                st.plotly_chart(fig_h, width="stretch")

            if "ph" in env_df.columns and "ec" in env_df.columns:
                d = env_df.dropna(subset=["time", "ph", "ec"]).copy()
                d["날짜"] = d["time"].dt.date
                daily_pe = d.groupby("날짜")[["ph", "ec"]].mean().reset_index()
                fig_pe = make_subplots(rows=1, cols=2, subplot_titles=("pH", "EC"))
                fig_pe.add_trace(go.Scatter(x=daily_pe["날짜"], y=daily_pe["ph"], mode="lines", name="pH"), row=1, col=1)
                fig_pe.add_trace(go.Scatter(x=daily_pe["날짜"], y=daily_pe["ec"], mode="lines", name="EC"), row=1, col=2)
                fig_pe.update_layout(title="일별 평균 pH·EC 변화", font=dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif"))
                st.plotly_chart(fig_pe, width="stretch")

            with st.expander("환경 데이터 원본 테이블"):
                st.dataframe(env_df, width="stretch")
                csv_env = env_df.to_csv(index=False).encode("utf-8-sig")
                st.download_button("환경 CSV 다운로드", csv_env, file_name=env_file.name, mime="text/csv")
    except Exception as e:
        st.warning(f"⚠️ 이 부분은 데이터 형식 때문에 표시하지 못했어요: {e}")

with tab3:
    try:
        st.header("📊 생육 결과")
        if growth_df is None or growth_df.empty:
            st.info("생육 데이터가 아직 업로드되지 않았어요. 사이드바에서 생육 CSV를 올려주세요.")
        else:
            st.write("**🥇 핵심 결과 카드**")
            c1, c2, c3 = st.columns(3)
            w = growth_df["생중량"].dropna() if "생중량" in growth_df.columns else pd.Series(dtype=float)
            if len(w) >= 1:
                max_id = w.idxmax()
                min_id = w.idxmin()
                max_row = growth_df.iloc[int(max_id)]
                min_row = growth_df.iloc[int(min_id)]
                c1.metric("평균 생중량", f"{w.mean():.3f} g")
                c2.metric("최대 개체", f"{max_row['개체번호']} ({w.max():.3f} g)")
                c3.metric("최소 개체", f"{min_row['개체번호']} ({w.min():.3f} g)")
            else:
                c1.metric("평균 생중량", "—")
                c2.metric("최대 개체", "—")
                c3.metric("최소 개체", "—")

            st.write("**개체별 생육 비교**")
            for col in ["생중량", "잎 수", "지상부 길이", "지하부 길이"]:
                if col not in growth_df.columns or col not in measure_cols:
                    continue
                fig = px.bar(growth_df, x="개체번호", y=col, title=f"개체별 평균 {col}")
                fig.update_layout(font=dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif"))
                st.plotly_chart(fig, width="stretch")

            if "생중량" in growth_df.columns:
                fig = px.box(growth_df, y="생중량", title="생중량 분포 (박스플롯)")
                fig.update_layout(font=dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif"))
                st.plotly_chart(fig, width="stretch")

            st.write("**상관관계 분석**")
            corr_pairs = [("잎 수", "생중량"), ("지상부 길이", "생중량")]
            for x_col, y_col in corr_pairs:
                if x_col in growth_df.columns and y_col in growth_df.columns:
                    d = growth_df[[x_col, y_col]].dropna()
                    if len(d) >= 2:
                        coef = np.polyfit(d[x_col], d[y_col], 1)
                        trend = np.poly1d(coef)
                        xs = np.linspace(d[x_col].min(), d[x_col].max(), 100)
                        r = d[x_col].corr(d[y_col])
                        fig = px.scatter(d, x=x_col, y=y_col, title=f"{x_col} vs {y_col} (r = {r:.2f})")
                        fig.add_trace(go.Scatter(x=xs, y=trend(xs), mode="lines", name="추세선"))
                        fig.update_layout(font=dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif"))
                        st.plotly_chart(fig, width="stretch")
                    else:
                        st.info(f"{x_col}와 {y_col} 데이터가 2개 이상 없어서 상관관계를 표시할 수 없어요.")

            if "생중량" in growth_df.columns and len(growth_df) >= 4:
                w = growth_df["생중량"].dropna()
                if len(w) >= 4:
                    q75 = w.quantile(0.75)
                    q25 = w.quantile(0.25)
                    top = growth_df[growth_df["생중량"] >= q75]
                    bottom = growth_df[growth_df["생중량"] <= q25]
                    rows = []
                    for label, group in [("상위 25%", top), ("하위 25%", bottom)]:
                        rows.append(
                            {
                                "구분": label,
                                "평균 생중량(g)": f"{group['생중량'].mean():.3f}",
                                "평균 잎 수": f"{group['잎 수'].mean():.1f}",
                                "평균 지상부 길이(mm)": f"{group['지상부 길이'].mean():.1f}",
                                "평균 지하부 길이(mm)": f"{group['지하부 길이'].mean():.1f}",
                            }
                        )
                    st.dataframe(pd.DataFrame(rows), width="stretch")

            with st.expander("생육 데이터 원본 테이블"):
                st.dataframe(growth_df, width="stretch")
                csv_growth = growth_df.to_csv(index=False).encode("utf-8-sig")
                st.download_button("생육 CSV 다운로드", csv_growth, file_name=growth_file.name, mime="text/csv")
    except Exception as e:
        st.warning(f"⚠️ 이 부분은 데이터 형식 때문에 표시하지 못했어요: {e}")
