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
        "limit": 20,
        "release_date": "2020-01-01T00:00:00",
        "total_review_count": 100,
        "total_review_positive_percent": 50,
        "recent_review_count": 0,
        "recent_review_positive_percent": 0,
        "game_id": 1091500
    }
  ```

### 2. User-to-Item 유저 기반 추천 검색
- **경로**: `POST /recommend/user`
- **설명**: 한 유저가 플레이한 게임 리스트와それぞれの `playtime_forever` (플레이 타임)을 기준으로 **유저 취향 벡터**를 계산한 뒤, 이 벡터와 유사한 게임을 스팀 전체 목록에서 검색하여 반환합니다. (유저가 현재 보유해 보낸 배열에 있는 게임들은 모두 결과에서 자동 제외됩니다.)
- **Request Body 예시**:
  ```json
    {
        "limit": 20,
        "release_date": "2000-01-01T00:00:00",
        "total_review_count": 100,
        "total_review_positive_percent": 50,
        "recent_review_count": 0,
        "recent_review_positive_percent": 0,
        "games": [
            {
            "appid": 1158310,
            "name": "",
            "playtime_forever": 10,
            "img_icon_url": "",
            "has_community_visible_stats": false
            },
            {
            "appid": 245,
            "name": "",
            "playtime_forever": 10,
            "img_icon_url": "",
            "has_community_visible_stats": false
            }
        ]
    }
  ```

### 3. 게임 정보 일괄 조회
- **경로**: `POST /games/info`
- **설명**: 여러 게임 ID를 한 번에 입력하면, 해당 게임들의 상세 정보(메타데이터, 리뷰, 장르, 태그)를 일괄 조회하여 반환합니다. DB에 존재하지 않는 게임 ID는 `not_found_game_ids`에 포함됩니다.
- **Request Body 예시**:
  ```json
    {
        "game_ids": [1091500, 1404210, 999999999]
    }
  ```
- **Response 예시**:
  ```json
    {
        "status": "success",
        "data": [
            {
                "game_id": 1091500,
                "url": "https://store.steampowered.com/app/1091500",
                "title": "Cyberpunk 2077",
                "description": "...",
                "header_image": "https://cdn.cloudflare.steamstatic.com/steam/apps/1091500/header.jpg",
                "developer": "CD PROJEKT RED",
                "publisher": "CD PROJEKT RED",
                "release_date": "2020-12-10T00:00:00",
                "release_date_original": "Dec 10, 2020",
                "total_review_count": 500000,
                "all_reviews": "Very Positive",
                "total_review_positive_percent": 85,
                "recent_review_count": 3000,
                "recent_reviews": "Very Positive",
                "recent_review_positive_percent": 93,
                "genres": ["RPG"],
                "tags": ["Open World", "RPG", "Cyberpunk"]
            }
        ],
        "not_found_game_ids": [999999999]
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
            "sim_score": 0.6711,
            "game_id": 1404210,
            "url": "https://store.steampowered.com/app/1404210",
            "title": "Red Dead Online",
            "description": "Red Dead Online is now a standalone...",
            "header_image": "https://cdn.cloudflare.steamstatic.com/steam/apps/1404210/header.jpg",
            "developer": "Rockstar Games",
            "publisher": "Rockstar Games",
            "release_date": "2020-12-01T00:00:00",
            "release_date_original": "Dec 1, 2020",
            "total_review_count": 30131,
            "all_reviews": "Mostly Positive",
            "total_review_positive_percent": 81,
            "recent_review_count": 412,
            "recent_reviews": "Mixed",
            "recent_review_positive_percent": 55,
            "genres": ["Action", "Adventure"],
            "tags": ["Open World", "Multiplayer", "Western"]
        }
    ],
    "skipped_game_ids": [ 245 ]
}
```

### 응답 필드 설명
| 필드 | 타입 | 설명 |
|------|------|------|
| `sim_score` | float | 코사인 유사도 점수 (1에 가까울수록 유사) |
| `game_id` | int | 스팀 게임 ID |
| `url` | string | 스팀 스토어 페이지 URL |
| `title` | string | 게임 제목 |
| `description` | string | 게임 설명 |
| `header_image` | string | 헤더 이미지 URL |
| `developer` | string | 개발사 |
| `publisher` | string | 퍼블리셔 |
| `release_date` | datetime | 출시일 (ISO-8601) |
| `release_date_original` | string | 출시일 원본 텍스트 |
| `total_review_count` | int | 전체 리뷰 수 |
| `all_reviews` | string | 전체 리뷰 요약 텍스트 |
| `total_review_positive_percent` | int | 전체 긍정 리뷰 비율 |
| `recent_review_count` | int | 최근 리뷰 수 |
| `recent_reviews` | string | 최근 리뷰 요약 텍스트 |
| `recent_review_positive_percent` | int | 최근 긍정 리뷰 비율 |
| `genres` | string[] | 장르 목록 |
| `tags` | string[] | 태그 목록 |

### 임베딩 데이터가 없는 경우
1. Item-to-Item : 404 response error
2. User-to-Item : `skipped_game_ids` 항목에 임베딩 데이터가 없는 게임 id 가 추가되어 응답됨
