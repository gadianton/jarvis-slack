import os
import logging
from slackclient import SlackClient

# setup logging
logger = logging.getLogger('main.slack')


def authenticate_slack():

    logger.info("Authenticating to Slack")

    token = os.environ["SLACK_BOT_TOKEN"]
    slack_client = SlackClient(token)

    test_response = slack_client.api_call('api.test')
    if not test_response.get('ok'):
        # logger.error('API connection failed. Response error: <%s>', test_response.get('error'))
        exit()

    logger.info("Authentication complete.")
    return slack_client


def post_message(blocks, channel_id=None, slack_id=None, ephemeral=False):

    logger.info("Sending message to slack")
    slack_client = authenticate_slack()

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
    slack_client = authenticate_slack()

    response = slack_client.api_call("chat.delete", channel=channel_id, ts=message_ts, as_user=True)
    logger.info("Finished deleting message")
    logger.debug('Server response from deleting message:\n{}'.format(response))