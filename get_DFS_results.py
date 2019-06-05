"""Use contest ID to update Google Sheet with DFS results."""
import argparse
import csv
import datetime
import io
import json
import logging
import pickle
import requests
# from unidecode import unidecode
import time
import unicodedata
import zipfile

from os import path

# from http.cookiejar import CookieJar
# from pprint import pprint
# from bs4 import BeautifulSoup
import browsercookie

from selenium import webdriver

from googleapiclient.discovery import build
from httplib2 import Http
from oauth2client import file, client, tools


logger = logging.getLogger(__name__)


class EST5EDT(datetime.tzinfo):
    """Create pz timezone for EST/EDT."""

    def utcoffset(self, dt):
        """Set UTC offset."""
        return datetime.timedelta(hours=-5) + self.dst(dt)

    def dst(self, dt):
        """Determine if DST is necessary depending on dates."""
        d = datetime.datetime(dt.year, 3, 8)  # 2nd Sunday in March
        self.dston = d + datetime.timedelta(days=6-d.weekday())
        d = datetime.datetime(dt.year, 11, 1)  # 1st Sunday in Nov
        self.dstoff = d + datetime.timedelta(days=6-d.weekday())
        if self.dston <= dt.replace(tzinfo=None) < self.dstoff:
            return datetime.timedelta(hours=1)
        else:
            return datetime.timedelta(0)

    def tzname(self, dt):
        """Return name of timezone."""
        return 'EST5EDT'


def strip_accents(s):
    """Strip accents from a given string and replace with letters without accents."""
    return ''.join(c for c in unicodedata.normalize('NFD', s)
                   if unicodedata.category(c) != 'Mn')


# def pull_soup_data(filename, ENDPOINT):
#     """Either pull file from html or from file."""
#     soup = None
#     if not path.isfile(filename):
#         print("{} does not exist. Pulling from endpoint [{}]".format(filename, ENDPOINT))
#
#         # set cookies based on Chrome session
#         # cookies = browsercookie.chrome()
#         with open('cookies.json') as f:
#             cookies = json.loads(f)
#
#         pprint(cookies)
#
#         # send GET request
#         r = requests.get(ENDPOINT, cookies=cookies)
#         status = r.status_code
#
#         # if not successful, raise an exception
#         if status != 200:
#             raise Exception('Requests status != 200. It is: {0}'.format(status))
#
#         # dump html to file to avoid multiple requests
#         with open(filename, 'w') as outfile:
#             print(r.text, file=outfile)
#
#         soup = BeautifulSoup(r.text, 'html5lib')
#     else:
#         print("File exists [{}]. Nice!".format(filename))
#         # load html from file
#         with open(filename, 'r') as html_file:
#             soup = BeautifulSoup(html_file, 'html5lib')
#
#     return soup


def pull_salary_csv(filename, csv_url):
    """Pull CSV for salary information."""
    with requests.Session() as s:
        download = s.get(csv_url)

        decoded_content = download.content.decode('utf-8')

        cr = csv.reader(decoded_content.splitlines(), delimiter=',')
        my_list = list(cr)

        return my_list


def cj_from_cookies_json(working_cookies):
    filename = 'cookies.json'

    # create empty cookie jar
    cj = requests.cookies.RequestsCookieJar()

    now = datetime.datetime.now()
    with open(filename) as f:
        cookies = json.load(f)
        for c in cookies:
            if c['name'] in working_cookies:
                # logger.info("found {} in working_cookies".format(c['name']))

                # some (one?) cookies do not have an expirationDate
                if 'expirationDate' not in c:
                    logger.debug('{} has no expirationDate'.format(c['name']))
                    c['expirationDate'] = None

                # create cookie object
                r_cookie = requests.cookies.create_cookie(
                    name=c['name'],
                    value=c['value'],
                    domain=c['domain'],
                    path=c['path'],
                    expires=c['expirationDate']
                )

                # logger.debug("name: {} expires: {}".format(
                #     r_cookie.name, r_cookie.expires))

                try:
                    if r_cookie.expires:
                        cookie_expiration = datetime.datetime.fromtimestamp(
                            r_cookie.expires)
                        diff = cookie_expiration - now
                        if diff.total_seconds() >= 0:
                            logger.info("c.name {} expires soon. difference: {} (c.expires: {} now: {})".format(
                                r_cookie.name, diff, cookie_expiration, now))
                        else:
                            logger.info("c.name {} EXPIRED {} ago (c.expires: {} now: {})".format(
                                r_cookie.name, now - cookie_expiration, cookie_expiration, now))
                # some cookies have unnecessarily long expiration times which produce overflow errors
                except OverflowError as e:
                    logger.debug("Overflow on {} [{}]".format(r_cookie.name, e))

                # add cookie to cookiejar
                cj.set_cookie(r_cookie)

    return cj


def cj_from_pickle(filename):
    try:
        with open(filename, 'rb') as f:
            return pickle.load(f)
    except FileNotFoundError as e:
        logger.error("File {} not found [{}]".format(filename, e))
        return False


def setup_session(contest_csv_url, cookies):
    s = requests.Session()
    now = datetime.datetime.now()

    for c in cookies:
        # if the cookies already exists from a legitimate fresh session, clear them out
        if c.name in s.cookies:
            logger.debug("removing {} from 'cookies' -- ".format(c.name), end='')
            cookies.clear(c.domain, c.path, c.name)
        else:
            if not c.expires:
                continue

            try:
                if c.expires <= now.timestamp():
                    logger.debug("c.name {} has EXPIRED!!! (c.expires: {} now: {})".format(
                        c.name, datetime.datetime.fromtimestamp(c.expires), now))
                else:  # check if
                    delta_hours = 5
                    d = datetime.datetime.fromtimestamp(
                        c.expires) - datetime.timedelta(hours=delta_hours)
                    # within 5 hours
                    if d <= now:
                        logger.debug("c.name {} expires within {} hours!! difference: {} (c.expires: {} now: {})".format(
                            c.name, delta_hours, datetime.datetime.fromtimestamp(c.expires) - now, datetime.datetime.fromtimestamp(c.expires), now))
            # some cookies have unnecessarily long expiration times which produce overflow errors
            except OverflowError as e:
                logger.debug("Overflow on {} {} [error: {}]".format(c.name, c.expires, e))

    # exit()
    logger.debug("adding all missing cookies to session.cookies")
    # print(cookies)
    s.cookies.update(cookies)

    return request_contest_url(s, contest_csv_url)


