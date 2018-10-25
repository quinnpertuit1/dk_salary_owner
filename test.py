import browsercookie
import csv
import io
from os import path, sep
import requests
# from unidecode import unidecode
import unicodedata
import zipfile

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


def pull_csv(filename, csv_url):
    with requests.Session() as s:
        download = s.get(csv_url)

        decoded_content = download.content.decode('utf-8')

        cr = csv.reader(decoded_content.splitlines(), delimiter=',')
        my_list = list(cr)

        return my_list


def pull_contest_zip(filename, contest_id):
    contest_csv_url = 'https://www.draftkings.com/contest/exportfullstandingscsv/{0}'.format(
        contest_id)

    # ~/Library/Application Support/Google/Chrome/Default/Cookies

    # Uses Chrome's default cookies filepath by default
    # cookies = chrome_cookies(contest_csv_url, cookie_file='~/Library/Application Support/Google/Chrome/Default/Cookies')
    cookies = browsercookie.chrome()

    # retrieve exported contest csv
    r = requests.get(contest_csv_url, cookies=cookies)

    # request will be a zip file
    z = zipfile.ZipFile(io.BytesIO(r.content))

    for name in z.namelist():
        # csvfile = z.read(name)
        z.extract(name)
        with z.open(name) as csvfile:
            print("name within zipfile".format(name))

            lines = io.TextIOWrapper(csvfile, newline='\r\n')
            cr = csv.reader(lines, delimiter=',')
            my_list = list(cr)
            return my_list


# def pull_data(filename, ENDPOINT):
#     """Either pull file from API or from file."""
#     data = None
#     if not path.isfile(filename):
#         print("{} does not exist. Pulling from endpoint [{}]".format(filename, ENDPOINT))
#         # send GET request
#         r = requests.get(ENDPOINT)
#         status = r.status_code
#
#         # if not successful, raise an exception
#         if status != 200:
#             raise Exception('Requests status != 200. It is: {0}'.format(status))
#
#         # store response
#         data = r.json()
#
#         # dump json to file for future use to avoid multiple API pulls
#         with open(filename, 'w') as outfile:
#             json.dump(data, outfile)
#     else:
#         print("File exists [{}]. Nice!".format(filename))
#         # load json from file
#         with open(filename, 'r') as json_file:
#             data = json.load(json_file)
#
#     return data


def add_header_format(service, spreadsheet_id):
    header_range = {
        'sheetId': 0,
        'startRowIndex': 0,
        'endRowIndex': 1,
        'startColumnIndex': 0,  # A
        'endColumnIndex': 7,  # F
    }
    requests = [{
        "repeatCell": {
            "range": header_range,
            "cell": {
                "userEnteredFormat": {
                    "backgroundColor": {
                        "red": 0.0,
                        "green": 0.0,
                        "blue": 0.0
                    },
                    'horizontalAlignment': 'CENTER',
                    'textFormat': {
                        "foregroundColor": {
                            "red": 1.0,
                            "green": 1.0,
                            "blue": 1.0
                        },
                        'fontFamily': 'Trebuchet MS',
                        "fontSize": 10,
                        "bold": True
                    }
                }
            },
            'fields': "userEnteredFormat(backgroundColor, textFormat, horizontalAlignment)"
        }
    }, {
        "updateSheetProperties": {
            "properties": {
                "sheetId": 0,
                "gridProperties": {
                    "frozenRowCount": 1
                }
            },
            "fields": "gridProperties.frozenRowCount"
        }
    }]
    print('Applying header to sheet')
    batch_update_sheet(service, spreadsheet_id, requests)


