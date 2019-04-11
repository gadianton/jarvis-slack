import requests
import logging
import json
import collections
from slackclient import SlackClient
from datetime import date, datetime
# from jarvis_app import authenticate_slack
from tvmaze import get_episodes_for_date, create_db_session
from db_schema import Base, User, TV_Series, Follow

# static variables
watchlist_categories = {
    'known': 'known_next_episode',
    'unknown': 'unknown_next_episode',
    'cancelled': 'cancelled'
}

def database_update():

    logger.info('Starting database update')

    session = create_db_session()

    all_series = session.query(TV_Series).all()
    for series in all_series:
        series_data = requests.get(series.api_url).json()
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

        series.status = series_data.get('status')
        series.next_episode_season = next_episode_season
        series.next_episode_number = next_episode_number
        series.next_episode_name = next_episode_name
        series.next_episode_date = next_episode_date
        series.next_episode_api_url = series.next_episode_api_url

        session.commit()

    session.close()

    logger.info('Finished database update')

    return

def create_watchlist_report():

    # Format into report
        # HIGHLIGHT premiers
        # include unfollow links/buttons (goes to URL that manages those)

    watchlist_data = collect_watchlist_data()
    watchlist_reports = format_watchlist_report(watchlist_data)
    send_watchlist_reports(watchlist_reports)

    # for series in all_series:
    #     for episode in episodes_for_date:
    #         if series.tvmaze_id == episode['show']['id']:
    #             followers_list = session.query(Follow). \
    #                 filter_by(tv_series_id=series.id). \
    #                 filter_by(is_following=True). \
    #                 all()

    #             follower_count = str(len(followers_list))
    #             series_name = episode.get('show').get('name')
    #             logger.info('<%s> person(s) are following <%s>.', follower_count, series_name)

    #             notification_message = " - `" + episode['show']['name'] + \
    #                           "` (season " + str(episode['season']) + \
    #                           " episode " + str(episode['number']) + ")\n"

    #             for follower in followers_list:
    #                 follower = session.query(User). \
    #                     filter_by(id=follower.user_id). \
    #                     first()

    #                 if messages.get(follower.slack_id):
    #                     messages[follower.slack_id] += notification_message

    #                 else:
    #                     messages[follower.slack_id] = \
    #                         "*TV Shows from your watchlist airing today (" + \
    #                         date + "):* \n\n" + notification_message

    # for user, message in messages.items():
    #     logger.info(user + "\n" + message + "\n")



def collect_watchlist_data():

    logger.info('Collecting watchlist data')
    watchlist_data = {}
    session = create_db_session()

    all_series = session.query(TV_Series).all()

    for series in all_series:
        if series.next_episode_date:
            watchlist_category = watchlist_categories['known']
        else:
            if series.status == 'Running':
                watchlist_category = watchlist_categories['unknown']
            else:
                watchlist_category = watchlist_categories['cancelled']
            
        followers = session.query(Follow.user_id).filter_by(tv_series_id=series.id, is_following=True).all()
        followers = [f[0] for f in followers]  # list comprehension to create list variable
        for follower in followers:
            slack_id = session.query(User.slack_id).filter_by(id=follower).scalar()
            if not watchlist_data.get(slack_id):
                watchlist_data[slack_id] = {
                    watchlist_categories['known']: {},
                    watchlist_categories['unknown']: {},
                    watchlist_categories['cancelled']: {}
                }

            watchlist_data[slack_id][watchlist_category][series.name] = {
                'series_name': series.name,
                'series_status': series.status,
                'next_episode_date': series.next_episode_date,
                'next_episode_season': series.next_episode_season,
                'next_episode_number': series.next_episode_number
            }

    session.close()
    logger.info('Finished watchlist data collection')
    
    return watchlist_data