def request_contest_url(s, contest_csv_url):
    # attempt to GET contest_csv_url
    r = s.get(contest_csv_url)
    logger.debug(r.status_code)
    logger.debug(r.url)
    logger.debug(r.headers['Content-Type'])
    # print(r.headers)
    if 'text/html' in r.headers['Content-Type']:
        # write broken cookies
        with open('pickled_cookies_broken.txt', 'wb') as f:
            pickle.dump(s.cookies, f)

        logger.info('We cannot do anything with html!')
        return False
    # if headers say file is a CSV file
    elif r.headers['Content-Type'] == 'text/csv':

        # write working cookies
        with open('pickled_cookies_works.txt', 'wb') as f:
            pickle.dump(s.cookies, f)
        # decode bytes into string
        csvfile = r.content.decode('utf-8')
        # open reader object on csvfile
        rdr = csv.reader(csvfile.splitlines(), delimiter=',')
        # return list
        return list(rdr)
    else:
        # write working cookies
        with open('pickled_cookies_works.txt', 'wb') as f:
            pickle.dump(s.cookies, f)

        # request will be a zip file
        z = zipfile.ZipFile(io.BytesIO(r.content))
        for name in z.namelist():
            # extract file - it seems easier this way
            z.extract(name)
            with z.open(name) as csvfile:
                logger.debug("name within zipfile: {}".format(name))
                # convert to TextIOWrapper object
                lines = io.TextIOWrapper(csvfile, encoding='utf-8', newline='\r\n')
                # open reader object on csvfile within zip file
                rdr = csv.reader(lines, delimiter=',')
                return list(rdr)


def text_cookie_issue():
    # create/check file for date
    filename = 'last_text_time.txt'
    now = datetime.datetime.now()

    if path.isfile(filename):
        with open(filename, 'r+') as f:
            last_time = f.read()
            last_time_dt = datetime.datetime.strptime(last_time, '%Y-%m-%d %H:%M:%S.%f')
            logger.debug("Last text time: {}".format(last_time_dt))

            # if it has been less than an hour, don't text
            if now - last_time_dt < datetime.timedelta(minutes=30):
                logger.debug("It has only been: {} ".format(now - last_time_dt))
            else:
                logger.debug("it has been more than the cutoff! {} ".format(
                    now - last_time_dt))
                logger.debug("texting adam!")
    else:
        with open(filename, 'w+') as f:
            logger.debug("Writing now(): {}".format(now))
            f.write("{}".format(now))


def pull_contest_zip(filename, contest_id):
    """Pull contest file (so far can be .zip or .csv file)."""
    contest_csv_url = "https://www.draftkings.com/contest/exportfullstandingscsv/{0}".format(
        contest_id)

    # cookies = browsercookie.chrome()
    # for c in cookies:
    #     if 'draft' not in c.domain:
    #         print("Clearing {} {} {} ".format(c.domain, c.path, c.name))
    #         cookies.clear(c.domain, c.path, c.name)
    #
    # # retrieve exported contest csv
    # s = requests.Session()
    # r = s.get(contest_csv_url, cookies=cookies)

    # try pickle cookies method
    cookies = cj_from_pickle('pickled_cookies_works.txt')
    if cookies:
        result = setup_session(contest_csv_url, cookies)

        logger.debug("type(result): {}".format(type(result)))
        if result is False:
            logger.debug("Broken from pickle method")
        else:
            logger.debug("pickle method worked!!")
            return result

    # try browsercookie method
    cookies = browsercookie.chrome()

    for c in cookies:
        if 'draft' not in c.domain:
            logger.debug("Clearing {} {} {} ".format(c.domain, c.path, c.name))
            cookies.clear(c.domain, c.path, c.name)
        else:
            if c.expires:
                # chrome is ridiculous - this math is required
                # Devide the actual timestamp (in my case it's expires_utc column in cookies table) by 1000000 // And someone should explain my why.
                # Subtract 11644473600
                # DONE! Now you got UNIX timestamp
                new_expiry = c.expires / 1000000
                new_expiry -= 11644473600
                c.expires = new_expiry

    result = setup_session(contest_csv_url, cookies)
    logger.debug("type(result): {}".format(type(result)))

    if result is False:
        logger.debug("Broken from browsercookie method")
    else:
        logger.debug("browsercookie method worked!!")
        return result

    # use selenium to refresh cookies
    use_selenium(contest_csv_url)

    # try browsercookie method again
    cookies = browsercookie.chrome()

    for c in cookies:
        if 'draft' not in c.domain:
            logger.debug("Clearing {} {} {} ".format(c.domain, c.path, c.name))
            cookies.clear(c.domain, c.path, c.name)
        else:
            if c.expires:
                # chrome is ridiculous - this math is required
                # Devide the actual timestamp (in my case it's expires_utc column in cookies table) by 1000000 // And someone should explain my why.
                # Subtract 11644473600
                # DONE! Now you got UNIX timestamp
                new_expiry = c.expires / 1000000
                new_expiry -= 11644473600
                c.expires = new_expiry

    result = setup_session(contest_csv_url, cookies)
    logger.debug("type(result): {}".format(type(result)))

    if result is False:
        logger.debug("Broken from SECOND browsercookie method")
    else:
        logger.debug("SECOND browsercookie method worked!!")
        return result
    #

    # trying load pickle cookie method
    # s.get('https://www.draftkings.com/')

    # with open('cookies.json') as f:
    #     cookies = json.load(f)
    #     for c in cookies:
    #         if c['name'] in s.cookies:
    #             print("removing {} from 'cookies' -- ".format(c.name), end='')
    #             cookies.clear(c.domain, c.path, c.name)

    #         else:
    #             print("did not find {} in s.cookies".format(c['name']))
    #             cookie = requests.cookies.create_cookie(
    #                 name=c['name'], value=c['value'], domain=c['domain'], path=c['path'], secure=c['secure'])
    #             s.cookies.set_cookie(cookie)


