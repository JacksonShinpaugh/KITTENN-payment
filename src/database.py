from dotenv import load_dotenv
load_dotenv()

from supabase import create_client
import os


# connect to database
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
client = create_client(url, key)


def update_tokens(customer_id, tokens):
        # update token balance
        token_info = list(client.table("tokens").select("token_balance", "total_token_usage").eq("customer_id", customer_id).execute())[0][1][0]
        existing_tokens = token_info['token_balance']
        token_usage = token_info['total_token_usage']
        client.table("tokens").update({
            "token_balance": existing_tokens - tokens,
            "total_token_usage": token_usage + tokens
        }).eq("customer_id", customer_id).execute()


def per_purchase(data):
    email = data['customerEmail']
    first_name = data['billingAddress']['firstName']
    last_name = data['billingAddress']['lastName']
    address_1 = data['billingAddress']['address1']
    address_2 = data['billingAddress']['address2']
    city = data['billingAddress']['city']
    state = data['billingAddress']['state']
    country = data['billingAddress']['countryCode']
    postal_code = data['billingAddress']['postalCode']
    sku = data['lineItems'][0]['sku']
    discord_username = data['formSubmission'][0]['value']
    subscription_info = list(client.table("subscriptions").select("id", "tokens", "price").eq("sku", sku).execute())[0][1][0]
    subscription_id = subscription_info['id']
    tokens = subscription_info['tokens']
    price = subscription_info['price']

    # if discord_username does not exist in database
    if not list(client.table("customers").select("id").eq("discord_username", discord_username).execute())[0][1]:
        # if email also does not exist in database
        if not list(client.table("customers").select("id").eq("email", email).execute())[0][1]:
            '''
            FIRST TIME PURCHASE
            '''
            # insert into customers 
            client.table("customers").insert({
                "discord_username": discord_username,
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "address_1": address_1,
                "address_2": address_2,
                "city": city,
                "state": state,
                "country": country,
                "postal_code": postal_code
            }).execute()
            customer_id = list(client.table("customers").select("id").eq("discord_username", discord_username).execute())[0][1][0]['id']
            
            # insert into tokens
            client.table('tokens').insert({
                "customer_id": customer_id,
                "subscription_id": subscription_id,
                "token_balance": tokens,
                "total_token_usage": 0
            }).execute()
        # discord_username does not exist but email does exist
        else:
            '''
            EXISTING CUSTOMER CHANGED DISCORD USERNAME
            '''
            customer_id = list(client.table("customers").select("id").eq("email", email).execute())[0][1][0]['id']
            token_info = list(client.table("tokens").select("token_balance", "subscription_id").eq("customer_id", customer_id).execute())[0][1][0]
            existing_tokens = token_info['token_balance']
            existing_subscription_id = token_info['subscription_id']
            # update discord username
            client.table("customers").update({
                "discord_username": discord_username
            }).eq("id", customer_id).execute()

            if 'otp' in sku and existing_subscription_id > 1 and existing_subscription_id <= 4:
                # don't update subscription id
                client.table('tokens').update({
                    "token_balance": existing_tokens + tokens
                }).eq("customer_id", customer_id).execute()  

            else:
                # update token balance
                client.table('tokens').update({
                    "subscription_id": subscription_id,
                    "token_balance": existing_tokens + tokens
                }).eq("customer_id", customer_id).execute()
            

    # if discord_username does exist
    else:
        # if email doesn't exist, it is a free tier customer that bought sub
        if not list(client.table("customers").select("id").eq("email", email).execute())[0][1]:
            '''
            FREE TIER CUSTOMER THAT JUST BOUGHT SUBSCRIPTION
            '''
            # insert into customers
            client.table("customers").update({
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "address_1": address_1,
                "address_2": address_2,
                "city": city,
                "state": state,
                "country": country,
                "postal_code": postal_code
            }).eq("discord_username", discord_username).execute()

            customer_id = list(client.table("customers").select("id").eq("discord_username", discord_username).execute())[0][1][0]['id']
            token_info = list(client.table("tokens").select("token_balance", "subscription_id").eq("customer_id", customer_id).execute())[0][1][0]
            existing_tokens = token_info['token_balance']

            # insert into tokens
            client.table('tokens').update({
                "subscription_id": subscription_id,
                "token_balance": existing_tokens + tokens
            }).eq("customer_id", customer_id).execute()

        # if email does exist, it is a recurring subscription charge
        else:
            customer_id = list(client.table("customers").select("id").eq("discord_username", discord_username).execute())[0][1][0]['id']
            token_info = list(client.table("tokens").select("token_balance", "subscription_id").eq("customer_id", customer_id).execute())[0][1][0]
            existing_tokens = token_info['token_balance']
            existing_subscription_id = token_info['subscription_id']

            if 'otp' in sku and existing_subscription_id > 1 and existing_subscription_id <= 4:
                '''
                CUSTOMER WITH SUBSCRIPTION BUYS ONE TIME PURCHASE OF TOKENS
                '''
                # don't update subscription id
                client.table('tokens').update({
                    "token_balance": existing_tokens + tokens
                }).eq("customer_id", customer_id).execute()  

            else:
                '''
                RECURRING SUBSCRIPTION CHARGE
                '''
                # update token balance
                client.table('tokens').update({
                    "subscription_id": subscription_id,
                    "token_balance": existing_tokens + tokens
                }).eq("customer_id", customer_id).execute()           

    # insert into purchases
    client.table('purchases').insert({
        "customer_id": customer_id,
        "subscription_id": subscription_id,
        "amount": price
    }).execute()


