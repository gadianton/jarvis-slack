import json
import requests
import re
import os
import logging
from datetime import datetime, date
from db_schema import Base, User, TV_Series, Follow, create_db_session

# setup logging
logger = logging.getLogger('main.tvmaze')

# Constants
API_URL = 'https://api.tvmaze.com'


def search_for_series(text):
    # series_search_url = API_URL + '/search/shows?q=' + parse.quote_plus(text)
    series_search_url = API_URL + '/search/shows?q=' + text
    payload = {
        'options': []
    }

    logger.info('Starting dynamic search for \'' + text + '\'')

    search_results = requests.get(series_search_url)
    status_code = search_results.status_code

    if status_code == 429:
        return ("The servers are busy. Try again in a few seconds.")

    series_list = search_results.json()
    
    # if series_list.count >= 3:
    #     for_loop_count = 3:
    # else:
    #     for_loop_count = series_list.count

    logger.info('Filtering out weak matches...')
    
    for series in series_list:
        if series.get('score') >= 3:
            series_name = series.get('show').get('name')
            series_id = str(series.get('show').get('id'))
            try:
                series_year = ' (' + series.get('show').get('premiered')[0:4] + ')'
            except:
                series_year = ''
            
            series_output = series_name + series_year
            option = {
                'text': {
                    'type': 'plain_text',
                    'text': series_output
                },
                'value': series_id
            }
            payload['options'].append(option)

    logger.info('Lookahead payload is complete')
    logger.debug('Payload contents:\n{}'.format(payload))

    return payload


def get_series_data_via_id(series_id):
    logger.info("Looking up series_id '{}'".format(series_id))
    series_lookup_url = API_URL + '/shows/{}'.format(series_id)

    series_data = requests.get(series_lookup_url)
    status_code = series_data.status_code

    if status_code == 429:
        return ("The servers are busy. Try again in a few seconds.")
    
    logger.info("Found TV series for series_id '{}'".format(series_id))
    logger.debug("Series data:\n{}".format(series_data.json()))

    return series_data.json()


def get_series_data(series_name):

    # TVmaze uses a scoring system to determine the best TV series match for a user's search.
    # This search will return a dictionary object with information about the matched series.

    #series_search_url = API_URL + '/singlesearch/shows?q=' + parse.quote_plus(series_name)
    series_search_url = API_URL + '/singlesearch/shows?q=' + series_name

    logger.info("Beginning a new search for '<%s>'", series_name)

    series_data = requests.get(series_search_url)
    status_code = series_data.status_code

    if status_code == 404:
        return ("I was unable to find '" + series_name + "'.")
    elif status_code == 429:
        return ("The servers are busy. Try again in a few seconds.")
    
    logger.info("Found series data for {}".format(series_name))

    return series_data.json()


def get_episode_data(episode_url):

    logger.info("Requesting episode found at " + episode_url)

    episode_data = requests.get(episode_url)

    logger.info("Found episode.")
    logger.debug("Episode data:\n{}".format(episode_data.json()))

    return episode_data.json()


def add_series_to_watchlist(series_id, user_id, user_name):
    series_data = get_series_data_via_id(series_id)
    series_name = series_data['name']

    # Pass along message to user if response isn't a dictionary (i.e. doesn't contain data)
    # This is usually the result of a 404 status code when searching for a TV series match
    if type(series_data) != dict:
        return series_data

    session = create_db_session()

    logger.info("Checking to see if TV Series and User already exist in the database...")
    tv_series = session.query(TV_Series). \
        filter_by(tvmaze_id=series_id). \
        first()
    user = session.query(User). \
        filter_by(slack_id=user_id). \
        first()

    if not tv_series:
        logger.info("TV Series '" + series_name + "' with "
            "ID '" + str(series_id) + "' did not exist in database. Creating"
            " an entry now.")
        
        try:
            next_episode_api_url = series_data['_links']['nextepisode']['href']
        except KeyError:
            next_episode_api_url = None
            next_episode_season = None
            next_episode_number = None
            next_episode_name = None
            next_episode_date = None

        if next_episode_api_url:
            episode_data = requests.get(next_episode_api_url).json()
            next_episode_season = episode_data.get('season')
            next_episode_number = episode_data.get('number')
            next_episode_name = episode_data.get('name')
            next_episode_date = datetime.strptime(episode_data.get('airdate'), '%Y-%m-%d')

        tv_series = TV_Series(
            tvmaze_id=series_id,
            name=series_name,
            status=series_data.get('status'),
            api_url=series_data['_links'].get('self')['href'],
            next_episode_season=next_episode_season,
            next_episode_number=next_episode_number,
            next_episode_name=next_episode_name,
            next_episode_date=next_episode_date,
            next_episode_api_url=next_episode_api_url
        )
        session.add(tv_series)

    if not user:
        logger.info("User '" + str(user_id) + "' did not exist in database. Creating an entry now.")
        user = User(
            slack_id=user_id,
            slack_name=user_name)
        session.add(user)

    follow_status = session.query(Follow). \
        filter_by(tv_series_id=tv_series.id). \
        filter_by(user_id=user.id). \
        first()

    if not follow_status:
        logger.info("User '" + str(user.slack_id) + "' and TV Series '" + \
              tv_series.name + "' did not have a joint table entry. Creating an entry now.")
        follow_status = Follow(
            tv_series_id=tv_series.id,
            user_id=user.id,
            is_following=True)
        session.add(follow_status)
        output_text = "_You are now following " + tv_series.name + " and " + \
                      "will receive notification before a new episode airs._"

    elif follow_status.is_following:
        output_text = "_You are already following " + tv_series.name + "._"

    else:
        session.query(Follow). \
            filter_by(tv_series_id=follow_status.tv_series_id). \
            filter_by(user_id=follow_status.user_id). \
            update({'is_following': True})
        output_text = "_You are now following " + tv_series.name + " and " + \
                      "will receive notification before a new episode airs._"

    session.commit()
    session.close()

    return output_text