def use_selenium(contest_csv_url):
    logger.debug("Creating and adding options")
    options = webdriver.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument('--user-data-dir=/home/pi/.config/chromium')
    options.add_argument('--profile-directory=Profile 1')
    # options.headless = True
    # print("Converting options to capabilities")
    # options = options.to_capabilities()
    logger.debug("Starting driver with options")
    driver = webdriver.Chrome(executable_path='/usr/bin/chromedriver',
                              desired_capabilities=options.to_capabilities())
    # driver = webdriver.Remote(service.service_url, options)

    logger.debug("Performing get on {}".format(contest_csv_url))
    driver.get(contest_csv_url)
    logger.debug(driver.current_url)
    logger.debug("Letting DK load ...")
    time.sleep(5)  # Let DK Load!
    logger.debug(driver.current_url)
    logger.debug("Letting DK load ...")
    time.sleep(5)  # Let DK Load!
    logger.debug(driver.current_url)
    logger.debug("Quitting driver")
    driver.quit()


def add_header_format(service, spreadsheet_id, sheet_id):
    """Format header (row 0) with white text on black blackground."""
    header_range = {
        'sheetId': sheet_id,
        'startRowIndex': 0,
        'endRowIndex': 1,
        'startColumnIndex': 0,  # A
        'endColumnIndex': 7,  # F
    }
    color_black = {'red': 0.0, 'green': 0.0, 'blue': 0.0}
    color_white = {'red': 1.0, 'green': 1.0, 'blue': 1.0}
    requests = [{
        'repeatCell': {
            'range': header_range,
            'cell': {
                'userEnteredFormat': {
                    'backgroundColor': color_black,
                    'horizontalAlignment': 'CENTER',
                    'textFormat': {
                        'foregroundColor': color_white,
                        'fontFamily': 'Trebuchet MS',
                        'fontSize': 10,
                        'bold': True
                    }
                }
            },
            'fields': "userEnteredFormat(backgroundColor, textFormat, horizontalAlignment)"
        }
    }, {
        'updateSheetProperties': {
            'properties': {
                'sheetId': sheet_id,
                'gridProperties': {
                    'frozenRowCount': 1
                }
            },
            'fields': 'gridProperties.frozenRowCount'
        }
    }]
    logger.info('Applying header to sheet')
    batch_update_sheet(service, spreadsheet_id, requests)


def add_col_num_fmt(service, spreadsheet_id, sheet_id):
    """Format each specified column with explicit number format."""
    range_ownership = {
        'sheetId': sheet_id,
        'startRowIndex': 1,
        'endRowIndex': 1000,
        'startColumnIndex': 5,  # F
        'endColumnIndex': 6
    }
    range_points = {
        'sheetId': sheet_id,
        'startRowIndex': 1,
        'endRowIndex': 1000,
        'startColumnIndex': 6,  # G
        'endColumnIndex': 7
    }
    range_value = {
        'sheetId': sheet_id,
        'startRowIndex': 1,
        'endRowIndex': 1000,
        'startColumnIndex': 7,  # H
        'endColumnIndex': 8
    }
    requests = [{
        'repeatCell': {
            'range': range_ownership,
            'cell': {
                'userEnteredFormat': {
                    'numberFormat': {
                        'type': 'NUMBER',
                        'pattern': '#0.00%'
                    }
                }
            },
            'fields': 'userEnteredFormat.numberFormat'
        }
    }, {
        'repeatCell': {
            'range': range_points,
            'cell': {
                'userEnteredFormat': {
                    'numberFormat': {
                        'type': 'NUMBER',
                        'pattern': '##0.00'
                    }
                }
            },
            'fields': 'userEnteredFormat.numberFormat'
        }
    }, {
        'repeatCell': {
            'range': range_value,
            'cell': {
                'userEnteredFormat': {
                    'numberFormat': {
                        'type': 'NUMBER',
                        'pattern': '#0.00'
                    }
                }
            },
            'fields': 'userEnteredFormat.numberFormat'
        }
    }]
    logger.info('Applying column number format(s)')
    batch_update_sheet(service, spreadsheet_id, requests)


def add_cond_format_rules(service, spreadsheet_id, sheet_id):
    """Add conditional formatting rules to ownership, points, and value fields."""
    color_yellow = {'red': 1.0, 'green': 0.839, 'blue': 0.4}
    color_white = {'red': 1.0, 'green': 1.0, 'blue': 1.0}
    color_red = {'red': 0.92, 'green': 0.486, 'blue': 0.451}
    color_green = {'red': 0.341, 'green': 0.733, 'blue': 0.541}
    range_ownership = {
        'sheetId': sheet_id,
        'startRowIndex': 1,
        'endRowIndex': 1001,
        'startColumnIndex': 5,  # F
        'endColumnIndex': 6,
    }
    range_points = {
        'sheetId': sheet_id,
        'startRowIndex': 1,
        'endRowIndex': 1001,
        'startColumnIndex': 6,  # G
        'endColumnIndex': 7,
    }
    value_range = {
        'sheetId': sheet_id,
        'startRowIndex': 1,
        'endRowIndex': 1001,
        'startColumnIndex': 7,  # H
        'endColumnIndex': 8,
    }
    # white --> yellow
    rule_white_yellow = {
        'minpoint': {
            'type': 'MIN',
            'color': color_white
        },
        'maxpoint': {
            'type': 'MAX',
            'color': color_yellow
        }
    }
    rule_red_white_green = {
        'minpoint': {
            # red
            'type': 'MIN',
            'color': color_red
        },
        'midpoint': {
            # white
            'type': 'PERCENTILE',
            'value': '50',
            'color': color_white
        },
        'maxpoint': {
            # green
            'type': 'MAX',
            'color': color_green
        }
    }
    # red --> white --> green
    requests = [{
        # ownership % rule for white --> yellow
        'addConditionalFormatRule': {
            'rule': {
                'ranges': [range_ownership],
                'gradientRule': rule_white_yellow
            },
            'index': 0
        }
    }, {
        # points rule for red --> white --> green
        'addConditionalFormatRule': {
            'rule': {
                'ranges': [range_points],
                'gradientRule': rule_red_white_green
            },
            'index': 0
        }
    }, {
        'addConditionalFormatRule': {
            'rule': {
                'ranges': [value_range],
                'gradientRule': rule_red_white_green
            },
            'index': 0
        }
    }]
    logger.info("Applying conditional formatting to sheet_id {}".format(sheet_id))
    batch_update_sheet(service, spreadsheet_id, requests)


