# app/routers/game_history.py
from email.header import Header

from fastapi import APIRouter, HTTPException, Request, Query, Response, \
    status, Header
from app.resources import GameHistoryResource
from app.models import GameHistory, Page, Link
import jwt
import os
from dotenv import load_dotenv
import boto3
import json

ALGORITHM = "HS256"

load_dotenv()
SECRET_KEY = os.getenv("SECRET_KEY")
router = APIRouter()
game_history_resource = GameHistoryResource()

sns_client = boto3.client("sns", region_name="us-east-1")
SNS_TOPIC_ARN = "arn:aws:sns:us-east-1:920373012265:game"


# sts_client = boto3.client("sts")
# identity = sts_client.get_caller_identity()
# print(identity)

@router.get("/game_history/{game_id}", response_model=GameHistory)
def get_game_by_id(game_id: int, request: Request):
    result = game_history_resource.get_by_key(game_id)
    if result:
        result.links = [
            Link(rel="self", href=str(request.url)),
            Link(rel="user_stats", href=f"/user_stats/{result.username}")
        ]
        return result
    else:
        raise HTTPException(status_code=404, detail="Game history not found")

@router.get("/game_history/", response_model=Page)
def get_game_history(request: Request, username: str = Query(None),
                     skip: int = Query(0, ge=0),
                     limit: int = Query(10, ge=1)):
    results = game_history_resource.get_by_username(username, skip, limit)
    for result in results:
        result.links = [
            Link(rel="self", href=f"/game_history/{result.game_id}"),
            Link(rel="user_stats", href=f"/user_stats/{result.username}")
        ]
    base_url = str(request.url).split('?')[0]
    query_params = dict(request.query_params)
    links = [Link(rel="self", href=str(request.url))]
    next_skip = skip + limit
    next_params = query_params.copy()
    next_params['skip'] = str(next_skip)
    next_params['limit'] = str(limit)
    next_query = "&".join([f"{k}={v}" for k, v in next_params.items()])
    links.append(Link(rel="next", href=f"{base_url}?{next_query}"))
    prev_skip = max(skip - limit, 0)
    prev_params = query_params.copy()
    prev_params['skip'] = str(prev_skip)
    prev_params['limit'] = str(limit)
    prev_query = "&".join([f"{k}={v}" for k, v in prev_params.items()])
    links.append(Link(rel="prev", href=f"{base_url}?{prev_query}"))
    page = Page(data=[result.dict() for result in results], links=links)
    return page

 # Must make sure we increment user stats accordingly in composite
 # Composite will not create without ensuring user_stats username presence
@router.post("/game_history/", status_code=status.HTTP_201_CREATED)
def create_game_history(game_history: GameHistory, request: Request,
                        response: Response):
    new_id = game_history_resource.create(game_history)
    location_url = request.url_for("get_game_by_id", game_id=new_id)
    response.headers["Location"] = str(location_url)

    # Step 2: Publish the event to SNS
    try:
        # Prepare the message payload
        event_message = {
            "game_id": new_id,
            "player": game_history.username,
            "outcome": game_history.result,
        }

        # Publish the message to SNS
        sns_client.publish(
            TopicArn=SNS_TOPIC_ARN,
            Message=json.dumps(event_message),
            Subject="New Game Event",
        )
        print(f"Published event to SNS: {event_message}")
    except Exception as e:
        print(f"Error publishing to SNS: {e}")

    return {"message": "Game history created successfully"}

# Composite must ensure other name exists in user stats if name change here
@router.put("/game_history/{game_id}")
def update_game_history(game_id: int, game_history: GameHistory):
    result = game_history_resource.update(game_id, game_history)
    if result:
        return {"message": "Game history updated successfully"}
    else:
        raise HTTPException(status_code=404, detail="Game history not found")

# Must make sure we decrement user stats accordingly in composite
@router.delete("/game_history/{game_id}")
def delete_game_history(game_id: int, auth: str = Header(...)):
    payload = jwt.decode(auth, SECRET_KEY, algorithms=[ALGORITHM])
    if "access_game_records" not in payload.get("permissions", []):
        raise HTTPException(status_code=403, detail="Permission denied")
    result = game_history_resource.delete(game_id)
    if result:
        return {"message": "Game history updated successfully"}
    else:
        raise HTTPException(status_code=404, detail="Game history not found")
