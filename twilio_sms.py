
from dotenv import load_dotenv

load_dotenv()

import os

account_sid = os.environ["TWILIO_ACCOUNT_SID"]
auth_token = os.environ["TWILIO_AUTH_TOKEN"]
twilio_phone_address = os.environ["TWILIO_ADDRESS"]

import requests
from requests.auth import HTTPBasicAuth

# sends a text!
def send_text_through_twilio(phone_number=twilio_phone_address,text_message='Hello world'):
    requests.post(f'https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json', auth=HTTPBasicAuth(account_sid, auth_token), data={'To': phone_number, 'From': twilio_phone_address, 'Body': text_message})

