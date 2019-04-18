import requests
import logging
import json
import collections
from slackclient import SlackClient
from datetime import date, datetime
from tvmaze import get_episodes_for_date, create_db_session
from db_schema import Base, User, TV_Series, Follow

# setup logging
logger = logging.getLogger('main.slack')


def authenticate_slack(token_type):
    # token_type is either "bot_token" or "app_token", depending on needed permissions

    logger.info("Authenticating to Slack")

    config_file = 'config.json'
    config_data = import_json(config_file)
    token = config_data[token_type]
    slack_client = SlackClient(token)

    test_response = slack_client.api_call('api.test')
    if not test_response.get('ok'):
        # logger.error('API connection failed. Response error: <%s>', test_response.get('error'))
        exit()

    logger.info("Authentication complete.")
    return slack_client


# def send_watchlist_reports(watchlist_reports):

#     logger.info('Sending watchlist reports')

#     slack_client = authenticate_slack('bot_token')
 
#     for slack_id, user_report in watchlist_reports.items():
#         response = slack_client.api_call('im.open', user=slack_id)
#         if response.get('ok'):
#             channel_id = response.get('channel').get('id')
#             blocks = [
#                 {
#                     "type": "context",
#                     "elements": [
#                         {
#                             "type": "mrkdwn",
#                             "text": "Daily watchlist report"
#                         }
#                     ]
#                 },
#                 {
#                     "type": "section",
#                     "text": {
#                         "type": "mrkdwn",
#                         "text": user_report
#                     }
#                 }
#             ]
#             slack_client.api_call('chat.postMessage', channel=channel_id, blocks=blocks, as_user=True)
        
#         else:
#             logger.error("Unable to send watchlist report to <%s>. Response error: <%s>", slack_id, response.get('error'))

#     logger.info('Finished sending watchlist reports')

#     return


# def send_series_output(blocks, channel_id):

#     logger.info('Sending series output')

#     slack_client = authenticate_slack('bot_token')
#     response = slack_client.api_call('chat.postMessage', channel=channel_id, blocks=blocks, as_user=True)

#     logger.info('Finished sending series output')
#     logger.debug('Response from posting output: \n{}'.format(response))


def post_message(blocks, channel_id=None, slack_id=None, ephemeral=False):

    logger.info("Sending message to slack")
    slack_client = authenticate_slack('bot_token')

    if ephemeral:
        post_type = 'chat.postEphemeral'
    else:
        post_type = 'chat.postMessage'

    if not channel_id:
        response = slack_client.api_call('im.open', user=slack_id)
        if response.get('ok'):
            channel_id = response.get('channel').get('id')
    
    logger.info("Sending message to slack")
    response = slack_client.api_call(post_type, user=slack_id, channel=channel_id, blocks=blocks, as_user=True)
    logger.info('Finished posting message to Slack')
    logger.debug('Server response from posting output:\n{}'.format(response))


def delete_message(channel_id, message_ts):

    logger.info("Deleting message from slack")
    slack_client = authenticate_slack('bot_token')

    response = slack_client.api_call("chat.delete", channel=channel_id, ts=message_ts, as_user=True)
    logger.info("Finished deleting message")
    logger.debug('Server response from deleting message:\n{}'.format(response))

def import_json(file_path):

    with open(file_path, 'r') as file:
        data = json.loads(file.read())

    return data