def add_last_updated(service, spreadsheet_id, title):
    """Add (or update) the time in the header."""
    range = "{}!J1:L1".format(title)
    now = datetime.datetime.now(tz=EST5EDT())
    values = [
        ['Last Updated', '', now.strftime('%Y-%m-%d %H:%M:%S')]
    ]
    body = {
        'values': values
    }
    value_input_option = 'USER_ENTERED'
    result = service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id, range=range,
        valueInputOption=value_input_option, body=body).execute()
    logger.debug('{0} cells updated.'.format(result.get('updatedCells')))


def update_sheet_title(service, spreadsheet_id, title):
    """Update spreadsheet title to reflect the correct sport."""
    requests = [{
        'updateSpreadsheetProperties': {
            'properties': {'title': title},
            'fields': 'title'
        }
    }]
    batch_update_sheet(service, spreadsheet_id, requests)


def batch_update_sheet(service, spreadsheet_id, requests):
    """Use function to run batchUpdate."""
    body = {
        'requests': requests
    }
    response = service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id, body=body).execute()
    logger.debug('{0} cells updated.'.format(len(response.get('replies'))))


def append_row(service, spreadsheet_id, range_name, values):
    """Append a set of values to a spreadsheet."""
    body = {
        'values': values
    }
    value_input_option = "USER_ENTERED"
    result = service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id, range=range_name,
        valueInputOption=value_input_option, body=body).execute()
    logger.info('{0} cells appended.'.format(result
                                             .get('updates')
                                             .get('updatedCells')))


def write_row(service, spreadsheet_id, range_name, values):
    """Write a set of values to a spreadsheet."""
    body = {
        'values': values
    }
    value_input_option = "USER_ENTERED"
    result = service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id, range=range_name,
        valueInputOption=value_input_option, body=body).execute()
    logger.debug('{0} cells updated.'.format(result.get('updatedCells')))


def find_sheet_id(service, spreadsheet_id, title):
    sheet_metadata = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    sheets = sheet_metadata.get('sheets', '')
    for sheet in sheets:
        if title in sheet['properties']['title']:
            logger.debug("Sheet ID for {} is {}".format(
                title, sheet['properties']['sheetId']))
            return sheet['properties']['sheetId']
    # title = sheets[0].get("properties", {}).get("title", "Sheet1")
    # sheet_id = sheets[0].get("properties", {}).get("sheetId", 0)
    # print(title)
    # print(sheet_id)


def get_matchup_info(game_info, team_abbv):
    # wth is this?
    # logger.debug(game_info)
    if game_info in ['In Progress', 'Final', 'Postponed', 'UNKNOWN', 'Suspended', 'Delayed']:
        return game_info

    # split game info into matchup_info
    home_team, a = game_info.split('@')
    away_team, match_time = a.split(' ', 1)
    # logger.debug("home_team: {} away_team: {} t: {}".format(
    #     home_team, away_team, match_time))
    # home_team, away_team = game_info.split(' ', 1)[0].split('@')
    if team_abbv == home_team:
        matchup_info = "vs. {}".format(away_team)
    else:
        matchup_info = "at {}".format(home_team)
    return matchup_info