def add_column_number_format(service, spreadsheet_id):
    range_ownership = {
        'sheetId': 0,
        'startRowIndex': 1,
        'endRowIndex': 1000,
        'startColumnIndex': 4,  # E
        'endColumnIndex': 5
    }
    range_points = {
        'sheetId': 0,
        'startRowIndex': 1,
        'endRowIndex': 1000,
        'startColumnIndex': 5,  # E
        'endColumnIndex': 6
    }
    range_value = {
        'sheetId': 0,
        'startRowIndex': 1,
        'endRowIndex': 1000,
        'startColumnIndex': 6,  # F
        'endColumnIndex': 7
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
    range_ownership = {
        'sheetId': 0,
        'startRowIndex': 1,
        'endRowIndex': 1001,
        'startColumnIndex': '4',  # E
        'endColumnIndex': '5',
    }
    range_points = {
        'sheetId': 0,
        'startRowIndex': 1,
        'endRowIndex': 1001,
        'startColumnIndex': '5',  # F
        'endColumnIndex': '6',
    }
    value_range = {
        'sheetId': 0,
        'startRowIndex': 1,
        'endRowIndex': 1001,
        'startColumnIndex': '6',  # G
        'endColumnIndex': '7',
    }
    # white --> yellow
    rule_white_yellow = {
        'minpoint': {
            'type': 'MIN',
            'color': {
                # white
                'red': 1.0,
                'green': 1.0,
                'blue': 1.0

            }
        },
        'maxpoint': {
            'type': 'MAX',
            'color': {
                # yellow
                'red': 1.0,
                'green': 0.839,
                'blue': 0.4
            }
        }
    }
    rule_red_white_green = {
        'minpoint': {
            # red
            'type': 'MIN',
            'color': {
                'red': 0.92,
                'green': 0.486,
                'blue': 0.451

            }
        },
        'midpoint': {
            # white
            'type': 'PERCENTILE',
            'value': '50',
            'color': {
                'red': 1.0,
                'green': 1.0,
                'blue': 1.0
            }
        },
        'maxpoint': {
            # green
            'type': 'MAX',
            'color': {
                'red': 0.341,
                'green': 0.733,
                'blue': 0.541
            }
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


def batch_update_sheet(service, spreadsheet_id, requests):
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


def main():
    # 62600001 Tuesday night $25 DU
    contest_id = 62600001
    #
    CSV_URL = 'https://www.draftkings.com/lineup/getavailableplayerscsv?contestTypeId=21&draftGroupId=22168'

    # fn = 'DKSalaries_week7_full.csv'
    # fn = 'DKSalaries_Tuesday_basketball.csv'
    dir = path.join('c:', sep, 'users', 'adam', 'documents', 'git', 'dk_salary_owner')
    fn = 'DKSalaries_Tuesday_basketball.csv'

    with open(path.join(dir, fn), mode='r') as f:
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
        salary_dict[name]['team_abbv'] = row[7]

    # link to get csv export from contest id
    # https://www.draftkings.com/contest/exportfullstandingscsv/62252398

    # client id  837292985707-anvf2dcn7ng1ts9jq1b452qa4rfs5k25.apps.googleusercontent.com
    # secret 4_ifPYAtKg0DTuJ2PJDfsDda

    # $50 week 7 contest id 61950009

    # my_list = pull_csv(fn, CSV_URL)
    # for row in my_list:
    #     print(row)

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
                # print(salary_dict[name]['team_abbv'])
                team_abbv = salary_dict[name]['team_abbv']
                perc = float(stats[2].replace('%', '')) / 100
                pts = float(stats[3])

                # calculate value
                if pts > 0:
                    value = pts / (salary / 1000)
                else:
                    value = 0
                # print([name, pos, salary, perc, pts, value])
                values_to_insert.append([name, team_abbv, pos, salary, perc, pts, value])
                wrtr.writerow([name, team_abbv, pos, salary, perc, pts, value])

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
    RANGE_NAME = 'Sheet1!A2:G'

    print('Starting write_row')
    write_row(service, SPREADSHEET_ID, RANGE_NAME, values_to_insert)

    add_column_number_format(service, SPREADSHEET_ID)
    add_header_format(service, SPREADSHEET_ID)
    add_cond_format_rules(service, SPREADSHEET_ID)

    # link to get salary for NFL main slate
    # 'https://www.draftkings.com/lineup/getavailableplayerscsv?contestTypeId=21&draftGroupId=22168'


if __name__ == '__main__':
    main()
