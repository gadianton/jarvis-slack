# Generating a Slack response payload:
# https://api.slack.com/slash-commands#responding_to_a_command

# Creating a Slack message attachment:
# https://api.slack.com/docs/message-attachments#attachment_structure

import os
import logging
import tvmaze
import xml.etree.cElementTree as ET
from datetime import datetime
from slackclient import SlackClient
from flask import Flask, request, Response, jsonify, json
from sys import exit


# Declare constants
# It's possible I may need to add in env variables for Client_id and Client_secret
# https://api.slack.com/docs/verifying-requests-from-slack
# https://slackapi.github.io/python-slackclient/auth.html#handling-tokens

app = Flask(__name__)
# # VERIFICATION_TOKEN = os.environ.get('JARVIS_VERIFICATION_TOKEN')
# # SIGNING_SECRET = os.environ.get('JARVIS_SIGNING_SECRET')
# # BOT_OAUTH_TOKEN = os.environ.get('JARVIS_BOT_OAUTH')
# OAUTH_TOKEN = os.environ.get('JARVIS_OAUTH_TOKEN')
# slack_client = SlackClient(OAUTH_TOKEN)

headers = {
    'Content-Type': 'application/json',
}

# setup logging
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

fh = logging.FileHandler('jarvis_app.log')
fh.setLevel(logging.DEBUG)
fh.setFormatter(formatter)

ch = logging.StreamHandler()
ch.setLevel(logging.WARNING)
ch.setFormatter(formatter)

logger = logging.getLogger('main')
logger.setLevel(logging.DEBUG)
logger.addHandler(fh)
logger.addHandler(ch)


@app.route('/tv', methods=['POST'])
def tv_main_menu():

    payload = {
        "response_type": "ephemeral",
        "text": "Would you like to *search* for a TV show or view your *watchlist*?",
        "attachments": [
            {
                "fallback": "Upgrade your Slack client to use this feature.",
                "callback_id": "tv_main_menu",
                "color": "black",
                "actions": [
                    {
                        "name": "search",
                        "type": "button",
                        "text": "Search",
                        "value": "search"
                    },
                    {
                        "name": "watchlist",
                        "type": "button",
                        "text": "Watchlist",
                        "value": "watchlist"
                    }
                ]
            }       
        ]
    }

    return jsonify(payload)


def create_search_box():

    payload = {
        "text": "TV Show Search",
        "response_type": "in_channel",
        "attachments": [
            {
                "fallback": "Upgrade your Slack client to use this feature.",
                "color": "3AA3E3",
                "attachment_type": "default",
                "callback_id": "series_search",
                "actions": [
                    {
                        "name": "user_input",
                        "text": "Search for TV show",
                        "type": "select",
                        "data_source": "external",
                        "min_query_length": 3,
                    }
                ]
            }
        ]
    }

    return payload


def get_series_data():
    # if request.form.get('token') == VERIFICATION_TOKEN:
    user_input = request.form.get('text')
    user_name = request.form.get('user_name')
    user_id = request.form.get('user_id')

    if user_input.lower() == 'watchlist':
        payload = tvmaze.create_watchlist_output(user_id)
    else:
        series_data = tvmaze.get_series_data(user_input)
    
        # Need change how API calls through tvmaze.py work
        if type(series_data) == str:
            payload = {
                "attachments": [
                    {
                        "color": "danger",
                        "title": "Series not found",
                        "text": series_data
                    }
                ]
            }

        else:
            payload = create_series_output(series_data, user_name)
    
    return jsonify(payload)