def per_message_db(per_message_item):
    new_user = False
    discord_id = per_message_item["discord_id"]
    discord_username = per_message_item["full_discord_username"]
    tokens = per_message_item["openai_tokens_used"]
    print(discord_id)
    print(discord_username)
    print(tokens)

    free_tokens = 7000
    # search for discord_id in customers table, if comes back empty,
    if not list(client.table("customers").select("id").eq("discord_id", discord_id).execute())[0][1]:

        # search for discord_username, if comes back empty it is new user on free tier
        if not list(client.table("customers").select("id").eq("discord_username", discord_username).execute())[0][1]:

            # add available info to customers table and insert free tokens
            client.table("customers").insert({
                "discord_id": discord_id,
                "discord_username": discord_username
            }).execute()
            customer_id = list(client.table("customers").select("id").eq("discord_username", discord_username).execute())[0][1][0]['id']
            new_user = True
            # add tokens to customer account
            client.table("tokens").insert({
                "customer_id": customer_id,
                "subscription_id": 1,    # change subscription_id to whatever it is in production
                "token_balance": free_tokens - tokens,
                "total_token_usage": tokens
            }).execute()
        
        # if discord_username comes back with a hit
        else:
            customer_id = list(client.table("customers").select("id").eq("discord_username", discord_username).execute())[0][1][0]['id']
            # update customer info with discord_id
            client.table("customers").update({
                "discord_id": discord_id 
            }).eq("id", customer_id).execute()

            # update token balance
            update_tokens(customer_id, tokens)
    else:
        # search for discord_username, if comes back empty, the customer changed their username
        if not list(client.table("customers").select("id").eq("discord_username", discord_username).execute())[0][1]:
            # update username
            client.table("customers").update({
                "discord_username": discord_username
            }).eq("discord_id", discord_id).execute()

        # update token balance
        customer_id = list(client.table("customers").select("id").eq("discord_id", discord_id).execute())[0][1][0]['id']
        update_tokens(customer_id, tokens)
    return {"new_user": new_user}


def get_token_info(user_credit_info_item):
    discord_id = user_credit_info_item['discord_id']
    # get customer_id
    customer_id = list(client.table("customers").select('id').eq("discord_id", discord_id).execute())[0][1][0]['id']
    # retrieve credit info
    customer_info = list(client.table("tokens").select("token_balance", "subscription_id").eq("customer_id", customer_id).execute())[0][1][0]
    token_balance = customer_info['token_balance']
    subscription = list(client.table("subscriptions").select("title").eq("id", customer_info['subscription_id']).execute())[0][1][0]['title']
    return {"total_tokens": token_balance, "sub_tier": subscription}
    


def check_tokens(has_tokens_item):
    has_tokens = True
    discord_id = has_tokens_item['discord_id']

    if not list(client.table("customers").select('id').eq("discord_id", discord_id).execute())[0][1]:
        has_tokens = True
        return {"has_tokens": has_tokens}

    customer_id = list(client.table("customers").select('id').eq("discord_id", discord_id).execute())[0][1][0]['id']
    customer_tokens = list(client.table("tokens").select("token_balance").eq("customer_id", customer_id).execute())[0][1][0]['token_balance']

    if customer_tokens <= 0:
        has_tokens = False

    return {"has_tokens": has_tokens}