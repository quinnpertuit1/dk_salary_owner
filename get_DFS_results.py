"""Use contest ID to update Google Sheet with DFS results."""
import argparse
import csv
import io
import json
import re
import requests
# from unidecode import unidecode
import unicodedata
import zipfile
from os import path, sep
from dateutil import parser
# from datetime import datetime
import datetime

from bs4 import BeautifulSoup
import browsercookie

from googleapiclient.discovery import build
from httplib2 import Http
from oauth2client import file, client, tools

# If modifying these scopes, delete the file token.json.
# SCOPES = 'https://www.googleapis.com/auth/spreadsheets.readonly'


# def strip_accents(text):
# u = str(text, 'utf-8')
# convert utf-8 to normal text
# return unidecode.unidecode(u)
# try:
#     text = unicode(text, 'utf-8')
# except NameError:  # unicode is a default on python 3
#     pass
# text = unicodedata.normalize('NFD', text)
# text = text.encode('ascii', 'ignore')
# text = text.decode("utf-8")
# return str(text)
# def strip_accents(s):
#     return ''.join(c for c in unicodedata.normalize('NFD', s)
#                    if unicodedata.category(c) != 'Mn')


class EST5EDT(datetime.tzinfo):

    def utcoffset(self, dt):
        return datetime.timedelta(hours=-5) + self.dst(dt)

    def dst(self, dt):
        d = datetime.datetime(dt.year, 3, 8)  # 2nd Sunday in March
        self.dston = d + datetime.timedelta(days=6-d.weekday())
        d = datetime.datetime(dt.year, 11, 1)  # 1st Sunday in Nov
        self.dstoff = d + datetime.timedelta(days=6-d.weekday())
        if self.dston <= dt.replace(tzinfo=None) < self.dstoff:
            return datetime.timedelta(hours=1)
        else:
            return datetime.timedelta(0)

    def tzname(self, dt):
        return 'EST5EDT'


def strip_accents(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s)
                   if unicodedata.category(c) != 'Mn')


def pull_dk_contests(reload=False):
    ENDPOINT = 'https://www.draftkings.com/mycontests'
    filename = 'my_contests.html'

    # pull data
    soup = pull_soup_data(filename, ENDPOINT)

    # find script(s) in the html
    script = soup.findAll('script')

    # for i, s in enumerate(script):
    #     print("{}: {}".format(i, s))
    js_contest_data = script[133].string

    # pull json object from data variable
    # pattern = re.compile(r'data = (.*);')
    pattern = re.compile(r'upcoming: (.*),')
    json_str = pattern.search(js_contest_data).group(1)
    contest_json = json.loads(json_str)

    bool_quarters = False
    now = datetime.datetime.now()
    # iterate through json
    for contest in contest_json:
        # print(contest)
        id = contest['ContestId']
        name = contest['ContestName']
        buyin = contest['BuyInAmount']
        est_starttime = contest['ContestStartDateEdt']
        top_payout = contest['TopPayout']
        group_id = contest['DraftGroupId']
        game_type = contest['GameTypeId']

        # only print quarters contests ServiceAccountCredentials
        if buyin == 0.25:
            if bool_quarters:
                continue
            else:
                bool_quarters = True

        dt_starttime = parser.parse(est_starttime)
        time_until = dt_starttime - now

        print("ID: {} buyin: {} payout: {} est_startime: {} starts in: {} [{}]".format(
            id, buyin, top_payout, est_starttime, time_until, name))
        print("group_id: {} game_type: {}".format(group_id, game_type))
        print("https://www.draftkings.com/lineup/getavailableplayerscsv?contestTypeId={}&draftGroupId={}".format(game_type, group_id))


def pull_soup_data(filename, ENDPOINT):
    """Either pull file from html or from file."""
    soup = None
    if not path.isfile(filename):
        print("{} does not exist. Pulling from endpoint [{}]".format(filename, ENDPOINT))

        # set cookies based on Chrome session
        cookies = browsercookie.chrome()

        # send GET request
        r = requests.get(ENDPOINT, cookies=cookies)
        status = r.status_code

        # if not successful, raise an exception
        if status != 200:
            raise Exception('Requests status != 200. It is: {0}'.format(status))

        # dump html to file to avoid multiple requests
        with open(filename, 'w') as outfile:
            print(r.text, file=outfile)

        soup = BeautifulSoup(r.text, 'html5lib')
    else:
        print("File exists [{}]. Nice!".format(filename))
        # load html from file
        with open(filename, 'r') as html_file:
            soup = BeautifulSoup(html_file, 'html5lib')

    return soup


