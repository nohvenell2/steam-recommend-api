import requests
import json
import time

BASE_URL = "http://127.0.0.1:8000"

def test_game_recommend():
    print("Testing /recommend/game ...")
    payload = {
        "release_date": "1900-01-01T00:00:00",
        "total_review_count": 500,
        "total_review_positive_percent": 70,
        "recent_review_count": 0,
        "recent_review_positive_percent": 0,
        "game_id": 292030  # Witcher 3
    }
    
    try:
        response = requests.post(f"{BASE_URL}/recommend/game", json=payload)
        response.raise_for_status()
        data = response.json()
        print("Response successful.")
        print(json.dumps(data.get("data", [])[:3], indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"Error testing game recommend: {e}")

def test_user_recommend():
    print("\nTesting /recommend/user ...")
    payload = {
        "release_date": "2020-01-01T00:00:00",
        "total_review_count": 100,
        "total_review_positive_percent": 50,
        "recent_review_count": 0,
        "recent_review_positive_percent": 0,
        "games": [
            {
                "appid": 1174180, # RDR 2
                "name": "Red Dead Redemption 2",
                "playtime_forever": 9316,
                "img_icon_url": "5106abd9c1187a97f23295a0ba9470c94804ec6c",
                "has_community_visible_stats": True
            },
            {
                "appid": 292030, # Witcher 3
                "name": "The Witcher 3: Wild Hunt",
                "playtime_forever": 5000,
                "img_icon_url": "",
                "has_community_visible_stats": True
            }
        ]
    }
    
    try:
        response = requests.post(f"{BASE_URL}/recommend/user", json=payload)
        response.raise_for_status()
        data = response.json()
        print("Response successful.")
        print(json.dumps(data.get("data", [])[:3], indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"Error testing user recommend: {e}")

if __name__ == "__main__":
    # Wait for server to be fully ready before testing
    time.sleep(2)
    test_game_recommend()
    test_user_recommend()
