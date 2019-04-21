import re
import logging
import tvmaze
import thetvdb
from threading import Thread
from slack import post_message, delete_message, post_dialog, post_file
from datetime import datetime, date
from flask import Flask, request, Response, jsonify, json

app = Flask(__name__)


# setup logging
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

fh = logging.FileHandler('jarvis_app.log')
fh.setLevel(logging.DEBUG)
fh.setFormatter(formatter)

ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
ch.setFormatter(formatter)

logger = logging.getLogger('main')
logger.setLevel(logging.DEBUG)
logger.addHandler(fh)
logger.addHandler(ch)


@app.route('/tv', methods=['POST'])
def create_search_box(channel_id=None, slack_id=None):

    logger.info("Creating search box")
    
    try:
        logger.debug("Request form: \n{}".format(request.form))
    except:
        pass

    blocks = [
        {          
            "type": "actions",
            "elements": [
                {
                    "action_id": "series_search",
                    "type": "external_select",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Search for TV series"
                    },
                    "min_query_length": 3
                }
            ]
        }
    ]
    if channel_id:
        post_message(blocks, channel_id=channel_id, slack_id=slack_id, ephemeral=True)
    else:  
        payload = {
            "response_type": "ephemeral",
            "blocks": blocks
        }
        return jsonify(payload)


def respond_to_series_request(series_id, channel_id, user_name, slack_id):

    series_data = tvmaze.get_series_data_via_id(series_id)
    blocks = format_series_output(series_data, user_name)
    post_message(blocks, channel_id=channel_id)
    create_search_box(channel_id, slack_id)


def format_series_output(series_data, user_name):

    series_name = series_data['name']
    logger.info("Formatting series output for {}".format(series_name))
    series_id = series_data['id']

    series_status = series_data['status']
    series_description = remove_html_tags(series_data['summary'])
    imdb_id = series_data["externals"]["imdb"]
    if imdb_id:
        imdb_base_url = "https://www.imdb.com/title/"
        imdb_url = imdb_base_url + imdb_id
        series_description += " (<{}|IMDB>)".format(imdb_url)

    tvdb_series_id = series_data['externals']['thetvdb']
    if not thetvdb.validate_series_id(tvdb_series_id):
        tvdb_series_id = thetvdb.find_series_id_via_imdb(imdb_id)
    image_url = thetvdb.get_series_banner(tvdb_series_id)
    if not image_url:
        image_url = series_data["image"]["original"]
        # image_url = series_data["image"]["medium"]

    if series_data.get("network"):
        network_name = series_data["network"]["name"]
    elif series_data.get("webChannel"):
        network_name = series_data["webChannel"]["name"]
    else:
        network_name = 'Unlisted Network'

    try:
        previous_episode_url = series_data['_links']['previousepisode']['href']
        previous_episode_output = format_episode_output(previous_episode_url)
    except:
        previous_episode_output = 'None'
    
    try:
        next_episode_url = series_data['_links']['nextepisode']['href']
        next_episode_output = format_episode_output(next_episode_url)
    except:
        if series_status == 'Ended':
            next_episode_output = 'Discontinued'
        else:
            next_episode_output = 'Unknown'

    blocks = [
        {
            "type": "image",
            "title": {
                "type": "plain_text",
                "text": series_name,
                "emoji": True
            },
            "image_url": image_url,
            "alt_text": "{} banner image".format(series_name)
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": series_description
            }
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": "*Status:* {}".format(series_status)
                },
                {
                    "type": "mrkdwn",
                    "text": "*Network:* {}".format(network_name)
                },
                {
                    "type": "mrkdwn",
                    "text": "*Previous Episode:*\n{}".format(previous_episode_output)
                },
                {
                    "type": "mrkdwn",
                    "text": "*Next Episode:*\n{}".format(next_episode_output)
                }
            ]
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "Requested by: {}".format(user_name)
                }
            ]
        },
        {
            "type": "actions",
            "block_id": "watchlist",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Add to watchlist :thumbsup:",
                        "emoji": True
                    },
                    "style": "primary",
                    "value": str(series_id),
                    "action_id": "add_to_watchlist"
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Remove from watchlist :thumbsdown:",
                        "emoji": True
                    },
                    "style": "danger",
                    "value": str(series_id),
                    "action_id": "remove_from_watchlist"
                }
            ]
        }
    ]

    logger.info('Finished formatting output for {}'.format(series_name))

    return blocks


def remove_html_tags(text):

    pattern = r"<\w{1,2}>|</\w{1,2}>"
    return re.sub(pattern, "", text)


def format_episode_output(episode_url):

    episode_data = tvmaze.get_episode_data(episode_url)
    season_number = str(episode_data.get('season'))
    episode_number = str(episode_data.get('number'))
    episode_date = episode_data.get('airdate')

    date_format = '%Y-%m-%d'
    episode_date_object = datetime.strptime(episode_date, date_format)
    today = datetime.combine(date.today(), datetime.min.time())
    
    delta_days = (episode_date_object - today).days

    if delta_days == 0:
        days_output = "today"
    elif delta_days == 1:
        days_output = "tomorrow"
    elif delta_days == -1:
        days_output = "yesterday"
    elif delta_days > 1:
        days_output = "in {} days".format(delta_days)
    elif delta_days < -1:
        days_output = "{} days ago".format(abs(delta_days))

    episode_output = "s{}.e{} | {}".format(season_number.zfill(2), episode_number.zfill(2), days_output)

    return episode_output


