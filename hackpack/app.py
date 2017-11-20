import re

from flask import Flask
from flask import render_template
from flask import url_for
from flask import request
from flask import session
import random
import json
import os
import redis

from twilio import twiml
from twilio.util import TwilioCapability

# Declare and configure application
app = Flask(__name__, static_url_path='/static')
app.secret_key = '2F34255D3EC24192CABC88752C88A2AED9825B9C2C49C7E013644E647596CC73'
app.config.from_pyfile('local_settings.py')

redis_url = os.getenv('REDISTOGO_URL', 'redis://localhost:6379')
redis = redis.from_url(redis_url)

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
restListFile = os.path.join(PROJECT_ROOT, 'restaurants.json')

numbers = []
restList = []

@app.before_first_request
def startup():
    global numbers
    global restList
    global restListFile
    if redis.get('nums') is not None:
        numbers_json = redis.get('nums')
        numbers = json.loads(numbers_json)
    # attempt to pull from redis
    if redis.get('restList') is None:
        data = json.load(open(restListFile))
        restList = data["list"]
        json_data = json.dumps(restList)
        redis.set('restList', json_data)
        print("saved rest list")
        print("printing...")
        print(json.loads(redis.get('restList')))
    else:
        restList = json.loads(redis.get('restList'))
        print("got rest list")
        print(restList)

# Voice Request URL
@app.route('/voice', methods=['GET', 'POST'])
def voice():
    response = twiml.Response()
    response.say("Welcome to RootRec. We do not support voice at this time. Sorry.")
    return str(response)


# SMS Request URL
@app.route('/sms1', methods=['GET'])
def sms():
    response = twiml.Response()
    response.sms("Nothing here")
    return str(response)

# SMS Request URL
@app.route('/sms', methods=['GET'])
def smsGet():
    response = twiml.Response()
    response.sms('Welcome to RootRec! Your number has been added to the list. Reply with "Stop" at any time to be removed from this service!')
    return str(response)

# SMS Request URL
@app.route('/sms', methods=['POST'])
def smsPost():
    global numbers
    global restList
    # setup response
    response = twiml.Response()
    # pull basic data from every message
    body = request.form['Body'].lower()
    num = request.form['From']
    # cookie data
    lastRecIndex = session.get('lastrec', -1)
    if num not in numbers:
        response.sms('Welcome to RootRec! Your number has been added to the list. Reply with "Stop" at any time to be removed from this service')
        numbers.append(num)
        json_data = json.dumps(numbers)
        redis.set("nums", json_data)
    elif "yes" in body: # handle follow up response
        if lastRecIndex == -1:
            response.sms("Sorry, something went wrong")
        else:
            rest = restList[lastRecIndex]
            response.sms("Great choice! {} is at {}, you can call them at {}".format(rest["name"], rest["addr"], rest["phone"]))
    else:
        rest = random.choice(restList)
        index = restList.index(rest)
        session['lastrec'] = index
        randNum = random.randrange(1, 3)
        opt = "opt" + str(randNum)
        optPrice = "opt" + str(randNum) + "price"
        response.sms('Hello, here is a healthy option nearby: you could go to "{}" and get "{}" for {}. Reply with "next" for another option, or "yes" to get the address.'.format(rest["name"], rest[opt], rest[optPrice]))
    return str(response)

# Twilio Client demo template
@app.route('/client')
def client():
    configuration_error = None
    for key in ('TWILIO_ACCOUNT_SID', 'TWILIO_AUTH_TOKEN', 'TWILIO_APP_SID',
                'TWILIO_CALLER_ID'):
        if not app.config.get(key, None):
            configuration_error = "Missing from local_settings.py: " \
                                  "{0}".format(key)
            token = None

    if not configuration_error:
        capability = TwilioCapability(app.config['TWILIO_ACCOUNT_SID'],
                                      app.config['TWILIO_AUTH_TOKEN'])
        capability.allow_client_incoming("joey_ramone")
        capability.allow_client_outgoing(app.config['TWILIO_APP_SID'])
        token = capability.generate()
    params = {'token': token}
    return render_template('client.html', params=params,
                           configuration_error=configuration_error)


@app.route('/client/incoming', methods=['POST'])
def client_incoming():
    try:
        from_number = request.values.get('PhoneNumber', None)

        resp = twiml.Response()

        if not from_number:
            resp.say("Your app is missing a Phone Number. "
                     "Make a request with a Phone Number to make outgoing "
                     "calls with the Twilio hack pack.")
            return str(resp)

        if 'TWILIO_CALLER_ID' not in app.config:
            resp.say(
                "Your app is missing a Caller ID parameter. "
                "Please add a Caller ID to make outgoing calls with Twilio "
                "Client")
            return str(resp)

        with resp.dial(callerId=app.config['TWILIO_CALLER_ID']) as r:
            # If we have a number, and it looks like a phone number:
            if from_number and re.search('^[\d\(\)\- \+]+$', from_number):
                r.number(from_number)
            else:
                r.say("We couldn't find a phone number to dial. Make sure "
                      "you are sending a Phone Number when you make a "
                      "request with Twilio Client")

        return str(resp)

    except:
        resp = twiml.Response()
        resp.say("An error occurred. Check your debugger at twilio dot com "
                 "for more information.")
        return str(resp)


# Installation success page
@app.route('/')
def index():
    params = {
        'Voice Request URL': url_for('.voice', _external=True),
        'SMS Request URL': url_for('.sms', _external=True),
        'Client URL': url_for('.client', _external=True)}
    return render_template('index.html', params=params,
                           configuration_error=None)