def parse_lineup(sport, lineup, points, pmr, rank, player_dict):

    splt = lineup.split(' ')

    results = {
        'rank': rank,
        'pmr': pmr,
        'points': points
    }

    if sport == 'NBA':
        positions = ['PG', 'SG', 'SF', 'PF', 'C', 'G', 'F', 'UTIL']
        # list comp for indicies of positions in splt
        indices = [i for i, pos in enumerate(splt) if pos in positions]
        # list comp for ending indices in splt. for splicing, the second argument is exclusive
        end_indices = [indices[i] for i in range(1, len(indices))]
        # append size of splt as last index
        end_indices.append(len(splt))
    elif 'PGA' in sport:
        positions = ['G', 'WG']
        # list comp for indicies of positions in splt
        indices = [i for i, pos in enumerate(splt) if pos in positions]
        # list comp for ending indices in splt. for splicing, the second argument is exclusive
        end_indices = [indices[i] for i in range(1, len(indices))]
        # append size of splt as last index
        end_indices.append(len(splt))
    elif sport == 'NFL':
        positions = ['QB', 'RB', 'WR', 'TE', 'FLEX', 'DST']
        # list comp for indicies of positions in splt
        indices = [i for i, pos in enumerate(splt) if pos in positions]
        # list comp for ending indices in splt. for splicing, the second argument is exclusive
        end_indices = [indices[i] for i in range(1, len(indices))]
        # append size of splt as last index
        end_indices.append(len(splt))
    elif sport == 'CFB':
        positions = ['QB', 'RB', 'WR', 'TE', 'FLEX', 'S-FLEX']
        # list comp for indicies of positions in splt
        indices = [i for i, pos in enumerate(splt) if pos in positions]
        # list comp for ending indices in splt. for splicing, the second argument is exclusive
        end_indices = [indices[i] for i in range(1, len(indices))]
        # append size of splt as last index
        end_indices.append(len(splt))
    elif sport == 'NHL':
        positions = ['C', 'W', 'D', 'G', 'UTIL']
        # list comp for indicies of positions in splt
        indices = [i for i, pos in enumerate(splt) if pos in positions]
        # list comp for ending indices in splt. for splicing, the second argument is exclusive
        end_indices = [indices[i] for i in range(1, len(indices))]
        # append size of splt as last index
        end_indices.append(len(splt))
    elif sport == 'MLB':
        positions = ['P', 'C', '1B', '2B', '3B', 'SS', 'OF']
        # list comp for indicies of positions in splt
        indices = [i for i, pos in enumerate(splt) if pos in positions]
        # list comp for ending indices in splt. for splicing, the second argument is exclusive
        end_indices = [indices[i] for i in range(1, len(indices))]
        # append size of splt as last index
        end_indices.append(len(splt))
    elif sport == 'TEN':
        positions = ['P']
        # list comp for indicies of positions in splt
        indices = [i for i, pos in enumerate(splt) if pos in positions]
        # list comp for ending indices in splt. for splicing, the second argument is exclusive
        end_indices = [indices[i] for i in range(1, len(indices))]
        # append size of splt as last index
        end_indices.append(len(splt))

    pts = 0
    value = 0

    for i, index in enumerate(indices):
        pos = splt[index]

        s = slice(index + 1, end_indices[i])
        name = splt[s]
        if name != 'LOCKED':
            name = ' '.join(name)

            # ensure name doesn't have any weird characters
            name = strip_accents(name)

            if name in player_dict:
                pts = player_dict[name]['pts']
                value = player_dict[name]['value']
                perc = player_dict[name]['perc']
                salary = player_dict[name]['salary']
                matchup_info = player_dict[name]['matchup_info']
            else:
                pts = ''
                value = ''
                perc = ''
                salary = ''
                matchup_info = ''

        if 'LOCKED' in name:
            name = 'LOCKED 🔒'

        if sport == 'NBA':
            results[pos] = {
                'name': name,
                'pts': pts,
                'value': value,
                'perc': perc,
                'salary': salary,
                'matchup_info': matchup_info
            }
        elif sport == 'TEN':
            if pos not in results:
                results[pos] = []

            results[pos].append({
                'name': name,
                'pts': pts,
                'value': value,
                'perc': perc,
                'salary': salary,
                'matchup_info': matchup_info
            })
        elif 'PGA' in sport:
            # because PGA has all 'G' , create a list rather than a dictionary
            if pos not in results:
                results[pos] = []

            # append each golfer to the results['G'] list
            results[pos].append({
                'name': name,
                'pts': pts,
                'value': value,
                'perc': perc,
                'salary': salary
            })
        elif sport == 'NFL' or sport == 'CFB':
            # create a list for RB and WR since there are multiple
            if pos == 'RB' or pos == 'WR':
                if pos not in results:
                    results[pos] = []
                # append to RB/WR list
                results[pos].append({
                    'name': name,
                    'pts': pts,
                    'value': value,
                    'perc': perc,
                    'salary': salary
                })
            else:
                # set QB, TE, FLEX, DST, S-FLEX
                results[pos] = {
                    'name': name,
                    'pts': pts,
                    'value': value,
                    'perc': perc,
                    'salary': salary
                }
        elif sport == 'NHL':
            # create a list for C/W/D since there are multiple
            if pos == 'C' or pos == 'W' or pos == 'D':
                if pos not in results:
                    results[pos] = []
                # append to RB/WR list
                results[pos].append({
                    'name': name,
                    'pts': pts,
                    'value': value,
                    'perc': perc,
                    'salary': salary
                })
            else:
                # set G/UTIL
                results[pos] = {
                    'name': name,
                    'pts': pts,
                    'value': value,
                    'perc': perc,
                    'salary': salary
                }
        elif sport == 'MLB':
            # create a list for P/OF since there are multiple
            if pos == 'P' or pos == 'OF':
                if pos not in results:
                    results[pos] = []
                # append to P/OF list
                results[pos].append({
                    'name': name,
                    'pts': pts,
                    'value': value,
                    'perc': perc,
                    'salary': salary,
                    'matchup_info': matchup_info
                })
            else:
                # set C/1B/2B/3B/SS
                results[pos] = {
                    'name': name,
                    'pts': pts,
                    'value': value,
                    'perc': perc,
                    'salary': salary,
                    'matchup_info': matchup_info
                }

    return results


def write_NBA_lineup(lineup, bro):
    ordered_position = ['PG', 'SG', 'SF', 'PF', 'C', 'G', 'F', 'UTIL']
    values = [
        [bro, '', 'PMR', lineup['pmr'], 'rank', lineup['rank']],
        ['Position', 'Player', 'Salary', 'Pts', 'Value', 'Own']
    ]
    rem_salary = 50000
    for position in ordered_position:
        values.append([position, lineup[position]['name'],
                       lineup[position]['salary'], lineup[position]['pts'],
                       lineup[position]['value'], lineup[position]['perc']])
        if lineup[position]['matchup_info'] in ['In Progress', 'Final']:
            rem_salary -= int(lineup[position]['salary'])

    values.append(['', 'rem salary', rem_salary, lineup['points'], '', ''])
    return values


def write_PGA_lineup(lineup, bro):
    values = [
        [bro, '', 'PMR', lineup['pmr'], '', ''],
        ['Position', 'Player', 'Salary', 'Pts', 'Value', 'Own']
    ]
    if 'WG' in lineup:
        for golfer in lineup['WG']:
            values.append(['WG', golfer['name'], golfer['salary'], golfer['pts'],
                           golfer['value'], golfer['perc']])
    elif 'G' in lineup:
        for golfer in lineup['G']:
            values.append(['G', golfer['name'], golfer['salary'], golfer['pts'],
                           golfer['value'], golfer['perc']])

    values.append(['rank', lineup['rank'], '', lineup['points'], '', ''])
    return values


