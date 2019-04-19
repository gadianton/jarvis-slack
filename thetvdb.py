import json
import requests
import os
import logging
from random import choice

# setup logging
logger = logging.getLogger('main.thetvdb')

# global variables
headers = {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
}
api_url = 'https://api.thetvdb.com'

# authenticate with TheTVDB
login_endpoint = api_url + '/login'
apikey = os.environ['TVDB_APIKEY']
payload = json.dumps({
    'apikey': apikey
})

response = requests.post(login_endpoint, data=payload, headers=headers)
tvdb_token = response.json().get('token')
headers['Authorization'] = 'Bearer {}'.format(tvdb_token)


def get_series_banner(series_id):

    logger.info('Finding series banner.')
    endpoint = '{}/series/{}/images/query'.format(api_url, series_id)
    params = {
        'keyType': 'series'
    }

    logger.info("Sending request to TheTVDB")
    response = requests.get(endpoint, params=params, headers=headers)
    banners = response.json().get('data')
    logger.info("Received banner data from TheTVDB")
    logger.debug("Banner data received:\n{}".format(banners))

    if banners:
        image_base_url = "https://www.thetvdb.com/banners/"
        image_url = find_best_image(banners, image_base_url)
    else:
        logger.warn("No banner images found on TVDB for series ID '{}'")
        image_url = None

    return image_url


def find_best_image(images, image_base_url):

    logger.info('Selecting the best image in the list')

    highest_rating = {
    'image_url': '',
    'rating': 0,
    'review_count': 0
    }
    for image in images:
        banner_rating = image['ratingsInfo']['average']
        banner_review_count = image['ratingsInfo']['count']

        if banner_rating and banner_rating > highest_rating['rating']:
            highest_rating = {
                'image_url': image_base_url + image['fileName'],
                'rating': banner_rating,
                'review_count': banner_review_count
            }
        elif banner_rating and banner_rating == highest_rating['rating'] and banner_review_count > highest_rating['review_count']:
            highest_rating = {
                'image_url': image_base_url + image['fileName'],
                'rating': banner_rating,
                'review_count': banner_review_count
            }

    if not highest_rating['rating']:
        random_image = choice(images)
        image_url = image_base_url + random_image['fileName']
    else:
        image_url = highest_rating['image_url']

    logger.info('Found best-reviewed image')
    logger.debug('Series image info:\n{}'.format(highest_rating))

    return image_url


def get_series_network(series_id):

    logger.info("Getting series network from TVDB")
    endpoint = '{}/series/{}'.format(api_url, series_id)

    try:
        response = requests.get(endpoint, headers=headers)
    except AttributeError:
        series_id 
        network = get_series_network(imdb_id)
        return network

    network = response.json().get('data').get('network')
    logger.info("Series network from TVDB: '{}'".format(network))


def find_series_id_via_imdb(imdb_id):

    endpoint = "{}/search/series".format(api_url)
    params = {
        "imdbId": imdb_id
    }

    response = requests.get(endpoint, headers=headers, params=params)
    series_id = response.json().get("data")[0].get("id")

    return series_id


def validate_series_id(series_id):
    # Sometimes the series_id provided by TVmaze is not accurate.
    # This function tests the series_id
    # If this returns false, use find_series_id_via_imdb() to get a correct series_id

    logger.info("Testing series_id '{}' from TVmaze".format(series_id))
    endpoint = "{}/series/{}".format(api_url, series_id)

    response = requests.get(endpoint, headers=headers)
    
    if response.json().get("data"):
        logger.info("series_id '{}' is valid".format(series_id))
        return True
    else:
        logger.warn("series_id '{}' is invalid".format(series_id))
        return False