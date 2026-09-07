import streamlit as st
import requests
from datetime import datetime, timedelta, timezone, date
import pandas as pd
import plotly.express as px


# ============================================================
# 페이지 설정
# ============================================================

st.set_page_config(
    page_title="박스오피스 조회",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 일일 박스오피스")
st.caption("영화진흥위원회(KOBIS) 영화관입장권통합전산망")


# ============================================================
# 한국 시간 계산
# ============================================================
# Streamlit Cloud 서버가 한국 시간이 아닐 수 있으므로
# UTC+9를 적용해서 한국 날짜를 계산합니다.

KST = timezone(timedelta(hours=9))

now_kst = datetime.now(KST)

# 한국 시간 기준 오늘
today_kst = now_kst.date()

# 한국 시간 기준 어제
yesterday_kst = today_kst - timedelta(days=1)


# ============================================================
# 날짜 선택
# ============================================================
# 사용자가 달력에서 박스오피스 날짜를 선택합니다.
#
# 오늘은 아직 집계가 끝나지 않았으므로
# 선택할 수 있는 가장 늦은 날짜를 어제로 설정합니다.

st.subheader("📅 조회 날짜")

selected_date = st.date_input(
    "박스오피스를 확인할 날짜를 선택하세요.",
    value=yesterday_kst,
    max_value=yesterday_kst,
    format="YYYY-MM-DD"
)


# ============================================================
# 선택한 날짜를 KOBIS 형식으로 변경
# ============================================================
# 예:
# 2026-09-06 → 20260906

target_date = selected_date.strftime("%Y%m%d")

display_date = selected_date.strftime(
    "%Y년 %m월 %d일"
)


# ============================================================
# KOBIS API 함수
# ============================================================
# 같은 날짜를 다시 조회하면
# 1시간 동안 저장된 결과를 사용합니다.
#
# target_dt가 함수의 입력값이기 때문에
# 날짜가 달라지면 새로운 API 요청을 합니다.

@st.cache_data(ttl=3600)
def get_boxoffice(target_dt):

    # --------------------------------------------------------
    # Streamlit Secrets에서 KOBIS 인증키 가져오기
    # --------------------------------------------------------

    try:
        api_key = st.secrets["KOBIS_KEY"]

    except Exception:
        return {
            "success": False,
            "message": (
                "KOBIS_KEY를 찾을 수 없습니다.\n\n"
                "Streamlit Cloud에서 다음을 확인하세요.\n\n"
                "① 앱의 Settings → Secrets로 이동\n"
                "② KOBIS_KEY가 정확히 입력되어 있는지 확인\n"
                "③ 저장 후 앱을 다시 실행하세요.\n\n"
                "Secrets 예시:\n"
                'KOBIS_KEY = "발급받은_인증키"'
            ),
            "data": []
        }


    # 인증키가 비어 있는 경우
    if not str(api_key).strip():

        return {
            "success": False,
            "message": (
                "KOBIS_KEY가 비어 있습니다.\n\n"
                "Streamlit Cloud의 Secrets에서 "
                "발급받은 KOBIS 인증키를 입력하세요."
            ),
            "data": []
        }


    # ========================================================
    # KOBIS API 주소
    # ========================================================

    url = (
        "https://www.kobis.or.kr/"
        "kobisopenapi/webservice/rest/boxoffice/"
        "searchDailyBoxOfficeList.json"
    )


    # API에 전달할 값
    params = {
        "key": str(api_key).strip(),
        "targetDt": target_dt
    }


    # ========================================================
    # API 요청
    # ========================================================

    try:

        response = requests.get(
            url,
            params=params,
            timeout=15
        )

        response.raise_for_status()

        result = response.json()


    except requests.exceptions.Timeout:

        return {
            "success": False,
            "message": (
                "KOBIS API 요청 시간이 초과되었습니다.\n\n"
                "잠시 후 다시 시도해 주세요."
            ),
            "data": []
        }


    except requests.exceptions.RequestException as e:

        return {
            "success": False,
            "message": (
                "KOBIS API에 연결하지 못했습니다.\n\n"
                "다음 내용을 확인하세요.\n"
                "• 인터넷 연결\n"
                "• KOBIS API 서버 상태\n"
                "• KOBIS API 주소\n\n"
                f"오류 내용: {e}"
            ),
            "data": []
        }


    except ValueError:

        return {
            "success": False,
            "message": (
                "KOBIS에서 정상적인 JSON 데이터를 받지 못했습니다.\n\n"
                "KOBIS API 서버 상태를 확인해 주세요."
            ),
            "data": []
        }


    # ========================================================
    # faultInfo 확인
    # ========================================================
    # KOBIS는 인증키가 잘못되어도 HTTP 200을 반환할 수 있습니다.
    # 따라서 faultInfo가 있는지 별도로 확인합니다.

    if "faultInfo" in result:

        fault = result["faultInfo"]

        fault_code = fault.get(
            "faultCode",
            ""
        )

        fault_message = fault.get(
            "message",
            ""
        )

        return {
            "success": False,
            "message": (
                "KOBIS에서 API 오류를 반환했습니다.\n\n"
                "다음 내용을 확인하세요.\n"
                "• KOBIS 인증키가 정확한지\n"
                "• 인증키 앞뒤에 불필요한 공백이 없는지\n"
                "• KOBIS Open API 인증키가 정상적으로 발급되었는지\n\n"
                f"오류 코드: {fault_code}\n"
                f"오류 메시지: {fault_message}"
            ),
            "data": []
        }


    # ========================================================
    # boxOfficeResult 확인
    # ========================================================

    boxoffice = result.get(
        "boxOfficeResult"
    )


    if not boxoffice:

        return {
            "success": False,
            "message": (
                "KOBIS 응답에 boxOfficeResult가 없습니다.\n\n"
                "KOBIS API의 응답 상태를 확인해 주세요."
            ),
            "data": []
        }


    # ========================================================
    # 영화 목록 가져오기
    # ========================================================

    movie_list = boxoffice.get(
        "dailyBoxOfficeList",
        []
    )


    # ========================================================
    # 영화 목록이 비어 있는 경우
    # ========================================================

    if not movie_list:

        return {
            "success": False,
            "empty": True,
            "message": (
                "그날은 아직 집계 전입니다."
            ),
            "data": []
        }


    # 정상적으로 영화 목록 반환
    return {
        "success": True,
        "empty": False,
        "message": "",
        "data": movie_list
    }


# ============================================================
# API 실행
# ============================================================

result = get_boxoffice(
    target_date
)


# ============================================================
# 데이터가 없는 경우
# ============================================================

if not result["success"]:

    # 영화 목록이 비어 있는 경우
    if result.get("empty", False):

        st.info(
            f"📭 {display_date} 박스오피스"
        )

        st.warning(
            "그날은 아직 집계 전입니다."
        )

        st.stop()


    # API 오류인 경우
    st.error(
        "박스오피스 데이터를 불러오지 못했습니다."
    )

    st.warning(
        result["message"]
    )

    st.stop()


# ============================================================
# 영화 데이터 가져오기
# ============================================================

movies = result["data"]


# ============================================================
# 숫자 데이터 변환
# ============================================================
# KOBIS API에서는 숫자도 문자열로 전달됩니다.
#
# 예:
# "1"      → 1
# "123456" → 123456

for movie in movies:

    movie["rank"] = int(
        movie.get("rank", 0) or 0
    )

    movie["rankInten"] = int(
        movie.get("rankInten", 0) or 0
    )

    movie["audiCnt"] = int(
        movie.get("audiCnt", 0) or 0
    )

    movie["audiAcc"] = int(
        movie.get("audiAcc", 0) or 0
    )

    movie["scrnCnt"] = int(
        movie.get("scrnCnt", 0) or 0
    )

    movie["showCnt"] = int(
        movie.get("showCnt", 0) or 0
    )


# ============================================================
# 데이터프레임 만들기
# ============================================================

df = pd.DataFrame(
    movies
)


# 순위 기준으로 정렬
df = (
    df.sort_values(
        by="rank",
        ascending=True
    )
    .reset_index(drop=True)
)


# ============================================================
# 조회 날짜 표시
# ============================================================

st.subheader(
    f"📅 {display_date} 박스오피스"
)

st.caption(
    f"KOBIS 조회 날짜: {target_date}"
)


# ============================================================
# 1위 영화
# ============================================================

first_movie = df.iloc[0]

first_movie_name = first_movie["movieNm"]


# 누적관객이 100만 명을 넘었으면 트로피 추가
if first_movie["audiAcc"] > 1_000_000:

    first_movie_name = (
        first_movie_name + " 🏆"
    )


st.markdown(
    f"## 🥇 1위: {first_movie_name}"
)


# ============================================================
# 1위 영화 지표 카드 3개
# ============================================================

col1, col2, col3 = st.columns(3)


with col1:

    st.metric(
        "👥 관객수",
        f"{first_movie['audiCnt']:,}명"
    )


with col2:

    st.metric(
        "🎟️ 누적 관객",
        f"{first_movie['audiAcc']:,}명"
    )


with col3:

    st.metric(
        "🖥️ 스크린수",
        f"{first_movie['scrnCnt']:,}개"
    )


# ============================================================
# 관객수 상위 5편 세로 막대그래프
# ============================================================

st.subheader(
    "📊 관객수 상위 5편"
)


# 관객수가 많은 순서로 정렬
top5 = (
    df.sort_values(
        by="audiCnt",
        ascending=False
    )
    .head(5)
    .reset_index(drop=True)
)


# ------------------------------------------------------------
# 그래프에서는 트로피가 표시되도록 영화명을 새로 만듭니다.
# ------------------------------------------------------------

top5["graph_movieNm"] = top5.apply(
    lambda row: (
        row["movieNm"] + " 🏆"
        if row["audiAcc"] > 1_000_000
        else row["movieNm"]
    ),
    axis=1
)


# ============================================================
# Plotly 세로 막대그래프
# ============================================================

fig = px.bar(
    top5,
    x="graph_movieNm",
    y="audiCnt",
    labels={
        "graph_movieNm": "영화",
        "audiCnt": "관객수"
    },
    text="audiCnt"
)


# ------------------------------------------------------------
# 왼쪽 → 오른쪽으로
# 관객수가 많은 영화 → 적은 영화 순서
# ------------------------------------------------------------

fig.update_layout(

    xaxis=dict(
        categoryorder="array",
        categoryarray=top5[
            "graph_movieNm"
        ].tolist()
    ),

    margin=dict(
        l=20,
        r=20,
        t=20,
        b=100
    )
)


# 막대 위에 관객수 표시
fig.update_traces(
    texttemplate="%{text:,}명",
    textposition="outside"
)


# 그래프 표시
st.plotly_chart(
    fig,
    use_container_width=True
)


# ============================================================
# 전체 박스오피스 표
# ============================================================

st.subheader(
    "🎥 전체 박스오피스"
)


# ============================================================
# 표용 데이터 만들기
# ============================================================

table_df = df[
    [
        "rank",
        "rankInten",
        "movieNm",
        "openDt",
        "audiCnt",
        "audiAcc",
        "scrnCnt"
    ]
].copy()


# ============================================================
# 순위 변동 표시 만들기
# ============================================================
# rankInten이 양수:
#   빨간색 ↑
#
# rankInten이 음수:
#   파란색 ↓
#
# 0:
#   변화 없음
#
# 주의:
# HTML 색상을 사용하기 위해
# 표에서는 st.markdown 방식의 HTML을 사용합니다.

def make_rank_change(value):

    if value > 0:

        return (
            f'<span style="color:red; font-weight:bold;">'
            f'↑ {value}'
            f'</span>'
        )

    elif value < 0:

        return (
            f'<span style="color:blue; font-weight:bold;">'
            f'↓ {abs(value)}'
            f'</span>'
        )

    else:

        return "–"


table_df["순위변동"] = (
    table_df["rankInten"]
    .apply(make_rank_change)
)


# ============================================================
# 영화명 옆에 트로피 표시
# ============================================================

table_df["영화명"] = table_df.apply(
    lambda row: (
        row["movieNm"] + " 🏆"
        if row["audiAcc"] > 1_000_000
        else row["movieNm"]
    ),
    axis=1
)


# ============================================================
# 필요한 열 이름으로 변경
# ============================================================

table_df = table_df[
    [
        "rank",
        "순위변동",
        "영화명",
        "openDt",
        "audiCnt",
        "audiAcc",
        "scrnCnt"
    ]
]


table_df.columns = [
    "순위",
    "순위변동",
    "영화명",
    "개봉일",
    "관객수",
    "누적관객",
    "스크린수"
]


# ============================================================
# 숫자에 천 단위 쉼표 표시
# ============================================================

table_df["관객수"] = table_df[
    "관객수"
].map(
    lambda x: f"{x:,}"
)


table_df["누적관객"] = table_df[
    "누적관객"
].map(
    lambda x: f"{x:,}"
)


table_df["스크린수"] = table_df[
    "스크린수"
].map(
    lambda x: f"{x:,}"
)


# ============================================================
# HTML 표로 출력
# ============================================================
# st.dataframe()에서는 HTML 화살표 색상을 적용하기 어렵기 때문에
# st.markdown()으로 표를 출력합니다.

st.markdown(
    table_df.to_html(
        index=False,
        escape=False
    ),
    unsafe_allow_html=True
)


# ============================================================
# 데이터 출처
# ============================================================

st.caption(
    "※ 데이터 출처: 영화진흥위원회(KOBIS) "
    "영화관입장권통합전산망"
)
