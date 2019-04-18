import json
import requests
import os
import logging
from random import choice

# setup logging
logger = logging.getLogger('main.thetvdb')

headers = {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
}

api_url = 'https://api.thetvdb.com'


def create_tvdb_session():

    logger.info("Authenticating with TheTVDB")
    login_endpoint = api_url + '/login'

    apikey = os.environ['TVDB_APIKEY']
    payload = json.dumps({
        'apikey': apikey
    })

    response = requests.post(login_endpoint, data=payload, headers=headers)
    tvdb_token = response.json().get('token')
    logger.info("Finished authenticating with TheTVDB")

    return tvdb_token


def get_series_banner(series_id):

    logger.info('Finding series banner.')

    tvdb_token = create_tvdb_session()
    endpoint = '{}/series/{}/images/query'.format(api_url, series_id)
    image_base_url = "https://www.thetvdb.com/banners/"
    params = {
        'keyType': 'series'
    }
    headers['Authorization'] = 'Bearer {}'.format(tvdb_token)

    logger.info("Sending request to TheTVDB")
    response = requests.get(endpoint, params=params, headers=headers)
    banners = response.json().get('data')
    logger.info("Received banner data from TheTVDB.")

    highest_rating = {
        'image_url': '',
        'rating': 0,
        'review_count': 0
    }
    for banner_data in banners:
        banner_rating = banner_data['ratingsInfo']['average']
        banner_review_count = banner_data['ratingsInfo']['count']

        if banner_rating and banner_rating > highest_rating['rating']:
            highest_rating = {
                'image_url': image_base_url + banner_data['fileName'],
                'rating': banner_rating,
                'review_count': banner_review_count
            }
        elif banner_rating and banner_rating == highest_rating['rating'] and banner_review_count > highest_rating['review_count']:
            highest_rating = {
                'image_url': image_base_url + banner_data['fileName'],
                'rating': banner_rating,
                'review_count': banner_review_count
            }

    if not highest_rating['rating']:
        random_banner = choice(banners)
        image_url = image_base_url + random_banner['fileName']
    else:
        image_url = highest_rating['image_url']

    logger.info('Found best-reviewed series banner.')
    logger.debug('Series banner info:\n{}'.format(highest_rating))

    return image_url


def get_series_network(series_id):

    tvdb_token = create_tvdb_session()
    endpoint = '{}/series/{}'.format(api_url, series_id)
    headers['Authorization'] = 'Bearer {}'.format(tvdb_token)

    response = requests.get(endpoint, headers=headers)
    network = response.json().get('data').get('network')

    return network