@app.route('/series-search', methods=['POST'])
def series_search():

    req = json.loads(request.form.get('payload'))
    text = req.get('value')
    logger.info("User search request for '{}' has been received.".format(text))
    payload = tvmaze.search_for_series(text)

    return jsonify(payload)


@app.route('/spoiler', methods=['POST'])
def create_spoiler_dialog():

    req = request.form
    logger.debug("/spoiler request received:\n{}".format(req))
    trigger_id = req["trigger_id"]

    ### Switch this to an dialog.open API call
    ### https://api.slack.com/methods/dialog.open
    ### Create new function for this in slack.py 

    # payload = {
    #     "trigger_id": trigger_id,
    #     "dialog": {
    #         "callback_id": "create_spoiler",
    #         "title": "Create a spoiler",
    #         "submit_label": "Post",
    #         "notify_on_cancel": True,
    #         "state": "placeholder",
    #         "elements": [
    #             {
    #                 "type": "text",
    #                 "label": "Spoiler title",
    #                 "name": "spoiler_text",
    #                 "placeholder": "Enter spoiler title here"
    #             },
    #             {
    #                 "type": "textarea",
    #                 "label": "Spoiler content",
    #                 "name": "spoiler_content",
    #                 "placeholder": "Enter spoiler content here"
    #             }
    #         ]
    #     }
    # }

    dialog = {
        "callback_id": "create_spoiler",
        "title": "Create a spoiler",
        "submit_label": "Post",
        "notify_on_cancel": True,
        "state": "placeholder",
        "elements": [
            {
                "type": "text",
                "label": "Spoiler subject",
                "name": "spoiler_subject",
                "placeholder": "Enter spoiler title here"
            },
            {
                "type": "textarea",
                "label": "Spoiler content",
                "name": "spoiler_body",
                "placeholder": "Enter spoiler content here"
            }
        ]
    }

    post_dialog(dialog, trigger_id)

    return '', 200


@app.route('/', methods=['POST'])
def inbound():

    logger.info("Inbound request from user received.")
    req = json.loads(request.form.get('payload'))
    logger.debug('Request data: \n{}'.format(req))

    user_name = req['user']['name']
    slack_id = req['user']['id']
    channel_id = req['channel']['id']
    callback_id = req.get('callback_id')
    action = req.get('actions')

    if action:
        action_id = action[0]['action_id']

        if action_id == 'series_search':
            series_id = action[0]['selected_option']['value']
            logger.info("Inbound request is a 'series_search'")
            t = Thread(target=respond_to_series_request, args=(
                series_id, channel_id, user_name, slack_id))
            logger.info ("Starting thread to generate series output")
            t.start()
            # delete_message(channel_id, message_ts)

        elif action_id == "add_to_watchlist":
            series_id = action[0]["value"]
            output_text = tvmaze.add_series_to_watchlist(series_id, slack_id, user_name)
            blocks = format_response_blocks(output_text)
            post_message(blocks, channel_id=channel_id, slack_id=slack_id, ephemeral=True)

        elif action_id == "remove_from_watchlist":
            series_id = action[0]["value"]
            output_text = tvmaze.remove_series_from_watchlist(series_id, slack_id)
            blocks = format_response_blocks(output_text)
            post_message(blocks, channel_id=channel_id, slack_id=slack_id, ephemeral=True)

    if callback_id:
        if callback_id == "create_spoiler":
            subject = req['submission']['spoiler_subject']
            body = req['submission']['spoiler_body']
            title, content = format_spoiler_output(subject, body, user_name)
            post_file(channel_id, content, title)

    logger.info('Sending HTTP Status 200 to requesting server')
    return '', 200


def format_response_blocks(text):

    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": text
            }
        }
    ]

    return blocks


def format_spoiler_output(subject, body, user_name):

    title = "Spoiler: {} | By: {}".format(subject, user_name)
    content = "SPOILER SUBJECT: {}\nAUTHOR: {}\nExpand spoiler at your own risk.\n\n\n{}".format(subject, user_name, body)

    return title, content


@app.route('/', methods=['GET'])
def test():
    return Response('Nothing to see here. Move along!')


if __name__ == "__main__":
    app.run()



# 1.0 FEATURES

    # Initial TV series payload is ephemeral. Provide ability to post to channel.
        # Put payload (minus push to channel button) into value of Push to Channel button

    # watchlist notifications
        # Daily report
            # Today
            # Next 7 days
            # Further out (?)
            # Unscheduled
            # Cancelled (with remove button)
            # if season premier (ep1) add party hats

    # mass watchlist management
        # sort by alphabetical
        # include unfollow buttons

    # implement logging

    # fix html tag removal for situations like "Friends" description -- use RegEx
        # "<p>Six young (20-something) people from New York City (Manhattan), on their own and struggling to survive in the real world, find the companionship, comfort and support they get from each other to be the perfect antidote to the pressures of life.</p><p>This average group of buddies goes through massive mayhem, family trouble, past and future romances, fights, laughs, tears and surprises as they learn what it really means to be a friend.</p>"

    # create .env file and install dotenv module
        # https://www.digitalocean.com/community/tutorials/how-to-write-a-slash-command-with-flask-and-python-3-on-ubuntu-16-04


# REFACTORING

    # dedupe series search functions in tvmaze.py


# BEYOND 1.0 ROADMAP

# Perform internal fuzzy searches (rather than API calls)
    # Update list of TV shows through daily pull
    # Do fuzzy searches against that

# Usage tracking
    # How often commands are used and by how many users

# Use banner images from TheTVDB (rather than vertical images)


