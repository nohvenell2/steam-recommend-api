from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

class BaseFilterParams(BaseModel):
    """공통 필터 파라미터"""
    limit: int = Field(
        default=20,
        description="검색 결과 최대 반환 개수 (기본값: 20)"
    )
    release_date: datetime = Field(
        default="2020-01-01T00:00:00", 
        description="이 날짜 이후에 출시된 게임만 검색 (기본값: 2020년 1월 1일)"
    )
    total_review_count: int = Field(
        default=100, 
        description="최소 전체 리뷰 수 (기본값: 100)"
    )
    total_review_positive_percent: int = Field(
        default=50, 
        ge=0, le=100,
        description="최소 전체 리뷰 긍정 비율 (0~100, 기본값: 50)"
    )
    recent_review_count: int = Field(
        default=0, 
        description="최소 최근 리뷰 수 (기본값: 0)"
    )
    recent_review_positive_percent: int = Field(
        default=0, 
        ge=0, le=100,
        description="최소 최근 리뷰 긍정 비율 (0~100, 기본값: 0)"
    )

class GameRecommendRequest(BaseFilterParams):
    """특정 게임 기준 유사도 검색 요청 (Item-to-Item)"""
    game_id: int = Field(..., description="기준이 되는 스팀 게임 ID")

class UserGameInfo(BaseModel):
    """스팀 유저의 개별 게임 플레이 정보"""
    appid: int
    name: str = ""
    playtime_forever: int
    img_icon_url: str = ""
    has_community_visible_stats: bool = False

class UserRecommendRequest(BaseFilterParams):
    """유저 정보 기반 유사도 검색 요청 (User-to-Item)"""
    games: List[UserGameInfo] = Field(..., description="유저가 플레이한 게임 목록")


class GameRecommendation(BaseModel):
    """추천 결과 단일 게임 정보"""
    game_id: int
    title: Optional[str] = None
    url: Optional[str] = None
    description: Optional[str] = None
    header_image: Optional[str] = None
    developer: Optional[str] = None
    publisher: Optional[str] = None
    release_date: Optional[datetime] = None
    release_date_original: Optional[str] = None
    sim_score: float
    total_review_count: Optional[int] = None
    all_reviews: Optional[str] = None
    total_review_positive_percent: Optional[int] = None
    recent_review_count: Optional[int] = None
    recent_reviews: Optional[str] = None
    recent_review_positive_percent: Optional[int] = None
    genres: List[str] = []
    tags: List[str] = []


class GameRecommendResponse(BaseModel):
    """게임 추천 응답"""
    status: str = "success"
    data: List[GameRecommendation]


class UserRecommendResponse(BaseModel):
    """유저 추천 응답"""
    status: str = "success"
    data: List[GameRecommendation]
    skipped_game_ids: List[int] = []