def pull_salary_csv(filename, csv_url):
    """Pull CSV for salary information."""
    with requests.Session() as s:
        download = s.get(csv_url)

        decoded_content = download.content.decode('utf-8')

        cr = csv.reader(decoded_content.splitlines(), delimiter=',')
        my_list = list(cr)

        return my_list


def pull_contest_zip(filename, contest_id):
    """Pull contest file (so far can be .zip or .csv file)."""
    contest_csv_url = "https://www.draftkings.com/contest/exportfullstandingscsv/{0}".format(
        contest_id)

    # ~/Library/Application Support/Google/Chrome/Default/Cookies

    # Uses Chrome's default cookies filepath by default
    # cookies = chrome_cookies(contest_csv_url, cookie_file='~/Library/Application Support/Google/Chrome/Default/Cookies')
    cookies = browsercookie.chrome()

    # retrieve exported contest csv
    r = requests.get(contest_csv_url, cookies=cookies)

    print(r.headers)
    # if headers say file is a CSV file
    if r.headers['Content-Type'] == 'text/csv':
        # decode bytes into string
        csvfile = r.content.decode('utf-8')
        # open reader object on csvfile
        rdr = csv.reader(csvfile.splitlines(), delimiter=',')
        # return list
        return list(rdr)
    elif 'text/html' in r.headers['Content-Type']:
        print(r.content)
        exit('We cannot do anything with html!')
    else:
        # request will be a zip file
        z = zipfile.ZipFile(io.BytesIO(r.content))

        for name in z.namelist():
            # extract file - it seems easier this way
            z.extract(name)
            with z.open(name) as csvfile:
                print("name within zipfile".format(name))
                # convert to TextIOWrapper object
                lines = io.TextIOWrapper(csvfile, encoding='utf-8', newline='\r\n')
                # open reader object on csvfile within zip file
                rdr = csv.reader(lines, delimiter=',')
                return list(rdr)


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
    print('Applying header to sheet')
    batch_update_sheet(service, spreadsheet_id, requests)


def add_column_number_format(service, spreadsheet_id, sheet_id):
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
    print('Applying column number format(s)')
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
    print("Applying conditional formatting to sheet_id {}".format(sheet_id))
    batch_update_sheet(service, spreadsheet_id, requests)


def add_last_updated(service, spreadsheet_id, title):
    """Add (or update) the time in the header."""
    range = "{}!I1:J1".format(title)
    now = datetime.datetime.now(tz=EST5EDT())
    values = [
        ['Last Updated', now.strftime('%Y-%m-%d %H:%M:%S')]
    ]
    body = {
        'values': values
    }
    value_input_option = 'USER_ENTERED'
    result = service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id, range=range,
        valueInputOption=value_input_option, body=body).execute()
    print('{0} cells updated.'.format(result.get('updatedCells')))


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
    print('{0} cells updated.'.format(len(response.get('replies'))))


