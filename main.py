import streamlit as st
import requests
from datetime import datetime, timedelta, timezone
import pandas as pd


# ============================================================
# 1. 페이지 기본 설정
# ============================================================

st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide"
)

st.title("🎬 어제의 박스오피스")
st.caption("영화진흥위원회(KOBIS) 일일 박스오피스")


# ============================================================
# 2. 한국 시간 기준으로 '어제' 날짜 계산
# ============================================================
# 배포 서버가 한국 시간이 아닐 수 있기 때문에
# 서버의 현재 시간을 그대로 사용하지 않고
# UTC+9(한국 시간)를 직접 적용합니다.

KST = timezone(timedelta(hours=9))

now_kst = datetime.now(KST)
yesterday_kst = now_kst - timedelta(days=1)

# KOBIS API가 요구하는 날짜 형식: YYYYMMDD
target_date = yesterday_kst.strftime("%Y%m%d")

# 화면에 보여줄 날짜 형식
display_date = yesterday_kst.strftime("%Y년 %m월 %d일")


# ============================================================
# 3. KOBIS API를 호출하는 함수
# ============================================================
# @st.cache_data(ttl=3600)
# → 같은 날짜를 다시 조회하면 1시간 동안 저장된 결과를 사용합니다.
# → 3600초 = 1시간

@st.cache_data(ttl=3600)
def get_boxoffice(target_dt):
    # Streamlit Cloud의 Secrets에서 인증키를 가져옵니다.
    # 실제 인증키를 코드에 직접 적지 않습니다.
    api_key = st.secrets.get("KOBIS_KEY")

    # 인증키가 없는 경우
    if not api_key:
        return {
            "success": False,
            "message": (
                "KOBIS_KEY가 설정되어 있지 않습니다.\n\n"
                "Streamlit Cloud의 앱 설정에서 "
                "Secrets에 KOBIS_KEY를 등록했는지 확인하세요."
            ),
            "data": []
        }

    # KOBIS 일일 박스오피스 API 주소
    url = (
        "https://www.kobis.or.kr/"
        "kobisopenapi/webservice/rest/boxoffice/"
        "searchDailyBoxOfficeList.json"
    )

    # API에 보낼 값
    params = {
        "key": api_key,
        "targetDt": target_dt
    }

    try:
        # API 요청
        response = requests.get(
            url,
            params=params,
            timeout=10
        )

        # HTTP 오류가 발생했는지 확인
        response.raise_for_status()

        # JSON 형태로 변환
        result = response.json()

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "message": (
                "KOBIS API 요청에 실패했습니다.\n\n"
                "다음 내용을 확인해 주세요.\n"
                "• 인터넷 연결 상태\n"
                "• KOBIS API 주소\n"
                "• Streamlit Cloud의 네트워크 상태\n"
                "• KOBIS API가 정상적으로 작동하는지\n\n"
                f"오류 내용: {e}"
            ),
            "data": []
        }

    except ValueError:
        return {
            "success": False,
            "message": (
                "KOBIS API에서 정상적인 JSON 응답을 받지 못했습니다.\n\n"
                "KOBIS API의 응답 상태를 확인해 주세요."
            ),
            "data": []
        }

    # ========================================================
    # 4. 인증키 오류 확인
    # ========================================================
    # KOBIS는 인증키가 틀려도 HTTP 상태코드가 200일 수 있습니다.
    # 따라서 faultInfo가 있는지 반드시 확인해야 합니다.

    if "faultInfo" in result:
        fault = result["faultInfo"]

        fault_code = fault.get("faultCode", "")
        fault_message = fault.get("message", "")

        return {
            "success": False,
            "message": (
                "KOBIS API에서 오류를 반환했습니다.\n\n"
                "다음 내용을 확인해 주세요.\n"
                "• Streamlit Cloud Secrets의 KOBIS_KEY가 정확한지\n"
                "• 인증키 앞뒤에 불필요한 공백이 없는지\n"
                "• KOBIS Open API 사용 신청 및 인증키 상태\n\n"
                f"오류 코드: {fault_code}\n"
                f"오류 메시지: {fault_message}"
            ),
            "data": []
        }

    # ========================================================
    # 5. 영화 목록 가져오기
    # ========================================================

    boxoffice_result = result.get("boxOfficeResult", {})
    movie_list = boxoffice_result.get("dailyBoxOfficeList", [])

    # 영화 목록이 비어 있는 경우
    if not movie_list:
        return {
            "success": False,
            "message": (
                f"{target_dt} 날짜의 박스오피스 데이터가 없습니다.\n\n"
                "다음 내용을 확인해 주세요.\n"
                "• 해당 날짜에 박스오피스 데이터가 집계되었는지\n"
                "• KOBIS API가 해당 날짜의 데이터를 제공하는지\n"
                "• 날짜가 올바르게 계산되었는지"
            ),
            "data": []
        }

    return {
        "success": True,
        "message": "",
        "data": movie_list
    }


