import os
import logging
from slackclient import SlackClient

# setup logging
logger = logging.getLogger('main.slack')

# authenticate with Slack
token = os.environ["SLACK_BOT_TOKEN"]
slack_client = SlackClient(token)

test_response = slack_client.api_call('api.test')
if not test_response.get('ok'):
    logger.error('API connection failed. Response error: <%s>', test_response.get('error'))


def post_message(blocks, channel_id=None, slack_id=None, ephemeral=False):

    logger.info("Sending message to slack")

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

    response = slack_client.api_call("chat.delete", channel=channel_id, ts=message_ts, as_user=True)
    logger.info("Finished deleting message")
    logger.debug('Server response from deleting message:\n{}'.format(response))


def post_dialog(dialog, trigger_id):

    logger.info("Posting dialog")
    response = slack_client.api_call("dialog.open", dialog=dialog, trigger_id=trigger_id)
    logger.info("Finished posting dialog")
    logger.debug("Server response from posting dialog:\n{}".format(response))


def post_file(channel_id, content, title):

    channels = [channel_id]
    logger.info("Posting spoiler content")
    response = slack_client.api_call("files.upload", content=content, title=title, channels=channels)
    logger.info("Finished posting spoiler content")
    logger.debug("Server response from posting spoiler content:\n{}".format(response))