def write_TEN_lineup(lineup, bro):
    values = [
        [bro, '', 'PMR', lineup['pmr'], '', ''],
        ['Position', 'Player', 'Salary', 'Pts', 'Value', 'Own']
    ]
    if 'P' in lineup:
        for p in lineup['P']:
            values.append(['P', p['name'], p['salary'], p['pts'], p['value'], p['perc']])

    values.append(['rank', lineup['rank'], '', lineup['points'], '', ''])
    return values


def write_NFL_lineup(lineup, bro):
    values = [
        [bro, '', 'PMR', lineup['pmr']],
        ['Position', 'Player', 'Points', 'Value']
    ]
    # append QB
    values.append(['QB', lineup['QB']['name'], lineup['QB']
                   ['pts'], lineup['QB']['value'],
                   lineup['QB']['perc']])

    # append RBs
    for RB in lineup['RB']:
        values.append(['RB', RB['name'], RB['pts'], RB['value'], RB['perc']])

    # append WRs
    for WR in lineup['WR']:
        values.append(['WR', WR['name'], WR['pts'], WR['value'], WR['perc']])

    # append the other positions
    for pos in ['TE', 'FLEX', 'DST']:
        values.append([pos, lineup[pos]['name'],
                       lineup[pos]['pts'], lineup[pos]['value'],
                       lineup[pos]['perc']])

    values.append(['rank', lineup['rank'], lineup['points'], ''])
    return values


def write_CFB_lineup(lineup, bro):
    values = [
        [bro, '', 'PMR', lineup['pmr']],
        ['Position', 'Player', 'Points', 'Value']
    ]
    # append QB
    values.append(['QB', lineup['QB']['name'], lineup['QB']
                   ['pts'], lineup['QB']['value']])
    # append RBs
    for RB in lineup['RB']:
        values.append(['RB', RB['name'], RB['pts'], RB['value']])
    # append WRs
    for WR in lineup['WR']:
        values.append(['WR', WR['name'], WR['pts'], WR['value']])

    for pos in ['FLEX', 'S-FLEX']:
        values.append([pos, lineup[pos]['name'],
                       lineup[pos]['pts'], lineup[pos]['value']])
    # append rank and points
    values.append(['rank', lineup['rank'], lineup['points'], ''])
    return values


def write_NHL_lineup(lineup, bro):
    values = [
        [bro, '', 'PMR', lineup['pmr']],
        ['Position', 'Player', 'Points', 'Value']
    ]
    # append C
    for C in lineup['C']:
        values.append(['C', C['name'], C['pts'], C['value']])
    # append W
    for W in lineup['W']:
        values.append(['W', W['name'], W['pts'], W['value']])
    # append D
    for D in lineup['D']:
        values.append(['D', D['name'], D['pts'], D['value']])
    # append G/UTIL
    for pos in ['G', 'UTIL']:
        values.append([pos, lineup[pos]['name'],
                       lineup[pos]['pts'], lineup[pos]['value']])
    # append rank and points
    values.append(['rank', lineup['rank'], lineup['points'], ''])
    return values


def write_MLB_lineup(lineup, bro):
    values = [
        [bro, '', 'PMR', lineup['pmr'], 'rank', lineup['rank']],
        ['Position', 'Player', 'Salary', 'Pts', 'Value', 'Own']
    ]
    rem_salary = 50000
    # append P
    for P in lineup['P']:
        values.append(['P', P['name'], P['salary'], P['pts'], P['value'], P['perc']])
        if P['matchup_info'] in ['In Progress', 'Final']:
            rem_salary -= int(P['salary'])
    # append C/1B/2B/3B/SS
    for position in ['C', '1B', '2B', '3B', 'SS']:
        values.append([position, lineup[position]['name'],
                       lineup[position]['salary'], lineup[position]['pts'],
                       lineup[position]['value'], lineup[position]['perc']])
        if lineup[position]['matchup_info'] in ['In Progress', 'Final']:
            rem_salary -= int(lineup[position]['salary'])
    # append OF
    for OF in lineup['OF']:
        values.append(['OF', OF['name'], OF['salary'],
                       OF['pts'], OF['value'], OF['perc']])
        if OF['matchup_info'] in ['In Progress', 'Final']:
            rem_salary -= int(OF['salary'])

    values.append(['', 'rem salary', rem_salary, lineup['points'], '', ''])
    return values


