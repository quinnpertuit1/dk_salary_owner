"""Use contest ID to update Google Sheet with DFS results."""
import argparse
import csv
import io
import json
import re
import requests
# from unidecode import unidecode
# import unicodedata
import zipfile
from os import path, sep
from dateutil import parser
from datetime import datetime

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
    now = datetime.now()
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
    values = [
        ['Last Updated', datetime.now().strftime('%Y-%m-%d %H:%M:%S')]
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


def parse_lineup(lineup, points, pmr, rank, player_dict):
    splt = lineup.split(' ')

    positions = ['PG', 'SG', 'SF', 'PF', 'C', 'G', 'F', 'UTIL']
    # list comp for indicies of positions in splt
    indices = [i for i, l in enumerate(splt) if l in positions]
    # list comp for ending indices in splt. for splicing, the second argument is exclusive
    end_indices = [indices[i] for i in range(1, len(indices))]
    # append size of splt as last index
    end_indices.append(len(splt))

    # lineup = {splt[index]: ' '.join(splt[index + 1:end_indices[i]]) for i, index in enumerate(indices)}
    results = {
        'rank': rank,
        'pmr': pmr,
        'points': points
    }
    pts = 0
    value = 0
    for i, index in enumerate(indices):
        pos = splt[index]
        s = slice(index + 1, end_indices[i])
        name = splt[s]
        if name != 'LOCKED':
            name = ' '.join(name)
            if name in player_dict:
                pts = player_dict[name]['pts']
                value = player_dict[name]['value']
            else:
                pts = None
                value = None

        results[pos] = {
            'name': name,
            'pts': pts,
            'value': value
        }
    return results


def write_NBA_lineup(lineup, bro):
    values = [
        [bro, '', 'PMR', lineup['pmr']],
        ['Position', 'Player', 'Points', 'Value'],
        ['PG', lineup['PG']['name'], lineup['PG']['pts'], lineup['PG']['value']],
        ['SG', lineup['SG']['name'], lineup['SG']['pts'], lineup['SG']['value']],
        ['SF', lineup['SF']['name'], lineup['SF']['pts'], lineup['SF']['value']],
        ['PF', lineup['PF']['name'], lineup['PF']['pts'], lineup['PF']['value']],
        ['C', lineup['C']['name'], lineup['C']['pts'], lineup['C']['value']],
        ['G', lineup['G']['name'], lineup['G']['pts'], lineup['G']['value']],
        ['F', lineup['F']['name'], lineup['F']['pts'], lineup['F']['value']],
        ['UTIL', lineup['UTIL']['name'], lineup['UTIL']['pts'], lineup['UTIL']['value']],
        ['rank', lineup['rank'], lineup['points']]
    ]
    return values


def write_CFB_lineup(lineup):
    values = []
    for k, bro in lineup.items():
        values = [
            [k, '', 'PMR', bro['pmr']],
            ['Position', 'Player', 'Points', 'Value'],
            ['QB', bro['QB']['name'], bro['QB']['pts'], bro['QB']['value']],
            ['RB', bro['SG']['name'], bro['SG']['pts'], bro['SG']['value']],
            ['RB', bro['SF']['name'], bro['SF']['pts'], bro['SF']['value']],
            ['WR', bro['PF']['name'], bro['PF']['pts'], bro['PF']['value']],
            ['WR', bro['C']['name'], bro['C']['pts'], bro['C']['value']],
            ['WR', bro['G']['name'], bro['G']['pts'], bro['G']['value']],
            ['FLEX', bro['F']['name'], bro['F']['pts'], bro['F']['value']],
            ['SFLEX', bro['UTIL']['name'], bro['UTIL']['pts'], bro['UTIL']['value']],
            ['', '', bro['points']]
        ]
    return values


def write_lineup(service, spreadsheet_id, sheet_id, lineup, sport):
    if sport not in ['NBA']:
        return

    print("Sport == {} - trying to write_lineup()..".format(sport))

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

    # print(lineup)
    if sport == 'NBA':
        for i, (k, v) in enumerate(lineup.items()):
            # print("i: {} K: {}\nv:{}".format(i, k, v))
            values = write_NBA_lineup(v, k)
            print("trying to write line [{}] to {}".format(k, ranges[i]))
            write_row(service, spreadsheet_id, ranges[i], values)

    elif sport == 'CFB':
        values = write_CFB_lineup(lineup)

    # values = [
    #     ['Last Updated', datetime.now().strftime('%Y-%m-%d %H:%M:%S')]
    # ]

    # write_row(service, spreadsheet_id, RANGE_NAME, values)


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
    return name


def main():
    """Use contest ID to update Google Sheet with DFS results."""
    # 63149608
    # pull_dk_contests()
    # exit()

    # parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--id', type=int, required=True,
                        help='Contest ID from DraftKings',)
    parser.add_argument('-c', '--csv', required=True, help='Slate CSV from DraftKings',)
    parser.add_argument('-s', '--sport', choices=['NBA', 'NFL', 'CFB', 'PGA'],
                        required=True, help='Type of contest (NBA, NFL, PGA, or CFB)')
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
    dir = path.join('c:', sep, 'users', 'adam', 'documents', 'git', 'dk_salary_owner')
    # fn = 'DKSalaries_Sunday_NFL.csv'

    salary_dict = read_salary_csv(fn)

    # link to get csv export from contest id
    # https://www.draftkings.com/contest/exportfullstandingscsv/62252398

    # client id  837292985707-anvf2dcn7ng1ts9jq1b452qa4rfs5k25.apps.googleusercontent.com
    # secret 4_ifPYAtKg0DTuJ2PJDfsDda

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
            v['lineup'], v['points'], v['pmr'], v['rank'], player_dict)

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