# ============================================================
# 6. API 실행
# ============================================================

result = get_boxoffice(target_date)


# ============================================================
# 7. 오류가 발생했을 때 안내
# ============================================================

if not result["success"]:
    st.error("박스오피스 데이터를 불러오지 못했습니다.")

    # 여러 줄 안내문을 보기 좋게 표시
    st.warning(result["message"])

    # 오류가 있으면 아래 영화 화면은 만들지 않습니다.
    st.stop()


# ============================================================
# 8. API에서 받은 영화 데이터를 표 형태로 정리
# ============================================================

movies = result["data"]

# 숫자로 사용할 값들은 문자열에서 정수로 변환합니다.
# 예: "12345" → 12345
# 이렇게 해야 정렬과 그래프에서 숫자로 제대로 처리됩니다.

for movie in movies:
    movie["rank"] = int(movie.get("rank", 0) or 0)
    movie["audiCnt"] = int(movie.get("audiCnt", 0) or 0)
    movie["audiAcc"] = int(movie.get("audiAcc", 0) or 0)
    movie["scrnCnt"] = int(movie.get("scrnCnt", 0) or 0)


# ============================================================
# 9. 데이터프레임 만들기
# ============================================================

df = pd.DataFrame(movies)

# 순위를 기준으로 다시 정렬
df = df.sort_values("rank").reset_index(drop=True)


# ============================================================
# 10. 조회 날짜 표시
# ============================================================

st.subheader(f"📅 {display_date} 박스오피스")

st.caption(
    f"KOBIS 조회 날짜: {target_date} · "
    "한국 시간 기준 어제"
)


# ============================================================
# 11. 1위 영화 정보
# ============================================================

first_movie = df.iloc[0]

st.markdown(
    f"### 🥇 1위: {first_movie['movieNm']}"
)

# 1위 영화의 주요 숫자 3개를 크게 보여줍니다.
col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "오늘 관객수",
        f"{first_movie['audiCnt']:,}명"
    )

with col2:
    st.metric(
        "누적 관객수",
        f"{first_movie['audiAcc']:,}명"
    )

with col3:
    st.metric(
        "스크린수",
        f"{first_movie['scrnCnt']:,}개"
    )


# ============================================================
# 12. 관객수 상위 5편 막대그래프
# ============================================================

st.subheader("📊 관객수 상위 5편")

top5 = (
    df.sort_values("audiCnt", ascending=False)
      .head(5)
      .copy()
)

# 영화명을 그래프의 인덱스로 사용
chart_data = top5.set_index("movieNm")[["audiCnt"]]

st.bar_chart(
# ============================================================
# 관객수 상위 5편 막대그래프
# ============================================================

st.subheader("📊 관객수 상위 5편")

# 관객수가 많은 순서로 정렬한 뒤 상위 5편 선택
top5 = (
    df.sort_values(
        by="audiCnt",
        ascending=False
    )
    .head(5)
    .reset_index(drop=True)
)

# 그래프용 데이터
# 이미 관객수가 많은 순서로 정렬되어 있습니다.
chart_data = top5[
    ["movieNm", "audiCnt"]
].set_index("movieNm")

st.bar_chart(
    chart_data,
    x_label="영화",
    y_label="관객수"
)
)


# ============================================================
# 13. 전체 박스오피스 표
# ============================================================

st.subheader("🎥 전체 박스오피스")

# 화면에 보여줄 열만 선택하고
# 초보자도 알아보기 쉬운 한글 이름으로 변경합니다.

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

table_df.columns = [
    "순위",
    "영화명",
    "개봉일",
    "관객수",
    "누적관객",
    "스크린수"
]


# 숫자에 천 단위 쉼표를 표시하기 위한 함수
def format_number(value):
    return f"{value:,}"


# 표에 표시되는 숫자를 보기 좋게 변경
table_df["관객수"] = table_df["관객수"].apply(format_number)
table_df["누적관객"] = table_df["누적관객"].apply(format_number)
table_df["스크린수"] = table_df["스크린수"].apply(format_number)


# 표 출력
st.dataframe(
    table_df,
    use_container_width=True,
    hide_index=True
)


# ============================================================
# 14. 데이터 출처
# ============================================================

st.caption(
    "※ 데이터 출처: 영화진흥위원회(KOBIS) 영화관입장권통합전산망"
)