def append_row(service, spreadsheet_id, range_name, values):
    """Append a set of values to a spreadsheet."""
    body = {
        'values': values
    }
    value_input_option = "USER_ENTERED"
    result = service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id, range=range_name,
        valueInputOption=value_input_option, body=body).execute()
    print('{0} cells appended.'.format(result
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
    print('{0} cells updated.'.format(result.get('updatedCells')))


def find_sheet_id(service, spreadsheet_id, title):
    sheet_metadata = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    sheets = sheet_metadata.get('sheets', '')
    for sheet in sheets:
        if title in sheet['properties']['title']:
            print("Sheet ID for {} is {}".format(title, sheet['properties']['sheetId']))
            return sheet['properties']['sheetId']
    # title = sheets[0].get("properties", {}).get("title", "Sheet1")
    # sheet_id = sheets[0].get("properties", {}).get("sheetId", 0)
    # print(title)
    # print(sheet_id)


def get_matchup_info(game_info, team_abbv):
    # wth is this?
    if game_info in ['In Progress', 'Final']:
        return game_info

    # split game info into matchup_info
    home_team, away_team = game_info.split(' ', 1)[0].split('@')
    if team_abbv == home_team:
        matchup_info = "vs. {}".format(away_team)
    else:
        matchup_info = "at {}".format(home_team)
    return matchup_info


def get_game_time_info(game_info):
    if game_info in ['In Progress', 'Final']:
        return game_info
    return game_info.split(' ', 1)[1]


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
    elif sport == 'PGA':
        position = 'G'
        # list comp for indicies of positions in splt
        indices = [i for i, pos in enumerate(splt) if pos == position]
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
            else:
                pts = None
                value = None
                perc = None

        if sport == 'NBA':
            results[pos] = {
                'name': name,
                'pts': pts,
                'value': value
            }
        elif sport == 'PGA':
            # because PGA has all 'G', create a list rather than a dictionary
            if pos not in results:
                results[pos] = []

            # append each golfer to the results['G'] list
            results[pos].append({
                'name': name,
                'pts': pts,
                'value': value
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
                    'value': value
                })
            else:
                # set QB, TE, FLEX, DST, S-FLEX
                results[pos] = {
                    'name': name,
                    'pts': pts,
                    'value': value
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
                    'value': value
                })
            else:
                # set G/UTIL
                results[pos] = {
                    'name': name,
                    'pts': pts,
                    'value': value
                }

    print(results)
    return results


def write_NBA_lineup(lineup, bro):
    ordered_position = ['PG', 'SG', 'SF', 'PF', 'C', 'G', 'F', 'UTIL']
    values = [
        [bro, '', 'PMR', lineup['pmr']],
        ['Position', 'Player', 'Points', 'Value']
    ]
    for position in ordered_position:
        values.append([position, lineup[position]['name'],
                       lineup[position]['pts'], lineup[position]['value']])

    values.append(['rank', lineup['rank'], lineup['points'], ''])
    return values


def write_PGA_lineup(lineup, bro):
    values = [
        [bro, '', 'PMR', lineup['pmr']],
        ['Position', 'Player', 'Points', 'Value']
    ]
    for golfer in lineup['G']:
        values.append(['G', golfer['name'], golfer['pts'], golfer['value']])

    values.append(['rank', lineup['rank'], lineup['points'], ''])
    return values


def write_NFL_lineup(lineup, bro):
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

    # append the other positions
    for pos in ['TE', 'FLEX', 'DST']:
        values.append([pos, lineup[pos]['name'],
                       lineup[pos]['pts'], lineup[pos]['value']])

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


def write_lineup(service, spreadsheet_id, sheet_id, lineup, sport):

    print("Sport == {} - trying to write_lineup()..".format(sport))

    # pre-defined google sheet lineup ranges
    # range 1 K3:N15  range 4: P3:S15
    # range 2 K15:N25 range 5: P15:S25
    # range 3 K27:N37 range 6: P27:S37
    ranges = [
        "{}!K3:N15".format(sport),
        "{}!K15:N25".format(sport),
        "{}!K27:N37".format(sport),
        "{}!P3:S15".format(sport),
        "{}!P15:S25".format(sport),
        "{}!P27:S37".format(sport)
    ]

    NFL_ranges = [
        "{}!K3:N15".format(sport),
        "{}!K16:N27".format(sport),
        "{}!K29:N40".format(sport),
        "{}!P3:S15".format(sport),
        "{}!P16:S27".format(sport),
        "{}!P29:S40".format(sport)
    ]

    # print(lineup)
    if sport == 'NBA':
        for i, (k, v) in enumerate(lineup.items()):
            # print("i: {} K: {}\nv:{}".format(i, k, v))
            values = write_NBA_lineup(v, k)
            print("trying to write line [{}] to {}".format(k, ranges[i]))
            write_row(service, spreadsheet_id, ranges[i], values)
    elif sport == 'PGA':
        for i, (k, v) in enumerate(lineup.items()):
            # print("i: {} K: {}\nv:{}".format(i, k, v))
            values = write_PGA_lineup(v, k)
            print("trying to write line [{}] to {}".format(k, ranges[i]))
            write_row(service, spreadsheet_id, ranges[i], values)
    elif sport == 'NFL':
        for i, (k, v) in enumerate(lineup.items()):
            # print("i: {} K: {}\nv:{}".format(i, k, v))
            values = write_NFL_lineup(v, k)
            print("trying to write line [{}] to {}".format(k, NFL_ranges[i]))
            # print(values)
            write_row(service, spreadsheet_id, NFL_ranges[i], values)
    elif sport == 'CFB':
        for i, (k, v) in enumerate(lineup.items()):
            # print("i: {} K: {}\nv:{}".format(i, k, v))
            values = write_CFB_lineup(v, k)
            print("trying to write line [{}] to {}".format(k, ranges[i]))
            # print(values)
            write_row(service, spreadsheet_id, ranges[i], values)
    elif sport == 'NHL':
        for i, (k, v) in enumerate(lineup.items()):
            # print("i: {} K: {}\nv:{}".format(i, k, v))
            values = write_NHL_lineup(v, k)
            print("trying to write line [{}] to {}".format(k, NFL_ranges[i]))
            # print(values)
            write_row(service, spreadsheet_id, NFL_ranges[i], values)


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


def massage_name(name):
    # wtf is going on with these guys' names?
    if 'Exum' in name:
        name = 'Dante Exum'
    if 'Guillermo Hernan' in name:
        name = 'Guillermo Hernangomez'
    if 'Juancho Hernan' in name:
        name = 'Juancho Hernangomez'
    if 'lex Abrines' in name:
        name = 'Alex Abrines'
    if 'Luwawu-Cabarrot' in name:
        name = 'Timothe Luwawu-Cabarrot'
    return name


def main():
    """Use contest ID to update Google Sheet with DFS results."""

    # parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--id', type=int, required=True,
                        help='Contest ID from DraftKings',)
    parser.add_argument('-c', '--csv', required=True, help='Slate CSV from DraftKings',)
    parser.add_argument('-s', '--sport', choices=['NBA', 'NFL', 'CFB', 'PGA', 'NHL'],
                        required=True, help='Type of contest (NBA, NFL, PGA, CFB, or NHL)')
    parser.add_argument('-v', '--verbose', help='Increase verbosity')
    args = parser.parse_args()

    # 62753724 Thursday night CFB $5 DU
    # https://www.draftkings.com/contest/exportfullstandingscsv/62753724
    contest_id = args.id
    fn = args.csv

    # 1244542866
    # CSV_URL = 'https://www.draftkings.com/lineup/getavailableplayerscsv?contestTypeId=21&draftGroupId=22168'
    # draftgroup info
    # 12 = MLB 21 = NFL 9 = PGA 24 = NASCAR 10 = Soccer 13 = MMA
    # friday night nba slate
    # https://www.draftkings.com/lineup/getavailableplayerscsv?contestTypeId=70&draftGroupId=22401

    # fn = 'DKSalaries_week7_full.csv'
    # fn = 'DKSalaries_Tuesday_basketball.csv'
    # dir = path.join('c:', sep, 'users', 'adam', 'documents', 'git', 'dk_salary_owner')
    dir = '/home/pi/Desktop/dk_salary_owner'
    # fn = 'DKSalaries_Sunday_NFL.csv'

    salary_dict = read_salary_csv(fn)

    # link to get csv export from contest id
    # https://www.draftkings.com/contest/exportfullstandingscsv/62252398

    # client id  837292985707-anvf2dcn7ng1ts9jq1b452qa4rfs5k25.apps.googleusercontent.com
    # secret 4_ifPYAtKg0DTuJ2PJDfsDda

    now = datetime.datetime.now()
    print("Current time: {}".format(now))
    fn2 = "contest-standings-{}.csv".format(contest_id)
    contest_list = pull_contest_zip(fn2, contest_id)
    parsed_lineup = {}
    # values = interate_contest_list(contest_list, salary_dict, args.sport)
    bros = ['aplewandowski', 'FlyntCoal', 'Cubbiesftw23',
            'Mcoleman1902', 'cglenn91', 'Notorious']
    values = []
    sport = args.sport
    bro_lineups = {}
    player_dict = {}
    for i, row in enumerate(contest_list[1:]):
        rank = row[0]
        name = row[2]
        pmr = row[3]
        points = row[4]
        lineup = row[5]

        if name in bros:
            print("found bro {}".format(name))
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

            name = massage_name(stats[0])
            pos = stats[1]
            salary = int(salary_dict[name]['salary'])
            if sport != 'PGA':
                team_abbv = salary_dict[name]['team_abbv']
                game_info = salary_dict[name]['game_info']
                matchup_info = get_matchup_info(game_info, team_abbv)
                game_time = get_game_time_info(game_info)
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
                'value': value
            }
            # print([name, pos, salary, perc, pts, value])
            values.append([pos, name, team_abbv, matchup_info, salary, perc, pts, value])

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

    # Call the Sheets API
    spreadsheet_id = '1Jv5nT-yUoEarkzY5wa7RW0_y0Dqoj8_zDrjeDs-pHL4'
    RANGE_NAME = "{}!A2:S".format(args.sport)
    sheet_id = find_sheet_id(service, spreadsheet_id, args.sport)

    print('Starting write_row')
    write_row(service, spreadsheet_id, RANGE_NAME, values)
    if parsed_lineup:
        print('Writing lineup')
        write_lineup(service, spreadsheet_id, sheet_id, parsed_lineup, args.sport)
    add_column_number_format(service, spreadsheet_id, sheet_id)
    add_header_format(service, spreadsheet_id, sheet_id)
    # add_cond_format_rules(service, spreadsheet_id, sheet_id)
    add_last_updated(service, spreadsheet_id, args.sport)
    # update_sheet_title(service, spreadsheet_id, sheet_id, args.sport)

    # link to get salary for NFL main slate
    # 'https://www.draftkings.com/lineup/getavailableplayerscsv?contestTypeId=21&draftGroupId=22168'


if __name__ == '__main__':
    main()
