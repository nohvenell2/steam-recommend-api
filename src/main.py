import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from src.database import get_db, init_db, close_db
from src.models import GameRecommendRequest, UserRecommendRequest
from src.services import get_item_recommendations, get_user_recommendations

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
def recommend_by_game(request: GameRecommendRequest, db: Session = Depends(get_db)):
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
def recommend_by_user(request: UserRecommendRequest, db: Session = Depends(get_db)):
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