def write_lineup(service, spreadsheet_id, sheet_id, lineup, sport):
    logger.debug("Sport == {} - trying to write_lineup()..".format(sport))
    # pre-defined google sheet lineup ranges
    # range 1 K3:N15  range 5: Q3:U15
    # range 2 K15:N25 range 6: Q15:U25
    # range 3 K27:N37 range 7: Q27:U37
    # range 4 K39:O49 range 8: Q39:U49
    ranges = [
        "{}!K3:O15".format(sport),
        "{}!K15:O25".format(sport),
        "{}!K27:O37".format(sport),
        "{}!K39:O49".format(sport),
        "{}!Q3:U15".format(sport),
        "{}!Q15:U25".format(sport),
        "{}!Q27:U37".format(sport),
        "{}!Q39:U49".format(sport)
    ]
    # NFL has an extra position, so it needs new ranges
    NFL_ranges = [
        "{}!K3:O15".format(sport),
        "{}!K16:O27".format(sport),
        "{}!K29:O40".format(sport),
        "{}!K42:O53".format(sport),
        "{}!Q3:U15".format(sport),
        "{}!Q16:U27".format(sport),
        "{}!Q29:U40".format(sport),
        "{}!Q42:U53".format(sport)
    ]

    ultimate_list = []
    lineup_mod = 4
    if sport == 'NBA':
        for i, (k, v) in enumerate(sorted(lineup.items())):
            # print("i: {} K: {}\nv:{}".format(i, k, v))
            nba_mod = 11
            values = write_NBA_lineup(v, k)
            for j, z in enumerate(values):
                if i < lineup_mod:
                    ultimate_list.append(z)
                elif i >= lineup_mod:
                    mod = (i % lineup_mod) + ((i % lineup_mod) * nba_mod) + j
                    ultimate_list[mod].extend([''] + z)
            # append an empty list for spacing
            ultimate_list.append([])
        r = "{}!J3:V54".format(sport)
        logger.debug("trying to write all lineups to [{}]".format(r))
        write_row(service, spreadsheet_id, r, ultimate_list)
    elif 'PGA' in sport:
        # for i, (k, v) in enumerate(sorted(lineup.items())):
        #     # print("i: {} K: {}\nv:{}".format(i, k, v))
        #     golf_mod = 9
        #     values = write_PGA_lineup(v, k)
        #     for j, z in enumerate(values):
        #         if i < lineup_mod:
        #             ultimate_list.append(z)
        #         elif i >= lineup_mod:
        #             # mod = (i % 4) + ((i % 4) * 10) + j
        #             mod = (i % lineup_mod) + ((i % lineup_mod) * golf_mod) + j
        #             ultimate_list[mod].extend([''] + z)
        #     # append an empty list for spacing
        #     ultimate_list.append([])
        ultimate_list = build_lineup_list(lineup, sport)
        r = "{}!J3:V54".format(sport)
        logger.debug("trying to write all lineups to [{}]".format(r))
        write_row(service, spreadsheet_id, r, ultimate_list)
    elif sport == 'TEN':
        for i, (k, v) in enumerate(sorted(lineup.items())):
            # print("i: {} K: {}\nv:{}".format(i, k, v))
            ten_mod = 9
            values = write_TEN_lineup(v, k)
            for j, z in enumerate(values):
                if i < lineup_mod:
                    ultimate_list.append(z)
                elif i >= lineup_mod:
                    mod = (i % lineup_mod) + ((i % lineup_mod) * ten_mod) + j
                    ultimate_list[mod].extend([''] + z)
            # append an empty list for spacing
            ultimate_list.append([])
        r = "{}!J3:V54".format(sport)
        logger.debug("trying to write all lineups to [{}]".format(r))
        write_row(service, spreadsheet_id, r, ultimate_list)
    elif sport == 'NFL':
        for i, (k, v) in enumerate(sorted(lineup.items())):
            # print("i: {} K: {}\nv:{}".format(i, k, v))
            values = write_NFL_lineup(v, k)
            logger.debug("trying to write line [{}] to {}".format(k, NFL_ranges[i]))
            # print(values)
            write_row(service, spreadsheet_id, NFL_ranges[i], values)
    elif sport == 'CFB':
        for i, (k, v) in enumerate(sorted(lineup.items())):
            # print("i: {} K: {}\nv:{}".format(i, k, v))
            values = write_CFB_lineup(v, k)
            logger.debug("trying to write line [{}] to {}".format(k, ranges[i]))
            # print(values)
            write_row(service, spreadsheet_id, ranges[i], values)
    elif sport == 'NHL':
        for i, (k, v) in enumerate(sorted(lineup.items())):
            # print("i: {} K: {}\nv:{}".format(i, k, v))
            values = write_NHL_lineup(v, k)
            logger.debug("trying to write line [{}] to {}".format(k, NFL_ranges[i]))
            # print(values)
            write_row(service, spreadsheet_id, NFL_ranges[i], values)
    elif sport == 'MLB':
        for i, (k, v) in enumerate(sorted(lineup.items())):
            mlb_mod = 13
            values = write_MLB_lineup(v, k)
            for j, z in enumerate(values):
                if i < lineup_mod:
                    ultimate_list.append(z)
                elif i >= lineup_mod:
                    mod = (i % lineup_mod) + ((i % lineup_mod) * mlb_mod) + j
                    ultimate_list[mod].extend([''] + z)
            # append an empty list for spacing
            ultimate_list.append([])
        r = "{}!J3:V57".format(sport)
        logger.debug("trying to write all lineups to [{}]".format(r))
        write_row(service, spreadsheet_id, r, ultimate_list)


def build_lineup_list(lineup, sport):
    logger.debug("build_lineup_list(lineup, {})".format(sport))
    ultimate_list = []
    sport_mod = 1
    lineup_mod = 4

    if 'PGA' in sport:
        sport_mod = 9
    elif 'TEN' in sport:
        sport_mod = 9

    for i, (k, v) in enumerate(sorted(lineup.items())):
        # print("i: {} K: {}\nv:{}".format(i, k, v))
        values = write_PGA_lineup(v, k)
        for j, z in enumerate(values):
            if i < lineup_mod:
                ultimate_list.append(z)
            elif i >= lineup_mod:
                # mod = (i % 4) + ((i % 4) * 10) + j
                mod = (i % lineup_mod) + ((i % lineup_mod) * sport_mod) + j
                ultimate_list[mod].extend([''] + z)
        # append an empty list for spacing
        ultimate_list.append([])

    return ultimate_list


def read_salary_csv(fn):
    with open(fn, mode='r') as f:
        cr = csv.reader(f, delimiter=',')
        slate_list = list(cr)

        salary = {}
        for row in slate_list[1:]:
            if len(row) < 2:
                continue
            name = row[2]
            if name not in salary:
                salary[name] = {}
                salary[name]['salary'] = 0
                salary[name]['team_abbv'] = ''

            salary[name]['salary'] = row[5]
            salary[name]['game_info'] = row[6]
            salary[name]['team_abbv'] = row[7]
        return salary


# TODO remove since i use strip_accents at the top
# def massage_name(name):
#     """Manually remove accents from peoples' names."""
#     # wtf is going on with these guys' names?
#     if 'Exum' in name:
#         name = 'Dante Exum'
#     if 'Guillermo Hernan' in name:
#         name = 'Guillermo Hernangomez'
#     if 'Juancho Hernan' in name:
#         name = 'Juancho Hernangomez'
#     if 'lex Abrines' in name:
#         name = 'Alex Abrines'
#     if 'Luwawu-Cabarrot' in name:
#         name = 'Timothe Luwawu-Cabarrot'
#     if ' Calder' in name:
#         name = 'Jose Calderon'
#     return name