def remove_series_from_watchlist(series_id, user_id):

    """
    * lookup TV series (get ID)
    * match ID against tvmaze_id in database
    * query the relationship between tv_series_id and user_id
    * if is_following is already false, tell user
    * otherwise, set is_following to false and notify user
    """

    session = create_db_session()

    tv_series = session.query(TV_Series). \
        filter_by(tvmaze_id=series_id). \
        first()

    if not tv_series:
        session.close()
        output_text = "_Congratulations! You're already *not* following " + series_name + "._"
        return output_text

    user = session.query(User). \
        filter_by(slack_id=user_id). \
        first()

    follow_status = session.query(Follow). \
        filter_by(tv_series_id=tv_series.id). \
        filter_by(user_id=user.id). \
        first()

    if not follow_status or follow_status.is_following == False:
        response_string = "_Congratulations! You're already *not* following " + \
                          tv_series.name + "._"
        session.close()
        return response_string
    else:
        session.query(Follow). \
            filter_by(tv_series_id=follow_status.tv_series_id). \
            filter_by(user_id=follow_status.user_id). \
            update({'is_following': False})

    response_string = "_You will no longer receive notifications for " + \
                       tv_series.name + " and are entitled to all the benefits " + \
                      "(or lack) thereof._"

    session.commit()
    session.close()

    return response_string


def create_watchlist_output(user_id):

    '''
    get user id (primary key)
    look up user in Follow table, return all tv_series_ids they follow
    look up names of tv_series_id
    return string with list of TV shows
    '''

    session = create_db_session()

    logger.info("Looking for user in database")

    user = session.query(User). \
        filter_by(slack_id=user_id). \
        first()

    if not user:
        return ("You're not following any TV shows yet. Please use the `follow` command "
               "to follow some TV shows first")

    logger.info("Querying the user's watchlist")

    watchlist = session.query(Follow). \
        filter_by(user_id=user.id). \
        filter_by(is_following=True). \
        all()

    if len(watchlist) == 0:
        return ("You're not following any TV shows yet. Please use the `follow` command "
               "to follow some TV shows first")

    output_string = "*TV shows on your watchlist:* \n"

    for followed_series in watchlist:

        series = session.query(TV_Series). \
            filter_by(id=followed_series.tv_series_id). \
            first()

        output_string += series.name + "\n"

    session.close()

    payload = {
        "text": output_string
    }

    logger.info(payload)
    
    return payload


def get_episodes_for_date(date):

    episodes_airing_today_url = API_URL + '/schedule?country=US&date='

    response = requests.get(episodes_airing_today_url + date)
    episodes_for_date = response.json()

    return episodes_for_date


### CHANGE DAILY NOTIFICATIONS BACK TO DATE VARIABLE (RATHER THAN STATIC)

'''
To do:

When a new TV show is added, it should automatically create follow associations to all users (set to False by default)
When a new user is added, it should automatically create follow associations to all TV shows (set to False by default)

    This will likely involve branching each task into a separate function (i.e. segreating from the follow_series function)
    When that is done, I can slim down and deduplicate the existing if/then tree in follow_series function

* consolidate repetitive code in 'follow_series' function
* consolidate repetitive code between 'follow_series' and 'unfollow_series'

* Document different tests - maybe write a test function for the Slack Bot
* let user know when an unknown airdate becomes known
'''
