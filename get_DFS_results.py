"""Use contest ID to update Google Sheet with DFS results."""
import argparse
import csv
import io
from os import path, sep
import requests
# from unidecode import unidecode
# import unicodedata
import zipfile
from datetime import datetime
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
                lines = io.TextIOWrapper(csvfile, newline='\r\n')
                # open reader object on csvfile within zip file
                rdr = csv.reader(lines, delimiter=',')
                return list(rdr)


def add_header_format(service, spreadsheet_id):
    """Format header (row 0) with white text on black blackground."""
    sheet_id = 0
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


def add_column_number_format(service, spreadsheet_id):
    """Format each specified column with explicit number format."""
    range_ownership = {
        'sheetId': 0,
        'startRowIndex': 1,
        'endRowIndex': 1000,
        'startColumnIndex': 5,  # F
        'endColumnIndex': 6
    }
    range_points = {
        'sheetId': 0,
        'startRowIndex': 1,
        'endRowIndex': 1000,
        'startColumnIndex': 6,  # G
        'endColumnIndex': 7
    }
    range_value = {
        'sheetId': 0,
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


def add_cond_format_rules(service, spreadsheet_id):
    """Add conditional formatting rules to ownership, points, and value fields."""
    color_yellow = {'red': 1.0, 'green': 0.839, 'blue': 0.4}
    color_white = {'red': 1.0, 'green': 1.0, 'blue': 1.0}
    color_red = {'red': 0.92, 'green': 0.486, 'blue': 0.451}
    color_green = {'red': 0.341, 'green': 0.733, 'blue': 0.541}
    range_ownership = {
        'sheetId': 0,
        'startRowIndex': 1,
        'endRowIndex': 1001,
        'startColumnIndex': 5,  # F
        'endColumnIndex': 6,
    }
    range_points = {
        'sheetId': 0,
        'startRowIndex': 1,
        'endRowIndex': 1001,
        'startColumnIndex': 6,  # G
        'endColumnIndex': 7,
    }
    value_range = {
        'sheetId': 0,
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
    print('Applying conditional formatting to sheet')
    batch_update_sheet(service, spreadsheet_id, requests)


def add_last_updated(service, spreadsheet_id):
    """Add (or update) the time in the header."""
    range = 'Sheet1!I1:J1'
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


def get_matchup_info(game_info, team_abbv):
    # split game info into matchup_info
    home_team, away_team = game_info.split(' ', 1)[0].split('@')
    if team_abbv == home_team:
        matchup_info = "vs. {}".format(away_team)
    else:
        matchup_info = "at {}".format(home_team)
    return matchup_info


def get_game_time_info(game_info):
    return game_info.split(' ', 1)[1]


def main():
    """Use contest ID to update Google Sheet with DFS results."""

    # parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--id', type=int, required=True,
                        help='Contest ID from DraftKings',)
    parser.add_argument('-c', '--csv', required=True, help='Slate CSV from DraftKings',)
    parser.add_argument('-t', '--type', choices=['NBA', 'NFL', 'CFB'],
                        required=True, help='Type of contest (NBA, NFL, or CFB)')
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

    # with open(path.join(dir, fn), mode='r') as f:
    with open(fn, mode='r') as f:
        cr = csv.reader(f, delimiter=',')
        slate_list = list(cr)

    salary_dict = {}
    # salary_dict = {row[2]: row[5] for row in slate_list}
    for row in slate_list[1:]:
        name = row[2]
        if name not in salary_dict:
            salary_dict[name] = {}
            salary_dict[name]['salary'] = 0
            salary_dict[name]['team_abbv'] = ''

        salary_dict[name]['salary'] = row[5]
        salary_dict[name]['game_info'] = row[6]
        salary_dict[name]['team_abbv'] = row[7]

    # link to get csv export from contest id
    # https://www.draftkings.com/contest/exportfullstandingscsv/62252398

    # client id  837292985707-anvf2dcn7ng1ts9jq1b452qa4rfs5k25.apps.googleusercontent.com
    # secret 4_ifPYAtKg0DTuJ2PJDfsDda

    fn2 = "contest-standings-{}.csv".format(contest_id)

    # contest_list = pull_contest_zip(fn2, contest_id)
    # fn2 = "contest-standings-61950009_finished.csv"
    # if path.exists(fn2):
    #     print("{0} exists".format(fn2))
    #     with open(fn2, mode='r') as f:
    #         # lines = io.TextIOWrapper(f, newline='\r\n')
    #         # print(lines)
    #         cr = csv.reader(f, delimiter=',')
    #         contest_list = list(cr)
    # else:
    #     contest_list = pull_contest_zip(fn2, contest_id)
    # contest_list = pull_contest_zip(fn2, contest_id)
    contest_list = pull_contest_zip(fn2, contest_id)

    # values
    # values = [
    #     [
    #         'A', 'B', 'C', 'D', 'E', 'F'
    #     ],
    #     [
    #         '1', '2', '3', '4', '5', '6'
    #     ]
    #     # etc
    # ]

    values_to_insert = []
    with open(path.join(dir, 'output.csv'), mode='w', newline='') as out:
        wrtr = csv.writer(out, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        for i, row in enumerate(contest_list[1:]):
            stats = row[7:]

            if stats:
                # continue if empty (sometimes happens on the player columns in the standings)
                if all('' == s or s.isspace() for s in stats):
                    continue
                name = stats[0]
                # wtf is going on with this guy's name?
                if 'Exum' in name:
                    name = 'Dante Exum'
                if 'Guillermo' in name:
                    name = 'Guillermo Hernangomez'
                # name = strip_accents(name)
                # print(name)
                pos = stats[1]
                salary = int(salary_dict[name]['salary'])
                team_abbv = salary_dict[name]['team_abbv']
                # print(salary_dict[name]['team_abbv'])
                game_info = salary_dict[name]['game_info']

                matchup_info = get_matchup_info(game_info, team_abbv)
                game_time = get_game_time_info(game_info)

                perc = float(stats[2].replace('%', '')) / 100
                pts = float(stats[3])

                # calculate value
                if pts > 0:
                    value = pts / (salary / 1000)
                else:
                    value = 0
                # print([name, pos, salary, perc, pts, value])
                values_to_insert.append(
                    [pos, name, team_abbv, matchup_info, salary, perc, pts, value])
                wrtr.writerow([pos, name, team_abbv, matchup_info,
                               salary, perc, pts, value])

    # google sheets API boilerplate
    SCOPES = 'https://www.googleapis.com/auth/spreadsheets'
    store = file.Storage(path.join(dir, 'token.json'))
    creds = store.get()
    if not creds or creds.invalid:
        flow = client.flow_from_clientsecrets(path.join(dir, 'token.json'), SCOPES)
        creds = tools.run_flow(flow, store)
    service = build('sheets', 'v4', http=creds.authorize(Http()))

    # Call the Sheets API
    SPREADSHEET_ID = '1Jv5nT-yUoEarkzY5wa7RW0_y0Dqoj8_zDrjeDs-pHL4'
    RANGE_NAME = 'Sheet1!A2:H'

    print('Starting write_row')
    write_row(service, SPREADSHEET_ID, RANGE_NAME, values_to_insert)

    add_column_number_format(service, SPREADSHEET_ID)
    add_header_format(service, SPREADSHEET_ID)
    # add_cond_format_rules(service, SPREADSHEET_ID)
    add_last_updated(service, SPREADSHEET_ID)
    update_sheet_title(service, SPREADSHEET_ID, args.type)

    # link to get salary for NFL main slate
    # 'https://www.draftkings.com/lineup/getavailableplayerscsv?contestTypeId=21&draftGroupId=22168'


if __name__ == '__main__':
    main()
