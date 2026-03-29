import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.api_key import APIKeyHeader
from sqlalchemy.orm import Session

from src.database import get_db, init_db, close_db
from src.models import GameRecommendRequest, UserRecommendRequest, GameInfoRequest
from src.services import get_item_recommendations, get_user_recommendations, get_game_details_by_ids

_API_KEY = os.getenv("API_KEY")
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def verify_api_key(api_key: str = Security(_api_key_header)):
    # API_KEY 미설정 시 인증 비활성화
    if not _API_KEY:
        return
    if api_key != _API_KEY:
        raise HTTPException(status_code=403, detail="유효하지 않은 API 키입니다")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("🚀 FastAPI 앱 기동 시작...")
    init_db()
    
    yield
    
    # Shutdown
    print("🛑 FastAPI 앱 종료 중...")
    close_db()

app = FastAPI(title="Steam Game Recommendation API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/recommend/game")
def recommend_by_game(request: GameRecommendRequest, db: Session = Depends(get_db), _: None = Depends(verify_api_key)):
    try:
        results = get_item_recommendations(db=db, request=request, limit=request.limit)
        if results is None:
            raise HTTPException(status_code=404, detail=f"game_id {request.game_id}의 임베딩이 존재하지 않습니다")
        return {"status": "success", "data": results}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching game recommendations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/recommend/user")
def recommend_by_user(request: UserRecommendRequest, db: Session = Depends(get_db), _: None = Depends(verify_api_key)):
    try:
        result = get_user_recommendations(db=db, request=request, limit=request.limit)
        return {
            "status": "success",
            "data": result["recommendations"],
            "skipped_game_ids": result["skipped_game_ids"]
        }
    except Exception as e:
        print(f"Error fetching user recommendations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/games/info")
def get_games_info(request: GameInfoRequest, db: Session = Depends(get_db), _: None = Depends(verify_api_key)):
    try:
        result = get_game_details_by_ids(db=db, game_ids=request.game_ids)
        return {
            "status": "success",
            "data": result["games"],
            "not_found_game_ids": result["not_found_game_ids"]
        }
    except Exception as e:
        print(f"Error fetching game details: {e}")
        raise HTTPException(status_code=500, detail=str(e))