def create_series_output(series_data, user_name):

    image_url = series_data.get('image').get('medium')
    series_name = series_data.get('name')

    # Canceled = :no_entry_sign:
    # Running = :white_check_mark:
    series_status = series_data.get('status')
    if series_status == 'Running':
        footer_icon = 'http://icons.iconarchive.com/icons/paomedia/small-n-flat/1024/sign-check-icon.png'
    else:
        footer_icon = 'http://www.newdesignfile.com/postpic/2013/10/transparent-red-x-icon_293199.png'

    try:
        network_name = series_data.get('network').get('name')
    except:
        network_name = 'Unlisted Network'

    series_description = remove_html_tags(series_data.get('summary'))
    series_description_output = '_' + network_name + '_\n' + series_description

    try:
        previous_episode_url = series_data.get('_links').get('previousepisode').get('href')
        previous_episode_output = create_episode_output(previous_episode_url)
    except:
        previous_episode_output = 'None'
    
    try:
        next_episode_url = series_data.get('_links').get('nextepisode').get('href')
        next_episode_output = create_episode_output(next_episode_url)
    except:
        if series_status == 'Running':
            next_episode_output = 'Unknown'
        else:
            next_episode_output = 'Canceled'

    # Slack message builder URL for testing
    # https://api.slack.com/docs/messages/builder?msg=%7B%22attachments%22%3A%5B%7B%22fallback%22%3A%22Required%20plain-text%20summary%20of%20the%20attachment.%22%2C%22color%22%3A%22black%22%2C%22image_url%22%3A%22http%3A%2F%2Fstatic.tvmaze.com%2Fuploads%2Fimages%2Fmedium_portrait%2F152%2F381152.jpg%22%2C%22title%22%3A%22Westworld%22%2C%22title_link%22%3A%22https%3A%2F%2Fwww.tvmaze.com%2Fshows%2F1371%2Fwestworld%22%2C%22text%22%3A%22(HBO)%5CnWestworld%20is%20a%20dark%20odyssey%20about%20the%20dawn%20of%20artificial%20consciousness%20and%20the%20evolution%20of%20sin.%20Set%20at%20the%20intersection%20of%20the%20near%20future%20and%20the%20reimagined%20past%2C%20it%20explores%20a%20world%20in%20which%20every%20human%20appetite%2C%20no%20matter%20how%20noble%20or%20depraved%2C%20can%20be%20indulged.%22%2C%22fields%22%3A%5B%7B%22title%22%3A%22Previous%20Episode%22%2C%22value%22%3A%22Season%202%20Ep%206%5Cn2018-09-05%20(3%20days%20ago)%22%2C%22short%22%3Atrue%7D%2C%7B%22title%22%3A%22Next%20Episode%22%2C%22value%22%3A%22Season%202%20Ep%207%5Cn2018-09-05%20(in%203%20days)%22%2C%22short%22%3Atrue%7D%5D%2C%22footer%22%3A%22Status%3A%20Cancelled%22%2C%22footer_icon%22%3A%22http%3A%2F%2Fwww.newdesignfile.com%2Fpostpic%2F2013%2F10%2Ftransparent-red-x-icon_293199.png%22%2C%22actions%22%3A%5B%7B%22type%22%3A%22button%22%2C%22text%22%3A%22Add%20Westworld%20to%20watchlist%22%2C%22url%22%3A%22https%3A%2F%2Fflights.example.com%2Fbook%2Fr123456%22%2C%22style%22%3A%22primary%22%7D%5D%7D%5D%7D
    payload = {
        "response_type": "in_channel",
        "attachments": [
            {
                "fallback": "Upgrade your Slack client to use this feature.",
                "callback_id": "watchlist",
                "color": "black",
                "image_url": image_url,
                "author_name": "From: @" + user_name,
                "title": series_name,
                "text": series_description_output,
                "fields": [
                    {
                        "title": "Previous Episode",
                        "value": previous_episode_output,
                        "short": True
                    },
                    {
                        "title": "Next Episode",
                        "value": next_episode_output,
                        "short": True
                    }
                ],
                "footer": "Status: " + series_status,
                "footer_icon": footer_icon,
                "actions": [
                    {
                        "name": "follow",
                        "type": "button",
                        "text": "Follow",
                        "value": series_name,
                        "style": "primary"
                    },
                    {
                        "name": "unfollow",
                        "type": "button",
                        "text": "Unfollow",
                        "value": series_name,
                        "style": "danger"
                    }
                ]
            }       
        ]
    }

    return payload


def remove_html_tags(text):

    try:
        output_text = ''.join(ET.fromstring(text).itertext())
    except:
        output_text = text
        # LOG ERROR MESSAGE

    return output_text


def create_episode_output(episode_url):

    episode_data = tvmaze.get_episode_data(episode_url)
    season_number = str(episode_data.get('season'))
    episode_number = str(episode_data.get('number'))
    episode_date = episode_data.get('airdate')

    date_format = '%Y-%m-%d'
    episode_date_object = datetime.strptime(episode_date, date_format)
    today = datetime.today()

    if today >= episode_date_object:
        delta_days = str((today - episode_date_object).days)
    else:
        delta_days = str((episode_date_object - today).days)

    episode_output = 'Season ' + season_number + ' Ep ' + episode_number + '\n' + episode_date + ' (' + delta_days + ' days)'

    return episode_output


@app.route('/series-search', methods=['POST'])
def series_search():

    req = json.loads(request.form.get('payload'))
    text = req.get('value')
    print ("User search request for " + text + " has been received.")
    payload = tvmaze.search_for_series(text)

    return jsonify(payload)


@app.route('/', methods=['POST'])
def inbound():

    req = json.loads(request.form.get('payload'))
    callback_id = req.get('callback_id')
    user_name = req.get('user').get('name')
    user_id = req.get('user').get('id')

    if callback_id == 'tv_main_menu':
        action = req.get('actions')[0].get('name')
        if action == 'search':
            payload = create_search_box()
        elif action == 'watchlist':
            print ("Received request for watchlist for user id: " + user_id)
            payload = tvmaze.create_watchlist_output(user_id)
    
    elif callback_id == 'series_search':
        series_id = req.get('actions')[0].get('selected_options')[0].get('value')
        series_data = tvmaze.get_series_data_via_id(series_id)
        payload = create_series_output(series_data, user_name)

    elif callback_id == 'watchlist':
        action = req.get('actions')[0].get('name')
        series_name = req.get('actions')[0].get('value')
        if action == 'follow':
            output_text = tvmaze.follow_series(series_name, user_id, user_name)
            payload = {
                'response_type:': 'ephemeral',
                'replace_original': False,
                'text': output_text
            }
        elif action == 'unfollow':
            output_text = tvmaze.unfollow_series(series_name, user_id, user_name)
            payload = {
                'response_type:': 'ephemeral',
                'replace_original': False,
                'text': output_text
            }

    return jsonify(payload)


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


