import requests, time, re, os#, jarvis_bot
# from urllib import parse
from datetime import datetime, date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db_schema import Base, User, TV_Series, Follow

# Constants
API_URL = 'http://api.tvmaze.com'

# Database connection settings
engine = create_engine('sqlite:///tvmaze.db')

# connection_string = "mysql://root:" + os.environ['JARVIS_DB_PW'] + "@127.0.0.1:3306/jarvis"
# connection_string = "mysql://root:" + os.environ['JARVIS_DB_PW'] + "@127.0.0.1:3306/jarvis_test"
# engine = create_engine(connection_string)

Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)


def search_for_series(text):
    # series_search_url = API_URL + '/search/shows?q=' + parse.quote_plus(text)
    series_search_url = API_URL + '/search/shows?q=' + text
    payload = {
        'options': []
    }

    print ('Starting dynamic search for \'' + text + '\'')

    search_results = requests.get(series_search_url)
    status_code = search_results.status_code

    if status_code == 429:
        return ("The servers are busy. Try again in a few seconds.")

    series_list = search_results.json()
    
    # if series_list.count >= 3:
    #     for_loop_count = 3:
    # else:
    #     for_loop_count = series_list.count

    print ('Filtering out weak matches...')
    
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
                'text': series_output,
                'value': series_id
            }
            payload.get('options').append(option)

    print ('Lookahead payload is completely generated.')

    return payload

def get_series_data_via_id(series_id):
    series_lookup_url = API_URL + '/shows/' + str(series_id)

    series_data = requests.get(series_lookup_url)
    status_code = series_data.status_code

    if status_code == 429:
        return ("The servers are busy. Try again in a few seconds.")

    return series_data.json()


# TVmaze uses a scoring system to determine the best TV series match for a user's search.
# This search will return a dictionary object with information about the matched series.
def get_series_data(series_name):
    #series_search_url = API_URL + '/singlesearch/shows?q=' + parse.quote_plus(series_name)
    series_search_url = API_URL + '/singlesearch/shows?q=' + series_name

    print(str(datetime.now()) + "  Beginning a new search for '" + series_name + "'")

    series_data = requests.get(series_search_url)
    status_code = series_data.status_code

    if status_code == 404:
        return ("I was unable to find '" + series_name + "'.")
    elif status_code == 429:
        return ("The servers are busy. Try again in a few seconds.")

    return series_data.json()


def get_episode_data (episode_url):

    print(str(datetime.now()) + "  Requesting episode found at " + \
          episode_url)

    episode_data = requests.get(episode_url)

    return episode_data.json()


def follow_series(series_name, user_id, user_name):
    series_data = get_series_data(series_name)
    series_id = series_data.get('id')

    # Pass along message to user if response isn't a dictionary (i.e. doesn't contain data)
    # This is usually the result of a 404 status code when searching for a TV series match
    if type(series_data) != dict:
        return series_data

    session = DBSession()

    print(str(datetime.now()) + "  Checking to see if TV Series and User already exist "
                                "in the database...")
    tv_series = session.query(TV_Series). \
        filter_by(tvmaze_id=series_id). \
        first()
    user = session.query(User). \
        filter_by(slack_id=user_id). \
        first()

    if not tv_series:
        print(str(datetime.now()) + " TV Series '" + series_name + "' with "
            "ID '" + str(series_id) + "' did not exist in database. Creating"
            " an entry now.")
        tv_series = TV_Series(
            tvmaze_id=series_id,
            name=series_name,
            api_url=series_data['_links'].get('self')['href'],
            web_url=series_data.get('url')
        )
        session.add(tv_series)

    if not user:
        print(str(datetime.now()) + " User '" + str(user_id) + "' did not exist in database. Creating an entry now.")
        user = User(
            slack_id=user_id,
            slack_name=user_name)
        session.add(user)

    follow_status = session.query(Follow). \
        filter_by(tv_series_id=tv_series.id). \
        filter_by(user_id=user.id). \
        first()

    if not follow_status:
        print(str(datetime.now()) + " User '" + str(user.slack_id) + "' and TV Series '" + \
              tv_series.name + "' did not have a joint table entry. Creating an entry now.")
        follow_status = Follow(
            tv_series_id=tv_series.id,
            user_id=user.id,
            is_following=True)
        session.add(follow_status)
        output_text = "You are now following " + tv_series.name + " and " + \
                      "will receive notification before a new episode airs."

    elif follow_status.is_following:
        output_text = "You are already following " + tv_series.name + "."

    else:
        session.query(Follow). \
            filter_by(tv_series_id=follow_status.tv_series_id). \
            filter_by(user_id=follow_status.user_id). \
            update({'is_following': True})
        output_text = "You are now following " + tv_series.name + " and " + \
                      "will receive notification before a new episode airs."

    session.commit()
    session.close()

    return output_text