def main():
    """Use contest ID to update Google Sheet with DFS results.

    Example export CSV/ZIP link
    https://www.draftkings.com/contest/exportfullstandingscsv/62753724

    Example salary CSV link
    https://www.draftkings.com/lineup/getavailableplayerscsv?contestTypeId=70&draftGroupId=22401
    12 = MLB 21 = NFL 9 = PGA 24 = NASCAR 10 = Soccer 13 = MMA
    """

    # text_cookie_issue()

    # parse arguments
    parser = argparse.ArgumentParser()
    choices = ['NBA', 'NFL', 'CFB', 'PGAMain',
               'PGAWeekend', 'PGAShowdown', 'NHL', 'MLB', 'TEN']
    parser.add_argument('-i', '--id', type=int, required=True,
                        help='Contest ID from DraftKings',)
    parser.add_argument('-c', '--csv', help='Slate CSV from DraftKings',)
    parser.add_argument('-s', '--sport', choices=choices,
                        required=True, help='Type of contest (NBA, NFL, PGA, CFB, NHL, or MLB)')
    parser.add_argument('-v', '--verbose', help='Increase verbosity')
    args = parser.parse_args()

    now = datetime.datetime.now()
    logger.info("Current time: {}".format(now))

    dir = '/home/pi/Desktop/dk_salary_owner'
    # set the filename for the salary CSV
    if args.csv:
        fn = args.csv
    else:
        fn = "DKSalaries_{}_{}.csv".format(args.sport, now.strftime('%A'))

    contest_id = args.id
    sport = args.sport

    logger.debug(args)

    # read salary CSV
    salary_dict = read_salary_csv(fn)

    # pull contest standings
    fn2 = "contest-standings-{}.csv".format(contest_id)
    contest_list = pull_contest_zip(fn2, contest_id)
    parsed_lineup = {}
    bros = ['aplewandowski', 'FlyntCoal', 'Cubbiesftw23',
            'Mcoleman1902', 'cglenn91', 'Notorious', 'Bra3105', 'ChipotleAddict']
    values = []

    bro_lineups = {}
    player_dict = {}
    for i, row in enumerate(contest_list[1:]):
        rank = row[0]
        name = row[2]
        pmr = row[3]
        points = row[4]
        lineup = row[5]

        # find lineup for friends
        if name in bros:
            logger.info("found bro {}".format(name))
            bro_lineups[name] = {
                'rank': rank,
                'lineup': lineup,
                'pmr': pmr,
                'points': points
            }

        stats = row[7:]
        if stats:
            # continue if empty (sometimes happens on the player columns in the standings)
            if all('' == s or s.isspace() for s in stats):
                continue

            name = strip_accents(stats[0])
            pos = stats[1]
            salary = int(salary_dict[name]['salary'])
            if 'PGA' not in sport:
                team_abbv = salary_dict[name]['team_abbv']
                game_info = salary_dict[name]['game_info']
                matchup_info = get_matchup_info(game_info, team_abbv)
            else:
                team_abbv = ''
                matchup_info = ''

            perc = float(stats[2].replace('%', '')) / 100
            pts = float(stats[3])

            # calculate value
            if pts > 0:
                value = pts / (salary / 1000)
            else:
                value = 0

            player_dict[name] = {
                'pos': pos,
                'salary': salary,
                'perc': perc,
                'pts': pts,
                'value': value,
                'matchup_info': matchup_info
            }
            # logger.debug("player_dict[{}]['matchup_info']: {}".format(
            #     name, player_dict[name]['matchup_info']))
            values.append([pos, name, team_abbv, matchup_info, salary, perc, pts, value])

    # logger.debug("player_dict:")
    # logger.debug(player_dict)
    # google sheets API boilerplate
    SCOPES = 'https://www.googleapis.com/auth/spreadsheets'
    store = file.Storage(path.join(dir, 'token.json'))
    creds = store.get()
    if not creds or creds.invalid:
        flow = client.flow_from_clientsecrets(path.join(dir, 'token.json'), SCOPES)
        creds = tools.run_flow(flow, store)
    service = build('sheets', 'v4', http=creds.authorize(Http()))

    for bro, v in bro_lineups.items():
        parsed_lineup[bro] = parse_lineup(
            sport, v['lineup'], v['points'], v['pmr'], v['rank'], player_dict)
        logger.debug("{} {}".format(bro, parsed_lineup[bro]))

    # call the Sheets API
    spreadsheet_id = '1Jv5nT-yUoEarkzY5wa7RW0_y0Dqoj8_zDrjeDs-pHL4'
    RANGE_NAME = "{}!A2:S".format(args.sport)
    sheet_id = find_sheet_id(service, spreadsheet_id, args.sport)

    logger.debug('Starting write_row')
    write_row(service, spreadsheet_id, RANGE_NAME, values)
    if parsed_lineup:
        logger.info('Writing lineup')
        write_lineup(service, spreadsheet_id, sheet_id, parsed_lineup, args.sport)
    add_col_num_fmt(service, spreadsheet_id, sheet_id)
    add_header_format(service, spreadsheet_id, sheet_id)
    # add_cond_format_rules(service, spreadsheet_id, sheet_id)
    add_last_updated(service, spreadsheet_id, args.sport)
    # update_sheet_title(service, spreadsheet_id, sheet_id, args.sport)


if __name__ == '__main__':
    logger.setLevel(logging.DEBUG)
    # formatter = logging.Formatter(fmt='%(asctime)s %(funcName)11s %(levelname)5s %(message)s',
    #                               datefmt='%Y-%m-%d %H:%M:%S')
    formatter = logging.Formatter(fmt='%(asctime)s %(funcName)20s %(levelname)5s %(message)s',
                                  datefmt='%Y-%m-%d %H:%M:%S')
    # configure and add stream handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    main()