def format_watchlist_report(watchlist_data):

    logger.info('Formatting watchlist reports')

    watchlist_reports = {}
    for slack_id, watchlist in watchlist_data.items():
        user_report = '*Scheduled Next Episodes*'
        
        scheduled_episodes = {}
        today = date.today()
        for series in watchlist[watchlist_categories['known']].values():
            days_until = (series['next_episode_date'] - today).days
            notification = '\n`{}` S{} E{} in {} days ({})'.format(
                series['series_name'], series['next_episode_season'], \
                series['next_episode_number'], days_until, \
                str(series['next_episode_date'])
            )
            if series['next_episode_number'] == 1:
                notification += ' *SEASON PREMIER*'
            scheduled_episodes[notification] = days_until
            
        ### REDUCE REPITITION IN FOLLOWING LINES
        sorted_dict = sorted(scheduled_episodes.items(), key=lambda kv: kv[1])
        ordered_schedule = collections.OrderedDict(sorted_dict)
        for notification in ordered_schedule.keys():
            user_report += notification

        user_report += '\n\n*Unscheduled Next Episodes*'
        for series in watchlist[watchlist_categories['unknown']].values():
            notification = '\n`{}`'.format(series['series_name'])
            user_report += notification

        user_report += '\n\n*Cancelled Shows*'
        for series in watchlist[watchlist_categories['cancelled']].values():
            notification = '\n`{}`'.format(series['series_name'])
            user_report += notification

        watchlist_reports[slack_id] = user_report

    logger.info('Finished formatting watchlist reports')
        
    return watchlist_reports
            

def send_watchlist_reports(watchlist_reports):

    logger.info('Sending watchlist reports')

    slack_client = authenticate_slack('bot_token')

    for slack_id, message in watchlist_reports.items():
        response = slack_client.api_call('im.open', user=slack_id)
        if response.get('ok'):
            channel_id = response.get('channel').get('id')
            slack_client.api_call('chat.postMessage', channel=channel_id, text=message, as_user=True)
        else:
            logger.error("Unable to send notification message to <%s>. Response error: <%s>", slack_id, response.get('error'))

    logger.info('Finished sending watchlist reports')


def database_cleanup():

    '''
    find tv series and users no longer used
    for each tv series in database...
    query follow table for tv series where no "is_following" fields are True
    '''

    logger.info("Starting database cleanup.")

    session = create_db_session()

    series_list = session.query(TV_Series).all()

    for series in series_list:
        series_followers = session.query(Follow). \
            filter_by(tv_series_id=series.id). \
            filter_by(is_following=True). \
            all()
        if len(series_followers) == 0:
            print(series.name + " has 0 followers. Marking for removal from database.")
            session.query(Follow). \
                filter_by(tv_series_id=series.id). \
                delete()
            session.query(TV_Series). \
                filter_by(id=series.id). \
                delete()

    session.commit()
    session.close()

    logger.info("Finished database cleanup")


def authenticate_slack(token_type):
    # token_type is either "bot_token" or "app_token", depending on needed permissions

    config_file = 'config.json'
    config_data = import_json(config_file)
    token = config_data[token_type]
    slack_client = SlackClient(token)

    test_response = slack_client.api_call('api.test')
    if not test_response.get('ok'):
        logger.error('API connection failed. Response error: <%s>', test_response.get('error'))
        exit()

    return slack_client


def import_json(file_path):

    with open(file_path, 'r') as file:
        data = json.loads(file.read())

    return data





if __name__ == "__main__":

    # setup logging
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    fh = logging.FileHandler('daily_tasks.log')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)

    ch = logging.StreamHandler()
    ch.setLevel(logging.WARNING)
    ch.setFormatter(formatter)

    logger = logging.getLogger('main')
    logger.setLevel(logging.DEBUG)
    logger.addHandler(fh)
    logger.addHandler(ch)

    # begin tasks
    database_cleanup()
    database_update()
    create_watchlist_report()



# To do:

# Limit modules to certain channels (e.g. Good-TV)
# Area for testing: categorization of shows for the report.
    # It's possible some shows without a next episode or "Running" status might not be cancelled (TBD)