def unfollow_series(series_name, user_id, user_name):

    """
    * lookup TV series (get ID)
    * match ID against tvmaze_id in database
    * query the relationship between tv_series_id and user_id
    * if is_following is already false, tell user
    * otherwise, set is_following to false and notify user
    """

    series_data = get_series_data(series_name)
    series_id = series_data.get('id')

    session = DBSession()

    tv_series = session.query(TV_Series). \
        filter_by(tvmaze_id=series_id). \
        first()

    if not tv_series:
        session.close()
        output_text = "Congratulations! You're already *not* following " + series_name + "."
        return output_text

    user = session.query(User). \
        filter_by(slack_id=user_id). \
        first()

    follow_status = session.query(Follow). \
        filter_by(tv_series_id=tv_series.id). \
        filter_by(user_id=user.id). \
        first()

    if not follow_status or follow_status.is_following == False:
        response_string = "Congratulations! You're already *not* following " + \
                          tv_series.name + "."
        session.close()
        return response_string
    else:
        session.query(Follow). \
            filter_by(tv_series_id=follow_status.tv_series_id). \
            filter_by(user_id=follow_status.user_id). \
            update({'is_following': False})

    response_string = "You will no longer receive notifications for " + \
                       tv_series.name + " and are entitled to all the benefits " + \
                      "(or lack) thereof."

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

    session = DBSession()

    print ("Looking for user in database")

    user = session.query(User). \
        filter_by(slack_id=user_id). \
        first()

    if not user:
        return ("You're not following any TV shows yet. Please use the `follow` command "
               "to follow some TV shows first")

    print ("Querying the user's watchlist")

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

    print (payload)
    
    return payload


def execute_daily_tasks():

    daily_watchlist_notifications()
    database_cleanup()


def daily_watchlist_notifications():

    print(str(datetime.now()) + "  Beginning notifications function.")

    episodes_airing_today_url = API_URL + '/schedule?country=US&date='
    date_today = date.today().strftime('%Y-%m-%d')

    episodes_airing = request(episodes_airing_today_url + date_today)

    session = DBSession()

    all_series = session.query(TV_Series).all()
    messages = {}

    print(str(datetime.now()) + "  Searching through database for episodes airing today.")

    for series in all_series:
        for episode in episodes_airing:
            if series.tvmaze_id == episode['show']['id']:
                followers_list = session.query(Follow). \
                    filter_by(tv_series_id=series.id). \
                    filter_by(is_following=True). \
                    all()

                print(str(datetime.now()) + "  " + str(len(followers_list)) + " person(s) are following " +
                      episode.get('show').get('name'))

                for follower in followers_list:
                    follower = session.query(User). \
                        filter_by(id=follower.user_id). \
                        first()

                    new_message = " - `" + episode['show']['name'] + \
                        "` (season " + str(episode['season']) + \
                        " episode " + str(episode['number']) + ")\n"

                    if messages.get(follower.slack_id):
                        messages[follower.slack_id] += new_message

                    else:
                        messages[follower.slack_id] = \
                            "*TV Shows from your watchlist airing today (" + \
                            date_today + "):* \n\n" + new_message

    for user, message in messages.items():
        print(user + "\n" + message + "\n")

    slack_bot.notifications(messages)
    session.close()


def database_cleanup():

    '''
    find tv series and users no longer used
    for each tv series in database...
    query follow table for tv series where no "is_following" fields are True
    '''

    print(str(datetime.now()) + "  Starting database cleanup.")

    session = DBSession()

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

    print(str(datetime.now()) + "  Database cleanup complete.")


if __name__ == "__main__":

    execute_daily_tasks()


'''
To do:

When a new TV show is added, it should automatically create follow associations to all users (set to False by default)
When a new user is added, it should automatically create follow associations to all TV shows (set to False by default)

    This will likely involve branching each task into a separate function (i.e. segreating from the follow_series function)
    When that is done, I can slim down and deduplicate the existing if/then tree in follow_series function



* add to github
* apps vs. bots research

* command list - @jarvis help
* consolidate repetitive code in 'follow_series' function
* consolidate repetitive code between 'follow_series' and 'unfollow_series'
* create notifications function and add to slack_loop or schedule

* Document different tests - maybe write a test function for the Slack Bot
* Limit modules to certain channels
* research other TVmaze API features
* add logging
* let user know when an unknown airdate becomes known
* add special suffixes to dates of episodes depending how far out they are


'''
