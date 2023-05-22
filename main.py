from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI, Request, Header
import uvicorn
from flask import Flask, redirect, request, jsonify
import stripe
import os
import json
import requests
from pydantic import BaseModel

from src.database import per_purchase, per_message_db, get_token_info, check_tokens

# connect to stripe
stripe.api_key = os.environ.get("TEST_SECRET_KEY")
webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET")
squarespace_key = os.environ.get("spkey")

# create app
app = FastAPI()


class PerMessageItem(BaseModel):
    discord_id: int
    full_discord_username: str
    openai_tokens_used: int

class UserSearch(BaseModel):
    discord_id: int
    full_discord_username: str


@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.post('/stripe_webhook')
async def stripe_webhook(request: Request):
    
    try:
        event = await request.json()
    except ValueError as e:
        # Invalid payload
        raise e
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        raise e
    
    # If a new charge comes in
    if event['type'] == 'charge.updated':
        squarespace_id = event['data']['object']['metadata']['id']
        
        headers = {
            'Authorization': f'Bearer {squarespace_key}',
            'User-Agent': 'foobar/2000',
        }
        response = requests.get(f'https://api.squarespace.com/1.0/commerce/orders/{squarespace_id}', headers=headers)
        data = json.loads(response.text)
        print("PROCESSING SUBSRCIPTION CHARGE")
        per_purchase(data)

    return {"Response": "Success"}


@app.post('/per_message')
async def per_message(per_message_item: PerMessageItem):
    per_message_item = per_message_item.dict()
    return per_message_db(per_message_item)


@app.post('/user_credit_info')
async def is_existing_user(user_credit_info_item: UserSearch):
    user_credit_info_item = user_credit_info_item.dict()
    return get_token_info(user_credit_info_item)


@app.post('/has_tokens')
async def has_tokens(has_tokens_item: UserSearch):
    has_tokens_item = has_tokens_item.dict()
    return check_tokens(has_tokens_item)
    