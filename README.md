# Steam Recommendation API

이 프로젝트는 PostgreSQL의 `pgvector` 확장을 활용하여 스팀 게임을 추천해 주는 FastAPI 기반의 추천 백엔드 서버입니다.
주어진 게임 또는 유저의 플레이 기록을 기반으로 TF-IDF 및 코사인 유사도 검색을 수행합니다.

## 시스템 요구사항
- Python 3.10+
- 대상 PostgreSQL DB (버전 15 이상, `pgvector` 확장 설치됨)

## 설치 및 실행

### 1. 가상환경 설정 및 패키지 설치
```bash
# 가상환경 생성
python -m venv .venv

# 가상환경 활성화 (Windows)
.\.venv\Scripts\Activate.ps1
# 가상환경 활성화 (Mac/Linux)
# source .venv/bin/activate

# 의존성 모듈 설치
pip install -r requirements.txt
```

### 2. 환경 변수 설정
프로젝트 루트 디렉토리에 `.env` 파일을 생성하고 데이터베이스 연결 정보를 입력합니다. (참고: `.env.example`)
```env
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=steam_games_clone
DB_USER=postgres
DB_PASSWORD=your_password
```

### 3. 서버 구동
```bash
uvicorn src.main:app --reload --port 8000
```
- 서버가 켜지면 브라우저에서 `http://127.0.0.1:8000/docs` 로 접속하여 즉시 인터랙티브하게 API를 테스트해 볼 수 있는 Swagger UI를 확인할 수 있습니다.

---

## API 엔드포인트 명세서

공통적으로 POST Body에 아래의 **Soft Filter 변수**를 포함시킬 수 있습니다.
- `limit` (int): 반환할 추천 결과의 최대 개수 (기본값: 20)
- `release_date` (string ISO-8601): 입력된 날짜 이후에 발매된 게임만 필터링 (기본값: `"2020-01-01T00:00:00"`)
- `total_review_count` (int): 누적 리뷰 수 하한선 (기본값: 100)
- `total_review_positive_percent` (int): 전체 긍정 리뷰 비율 하한선 (0~100, 기본값: 50)
- `recent_review_count` (int): 최근 리뷰 수 하한선 (기본값: 0)
- `recent_review_positive_percent` (int): 최근 긍정 비율 하한선 (0~100, 기본값: 0)

### 1. Item-to-Item 게임 추천 검색
- **경로**: `POST /recommend/game`
- **설명**: 특정 게임의 ID(`game_id`)를 기준으로, 함께 맵핑된 벡터를 가장 유사한 순으로 검색하여 반환합니다. (지정된 대상 게임 자신은 결과에서 제외됩니다.)
- **Request Body 예시**:
  ```json
  {
      "game_id": 292030,
      "limit": 10
  }
  ```

### 2. User-to-Item 유저 기반 추천 검색
- **경로**: `POST /recommend/user`
- **설명**: 한 유저가 플레이한 게임 리스트와それぞれの `playtime_forever` (플레이 타임)을 기준으로 **유저 취향 벡터**를 계산한 뒤, 이 벡터와 유사한 게임을 스팀 전체 목록에서 검색하여 반환합니다. (유저가 현재 보유해 보낸 배열에 있는 게임들은 모두 결과에서 자동 제외됩니다.)
- **Request Body 예시**:
  ```json
  {
      "games": [
          {
              "appid": 1174180,
              "name": "Red Dead Redemption 2",
              "playtime_forever": 9316
          },
          {
              "appid": 292030,
              "name": "The Witcher 3: Wild Hunt",
              "playtime_forever": 5000
          }
      ],
      "limit": 5,
      "total_review_count": 500
  }
  ```

---

## 응답 (Response) 형식
성공적인 호출(HTTP 200)에 대해 아래와 같이 응답합니다. `sim_score`가 1에 가까울수록 가장 연관성이 짙은 추천 게임입니다.
```json
{
    "status": "success",
    "data": [
        {
            "game_id": 1404210,
            "title": "Red Dead Online",
            "url": "https://store.steampowered.com/app/1404210",
            "description": "게임 설명 텍스트...",
            "header_image": "https://cdn.akamai.steamstatic.com/...",
            "developer": "Rockstar Games",
            "publisher": "Rockstar Games",
            "release_date": "2020-12-01T00:00:00",
            "release_date_original": "Dec 1, 2020",
            "sim_score": 0.6711,
            "total_review_count": 30131,
            "all_reviews": "Mostly Positive",
            "total_review_positive_percent": 81,
            "recent_review_count": null,
            "recent_reviews": null,
            "recent_review_positive_percent": null,
            "genres": ["Action", "Adventure"],
            "tags": ["Open World", "Multiplayer", "Western"]
        }
    ]
}
```

`/recommend/user` 엔드포인트는 추가로 `skipped_game_ids` 필드를 반환합니다. 이 필드에는 임베딩이 존재하지 않아 유저 프로필 벡터 계산에서 제외된 게임 ID 목록이 포함됩니다.
