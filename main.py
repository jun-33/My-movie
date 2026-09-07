import streamlit as st
import requests
from datetime import datetime, timedelta, timezone
import pandas as pd
import plotly.express as px


# ============================================================
# 페이지 설정
# ============================================================

st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 어제의 박스오피스")
st.caption("영화진흥위원회(KOBIS) 일일 박스오피스")


# ============================================================
# 한국 시간 기준으로 '어제' 계산
# ============================================================
# Streamlit Cloud 서버가 한국 시간이 아닐 수 있기 때문에
# UTC+9를 직접 적용해서 한국 시간을 계산합니다.

KST = timezone(timedelta(hours=9))

now_kst = datetime.now(KST)

# 한국 시간 기준 어제
yesterday = now_kst - timedelta(days=1)

# KOBIS API가 사용하는 날짜 형식
target_date = yesterday.strftime("%Y%m%d")

# 화면에 표시할 날짜
display_date = yesterday.strftime("%Y년 %m월 %d일")


# ============================================================
# KOBIS API에서 박스오피스 정보를 가져오는 함수
# ============================================================
# 같은 날짜를 다시 조회하면 1시간 동안 저장된 결과를 사용합니다.
# 3600초 = 1시간

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
                "잠시 후 앱을 새로고침해 주세요."
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
    # KOBIS faultInfo 확인
    # ========================================================
    # KOBIS는 인증키가 잘못되어도 상태코드 200을 보낼 수 있습니다.
    # 따라서 faultInfo가 있는지 확인합니다.

    if "faultInfo" in result:

        fault = result["faultInfo"]

        fault_code = fault.get("faultCode", "")
        fault_message = fault.get("message", "")

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
    # 박스오피스 결과 가져오기
    # ========================================================

    boxoffice = result.get("boxOfficeResult")


    if not boxoffice:

        return {
            "success": False,
            "message": (
                "KOBIS 응답에 boxOfficeResult가 없습니다.\n\n"
                "KOBIS API의 응답 상태를 확인해 주세요."
            ),
            "data": []
        }


    # 영화 목록 가져오기
    movie_list = boxoffice.get(
        "dailyBoxOfficeList",
        []
    )


    # 영화 목록이 비어 있는 경우
    if not movie_list:

        return {
            "success": False,
            "message": (
                f"{target_date} 날짜의 박스오피스 영화 목록이 없습니다.\n\n"
                "다음 내용을 확인하세요.\n"
                "• 해당 날짜의 영화관 집계가 완료되었는지\n"
                "• KOBIS에서 해당 날짜 데이터를 제공하는지\n"
                "• 한국 시간 기준 날짜가 올바르게 계산되었는지"
            ),
            "data": []
        }


    # 정상적으로 영화 목록 반환
    return {
        "success": True,
        "message": "",
        "data": movie_list
    }


# ============================================================
# API 실행
# ============================================================

result = get_boxoffice(target_date)


# ============================================================
# 오류가 발생한 경우
# ============================================================

if not result["success"]:

    st.error("박스오피스 데이터를 불러오지 못했습니다.")

    st.warning(result["message"])

    # 오류가 있으면 아래 화면을 만들지 않습니다.
    st.stop()


# ============================================================
# 영화 데이터 가져오기
# ============================================================

movies = result["data"]


# ============================================================
# 문자열로 받은 숫자를 실제 숫자로 변환
# ============================================================
# KOBIS API에서는 숫자도 문자열로 전달됩니다.
# 예: "12345" → 12345

for movie in movies:

    movie["rank"] = int(
        movie.get("rank", 0) or 0
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


# ============================================================
# 데이터프레임 만들기
# ============================================================

df = pd.DataFrame(movies)


# 순위를 기준으로 정렬
df = df.sort_values(
    by="rank"
).reset_index(drop=True)


# ============================================================
# 조회 날짜 표시
# ============================================================

st.subheader(
    f"📅 {display_date} 박스오피스"
)

st.caption(
    f"KOBIS 조회 날짜: {target_date} · 한국 시간 기준 어제"
)


# ============================================================
# 1위 영화
# ============================================================

first_movie = df.iloc[0]

st.markdown(
    f"## 🥇 1위: {first_movie['movieNm']}"
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

st.subheader("📊 관객수 상위 5편")


# ------------------------------------------------------------
# 관객수가 많은 순서로 정렬
# ------------------------------------------------------------
# 가장 많은 영화가 첫 번째가 됩니다.

top5 = (
    df.sort_values(
        by="audiCnt",
        ascending=False
    )
    .head(5)
    .reset_index(drop=True)
)


# ============================================================
# Plotly 세로 막대그래프
# ============================================================
# x축 = 영화
# y축 = 관객수
# orientation을 지정하지 않으면 기본적으로 세로 막대입니다.

fig = px.bar(
    top5,
    x="movieNm",
    y="audiCnt",
    labels={
        "movieNm": "영화",
        "audiCnt": "관객수"
    },
    text="audiCnt"
)


# ------------------------------------------------------------
# 왼쪽 → 오른쪽 순서를 직접 지정
# ------------------------------------------------------------
# 관객수가 많은 영화가 왼쪽에 오고
# 관객수가 적은 영화가 오른쪽에 옵니다.

fig.update_layout(

    xaxis=dict(
        categoryorder="array",
        categoryarray=top5["movieNm"].tolist()
    ),

    # 그래프 아래쪽 영화 이름이 잘리지 않도록
    # 아래 여백을 조금 넓힙니다.
    margin=dict(
        l=20,
        r=20,
        t=20,
        b=100
    )
)


# ============================================================
# 막대 위에 관객수 표시
# ============================================================

fig.update_traces(
    texttemplate="%{text:,}명",
    textposition="outside"
)


# ============================================================
# 그래프 화면에 표시
# ============================================================

st.plotly_chart(
    fig,
    use_container_width=True
)


# ============================================================
# 전체 박스오피스 표
# ============================================================

st.subheader("🎥 전체 박스오피스")


# 표에 사용할 데이터만 선택
table_df = df[
    [
        "rank",
        "movieNm",
        "openDt",
        "audiCnt",
        "audiAcc",
        "scrnCnt"
    ]
].copy()


# 열 이름을 한국어로 변경
table_df.columns = [
    "순위",
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
].map(lambda x: f"{x:,}")


table_df["누적관객"] = table_df[
    "누적관객"
].map(lambda x: f"{x:,}")


table_df["스크린수"] = table_df[
    "스크린수"
].map(lambda x: f"{x:,}")


# ============================================================
# 표 출력
# ============================================================

st.dataframe(
    table_df,
    use_container_width=True,
    hide_index=True
)


# ============================================================
# 데이터 출처
# ============================================================

st.caption(
    "※ 데이터 출처: 영화진흥위원회(KOBIS) "
    "영화관입장권통합전산망"
)
