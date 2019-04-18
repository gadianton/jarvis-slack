import requests
import logging
import json
import collections
from slack import post_message
from datetime import date, datetime
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

    watchlist_data = collect_watchlist_data()
    watchlist_reports = format_watchlist_report(watchlist_data)
    send_watchlist_reports(watchlist_reports)


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

        scheduled_episodes = {}
        today = date.today()
        for series in watchlist[watchlist_categories['known']].values():
            days_until = (series['next_episode_date'] - today).days
            notification = '{} `s{}.e{}`'.format(
                series['series_name'], \
                str(series['next_episode_season']).zfill(2), \
                str(series['next_episode_number']).zfill(2)
            )
            if series['next_episode_number'] == 1:
                notification += '    :tada:'
            scheduled_episodes[notification] = days_until

        sorted_dict = sorted(scheduled_episodes.items(), key=lambda kv: kv[1])
        ordered_schedule = collections.OrderedDict(sorted_dict)

        user_report = '*TODAY*'
        episodes = [k for k,v in ordered_schedule.items() if v == 0]
        if episodes:
            for episode in episodes:
                user_report += '\n>{}'.format(episode)
        else:
            user_report += '\n_Read a book_'
        
        user_report += '\n\n*TOMMOROW*'
        episodes = [k for k,v in ordered_schedule.items() if v == 1]
        if episodes:
            for episode in episodes:
                user_report += '\n>{}'.format(episode)
        else:
            user_report += '\n_Read a book_'
        
        user_report += '\n\n*LATER*'
        for notification, days_until in ordered_schedule.items():
            if days_until > 1:
                user_report += '\n>[{}d] {}'.format(
                    days_until, notification
                )

        watchlist_reports[slack_id] = user_report

    logger.info('Finished formatting watchlist reports')

    return watchlist_reports


def send_watchlist_reports(watchlist_reports):

    for slack_id, user_report in watchlist_reports.items():
        blocks = [
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "Daily watchlist report"
                    }
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": user_report
                }
            }
        ]
        post_message(blocks, slack_id=slack_id)


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

# Create unfollow links in watchlist reports
# Area for testing: categorization of shows for the report.
    # It's possible some shows without a next episode or "Running" status might not be cancelled (TBD)