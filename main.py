import base64
import logging
import json
from calendar import monthrange
import datetime
from httplib2 import Http
from json import dumps
from google.auth import compute_engine
from apiclient import discovery

def handle_notification(event, context):
    """Triggered from a message on a Cloud Pub/Sub topic.
    Args:
         event (dict): Event payload.
         context (google.cloud.functions.Context): Metadata for the event.
    """
    pubsub_message = base64.b64decode(event['data']).decode('utf-8')
    logging.info('Budget information: {}'.format(pubsub_message))
    jsonPayload = json.loads(pubsub_message)
    costAmount = jsonPayload['costAmount']
    budgetAmount = jsonPayload['budgetAmount']
    percentOfBudget = round((costAmount/budgetAmount) * 100,2)
    budgetDisplayName = jsonPayload['budgetDisplayName']
    costIntervalStart = jsonPayload['costIntervalStart']
    
    #Determine the projectID from the budgetDisplayName
    projectID = budgetDisplayName[budgetDisplayName.find("sandbox-") + 15: len(budgetDisplayName)]
    logging.info('found projectID: {}'.format(projectID))

    if percentOfBudget >= 100:
        if disableBilling(projectID): #disabled billing successful, notify via chat of action
            message_text = "{}".format(budgetDisplayName) + ": DISABLED BILLING! {}".format(percentOfBudget) + "% of budget (${:,.2f}".format(costAmount) + "/${:,.2f}".format(budgetAmount) + ")"
            logging.info('message_text: {}'.format(message_text))
            sendChatMessage(message_text)
    else: #spend is below budget
        message_text = "{}".format(budgetDisplayName) + ": {}".format(percentOfBudget) + "% used (${:,.2f}".format(costAmount) + "/${:,.2f}".format(budgetAmount) + ")"
        logging.info('message_text: {}'.format(message_text))

def disableBilling(projectID):
    """
    Check if the billing is enabled for a given projectID
    :param projectID: projectID to cap costs for and check billing status
    :return: whether the billing was enabled for the given projectID
    """
    credentials = compute_engine.Credentials()

    # Using Python Google API Client Library to construct a Resource object for interacting with an API
    # The name and the version of the API to use can be found here https://developers.google.com/api-client-library/python/apis/
    billing_service = discovery.build('cloudbilling', 'v1', credentials=credentials, cache_discovery=False)

    # https://developers.google.com/resources/api-libraries/documentation/cloudbilling/v1/python/latest/cloudbilling_v1.projects.html#getBillingInfo
    billing_info = billing_service.projects().getBillingInfo(name='projects/{}'.format(projectID)).execute()
    if not billing_info or 'billingEnabled' not in billing_info: #billing has already been disabled
        return False
    else: #billing isn't disabled
        #Change to a blank billing account -- disables billing
        billing_info = billing_service.projects().updateBillingInfo(
            name='projects/{}'.format(projectID),
            body={'billingAccountName': ''}
        ).execute()
        logging.info('Disabled billing for {}'.format(projectID))        
        return True

def sendChatMessage(message_text):
    """
    Send a Chat Message to the Sandbox Alerts room
    :param message_text: Message to send
    :return: none
    """
    
    url = 'https://chat.googleapis.com/v1/spaces/alphanumberCode/messages?key=longAlphnumbericWebhookAddress'
    bot_message = {'text' : '{}'.format(message_text)}

    message_headers = { 'Content-Type': 'application/json; charset=UTF-8'}

    http_obj = Http()

    response = http_obj.request(
        uri=url,
        method='POST',
        headers=message_headers,
        body=dumps(bot_message),
    )
    logging.info('Message sent')
    logging.info('Response: {}'.format(response))    
