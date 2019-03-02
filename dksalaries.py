"""
URL: https://www.draftkings.com/lobby/getcontests?sport=NBA
Response format: {
    'SelectedSport': 4,
    # To find the correct contests, see: find_new_contests()
    'Contests': [{
        'id': '16911618',                              # Contest id
        'n': 'NBA $375K Tipoff Special [$50K to 1st]', # Contest name
        'po': 375000,                                  # Total payout
        'm': 143750,                                   # Max entries
        'a': 3.0,                                      # Entry fee
        'sd': '/Date(1449619200000)/'                  # Start date
        'dg': 8014                                     # Draft group
        ... (the rest is unimportant)
    },
    ...
    ],
    # Draft groups are for querying salaries, see: run()
    'DraftGroups': [{
        'DraftGroupId': 8014,
        'ContestTypeId': 5,
        'StartDate': '2015-12-09T00:00:00.0000000Z',
        'StartDateEst': '2015-12-08T19:00:00.0000000',
        'Sport': 'NBA',
        'GameCount': 6,
        'ContestStartTimeSuffix': null,
        'ContestStartTimeType': 0,
        'Games': null
    },
    ...
    ],
    ... (the rest is unimportant)
}
"""

from csv import reader, writer
import argparse
import datetime
import os
import re
from pytz import timezone
import requests
# from nba.models import Player, DKContest, DKSalary

import browsercookie

CSVPATH = 'nba/data/salaries'


def find_new_contests():
    """
    Maybe this belongs in another module
    """

    def get_pst_from_timestamp(timestamp_str):
        timestamp = float(re.findall('[^\d]*(\d+)[^\d]*', timestamp_str)[0])
        return datetime.datetime.fromtimestamp(
            timestamp / 1000, timezone('America/Los_Angeles')
        )

    def get_largest_contest(contests, entry_fee):
        return sorted([c for c in contests if c['a'] == entry_fee],
                      key=lambda x: x['m'],
                      reverse=True)[0]

    def get_contests_by_entries(contests, entry_fee, limit):
        return sorted([c for c in contests
                       if c['a'] == entry_fee and c['m'] > limit],
                      key=lambda x: x['m'],
                      reverse=True)

    URL = 'https://www.draftkings.com/lobby/getcontests?sport=NBA'
    HEADERS = {
        'Accept': '*/*',
        'Accept-Encoding': 'gzip, deflate, sdch',
        'Accept-Language': 'en-US,en;q=0.8',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Cookie': os.environ['DK_AUTH_COOKIES'],
        'Host': 'www.draftkings.com',
        'Pragma': 'no-cache',
        'User-Agent': ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_5) '
                       'AppleWebKit/537.36 (KHTML, like Gecko) '
                       'Chrome/48.0.2564.97 Safari/537.36'),
        'X-Requested-With': 'XMLHttpRequest'
    }

    response = requests.get(URL, headers=HEADERS).json()
    contests = [
        get_largest_contest(response['Contests'], 3),
        get_largest_contest(response['Contests'], 0.25),
        get_largest_contest(response['Contests'], 27)
    ] + get_contests_by_entries(response['Contests'], 3, 50000)
    for contest in contests:
        date_time = get_pst_from_timestamp(contest['sd'])
        DKContest.objects.update_or_create(dk_id=contest['id'], defaults={
            'date': date_time.date(),
            'datetime': date_time,
            'name': contest['n'],
            'total_prizes': contest['po'],
            'entries': contest['m'],
            'entry_fee': contest['a']
        })


def write_salaries_to_db(input_rows, date=datetime.date.today()):
    return_rows = []
    csvreader = reader(input_rows, delimiter=',', quotechar='"')
    try:
        for i, row in enumerate(csvreader):
            if i != 0 and len(row) == 6:  # Ignore possible empty rows
                pos, name, salary, game, ppg, team = row
                player = Player.get_by_name(name)
                dksalary, _ = DKSalary.objects.get_or_create(
                    player=player,
                    date=date,
                    defaults={'salary': int(salary)}
                )
                player.dk_position = pos
                player.save()
                if dksalary.salary != int(salary):
                    print('Warning: trying to overwrite salary for %s.'
                          ' Ignoring - did not overwrite' % player)
                return_rows.append(row)
    except UnicodeEncodeError as e:
        print(e)
        return []
    return return_rows


def dump_csvs():
    """
    Writes all existing salary CSVs in the @CSVPATH directory to the database
    """

    FILE_DATETIME_REGEX = r'.*/dk_nba_salaries_([^\.]+).csv'

    files = [os.path.join(CSVPATH, f) for f in os.listdir(CSVPATH)
             if os.path.isfile(os.path.join(CSVPATH, f))]
    for filename in files:
        print('Writing salaries for %s' % filename)
        with open(filename, 'r') as f:
            datestr = re.findall(FILE_DATETIME_REGEX, filename)[0]
            date = datetime.datetime.strptime(datestr, '%Y_%m_%d').date()
            write_salaries_to_db(f, date)


def run(writecsv=True):
    """
    Downloads and unzips the CSV salaries and then populates the database
    """

    def get_salary_date(draft_groups):
        dates = [datetime.datetime.strptime(
            dg['StartDateEst'].split('T')[0], '%Y-%m-%d'
        ).date() for dg in response['DraftGroups']]
        date_counts = [(d, dates.count(d)) for d in set(dates)]
        # Get the date from the (date, count) tuple with the most counts
        return sorted(date_counts, key=lambda x: x[1])[-1][0]

    def get_salary_csv(draft_group_id, contest_type_id, date):
        """Assume the salaries for each player in different draft groups are the same for any given day."""
        URL = 'https://www.draftkings.com/lineup/getavailableplayerscsv'
        response = requests.get(URL, headers=HEADERS, params={
            'contestTypeId': contest_type_id,
            'draftGroupId': draft_group_id
        })
        return write_salaries_to_db(response.text.split('\n'), date)

    def write_csv(rows, date):
        HEADER_ROW = ['Position', 'Name', 'Salary', 'GameInfo',
                      'AvgPointsPerGame', 'teamAbbrev']
        outfile = ('%s/dk_nba_salaries_%s.csv'
                   % (CSVPATH, date.strftime('%Y_%m_%d')))
        # Remove duplicate rows and sort by salary, then name
        # Lists are unhashable so convert each element to a tuple
        rows = sorted(list(set([tuple(r) for r in rows])),
                      key=lambda x: (-int(x[2]), x[1]))
        print('Writing salaries to csv %s' % outfile)
        with open(outfile, 'w') as f:
            csvwriter = writer(f, delimiter=',', quotechar='"')
            csvwriter.writerow(HEADER_ROW)
            for row in rows:
                csvwriter.writerow(row)

    URL = 'https://www.draftkings.com/lobby/getcontests?sport=NBA'
    HEADERS = {
        'Accept': '*/*',
        'Accept-Encoding': 'gzip, deflate, sdch',
        'Accept-Language': 'en-US,en;q=0.8',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Cookie': os.environ['DK_AUTH_COOKIES'],
        'Host': 'www.draftkings.com',
        'Pragma': 'no-cache',
        'User-Agent': ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_5) '
                       'AppleWebKit/537.36 (KHTML, like Gecko) '
                       'Chrome/48.0.2564.97 Safari/537.36'),
        'X-Requested-With': 'XMLHttpRequest'
    }

    response = requests.get(URL, headers=HEADERS).json()
    rows_by_date = {}
    for dg in response['DraftGroups']:
        # dg['StartDateEst'] should be mostly the same for draft groups, (might
        # not be the same for the rare long-running contest) and should be the
        # date we're looking for (game date in US time).
        date = get_salary_date(response['DraftGroups'])
        print('Updating salaries for draft group %d, contest type %d, date %s'
              % (dg['DraftGroupId'], dg['ContestTypeId'], date))
        row = get_salary_csv(dg['DraftGroupId'], dg['ContestTypeId'], date)
        if date not in rows_by_date:
            rows_by_date[date] = []
        rows_by_date[date] += row
    if writecsv:
        for date, rows in rows_by_date.iteritems():
            write_csv(rows, date)


def get_pst_from_timestamp(timestamp_str):
    timestamp = float(re.findall(r'[^\d]*(\d+)[^\d]*', timestamp_str)[0])
    print(timestamp)
    return datetime.datetime.fromtimestamp(
        timestamp / 1000, timezone('America/Los_Angeles')
    )


def get_dt_from_timestamp(timestamp_str):
    timestamp = float(re.findall(r'[^\d]*(\d+)[^\d]*', timestamp_str)[0])
    return datetime.datetime.fromtimestamp(timestamp / 1000)


def get_largest_contest(contests, entry_fee, query=None, dt=datetime.datetime.today()):
    print("get_largest_contest(contests, {})".format(entry_fee))
    print(type(contests))
    print("contests size: {}".format(len(contests)))
    ls = []
    for c in contests:
        ts = get_dt_from_timestamp(c['sd'])
        if ts.date() == dt.date():
            if c['a'] == entry_fee:
                if query:
                    if query in c['n']:
                        ls.append(c)
                else:
                    ls.append(c)

    # sort contests by # of entries
    sorted_list = sorted(ls, key=lambda x: x['m'], reverse=True)

    # if there is a sorted list, return the
    if sorted_list:
        return sorted_list[0]

    return None


def get_contests_by_entries(contests, entry_fee, limit):
    return sorted([c for c in contests
                   if c['a'] == entry_fee and c['m'] > limit],
                  key=lambda x: x['m'],
                  reverse=True)


def main():
    """"""
    # parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-s', '--sport', choices=['NBA', 'NFL', 'CFB', 'GOLF', 'NHL'],
        required=True, help='Type of contest (NBA, NFL, GOLF, CFB, or NHL)')
    parser.add_argument(
        '-l', '--live', action='store_true', help='Get live contests')
    parser.add_argument(
        '-q', '--query', help='Search contest name')
    args = parser.parse_args()

    live = ''
    print(args)
    if args.live:
        print("args.live is true")
        live = 'live'

    # set query if there is an argument
    query = None
    if args.query:
        query = args.query

    today = datetime.datetime.today()
    weekday = today.strftime('%A')
    monthday = today.strftime('%d')
    month = today.strftime('%m')

    # set cookies based on Chrome session
    COOKIES = browsercookie.chrome()
    URL = "https://www.draftkings.com/lobby/get{0}contests?sport={1}".format(
        live, args.sport)
    HEADERS = {
        'Accept': '*/*',
        'Accept-Encoding': 'gzip, deflate, sdch',
        'Accept-Language': 'en-US,en;q=0.8',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        # 'Cookie': os.environ['DK_AUTH_COOKIES'],
        'Host': 'www.draftkings.com',
        'Pragma': 'no-cache',
        'User-Agent': ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_5) '
                       'AppleWebKit/537.36 (KHTML, like Gecko) '
                       'Chrome/48.0.2564.97 Safari/537.36'),
        'X-Requested-With': 'XMLHttpRequest'
    }

    response = requests.get(URL, headers=HEADERS, cookies=COOKIES).json()
    response_contests = {}
    if isinstance(response, list):
        print("response is a list")
        response_contests = response
    elif 'Contests' in response:
        print("response is a dict")
        response_contests = response['Contests']
    else:
        print("response isn't a dict or a list??? exiting")
        exit()

    # contests = [
    #     get_largest_contest(response_contests, 3),
    #     get_largest_contest(response_contests, 0.25),
    #     get_largest_contest(response_contests, 27)
    # ] + get_contests_by_entries(response_contests, 3, 50000)

    contests = [
        get_largest_contest(response_contests, 3, query),
        get_largest_contest(response_contests, 0.25, query),
        get_largest_contest(response_contests, 25, query)
    ]

    for contest in contests:
        # print("---------------")
        # print(contest)
        # print("---------------")
        date_time = get_pst_from_timestamp(contest['sd'])
        dt = get_dt_from_timestamp(contest['sd'])
        print("name: {}".format(contest['n']))
        print("date_time: {}".format(date_time))
        print("dt: {}".format(dt))
        print("contest id: {}".format(contest['id']))
        print("draft group: {}".format(contest['dg']))
        print("date: {}".format(date_time.date()))
        print("sd: {}".format(contest['sd']))
        print("total_prizes: {}".format(contest['po']))
        print("entries: {}".format(contest['m']))
        print("entry_fee: {}".format(contest['a']))
        print("")

        # print cron jobs
        print("*/10 0-1,19-23 {0}-{1:02d} {2} * cd /home/pi/Desktop/dk_salary_owner/ && /usr/local/bin/pipenv run python download_DK_salary.py -s {3} -dg {4} -f DKSalaries_{3}_{5}.csv >> /home/pi/Desktop/test.log 2>&1".format(
            monthday, int(monthday) + 1, month, args.sport, contest['dg'], weekday))
        print("*/5 0-1,19-23 {0}-{1:02d} {2} * cd /home/pi/Desktop/dk_salary_owner/ && /usr/local/bin/pipenv run python get_DFS_results.py -s {3} -i {4} -c DKSalaries_{3}_{5}.csv >> /home/pi/Desktop/NBA_results.log 2>&1".format(
            monthday, int(monthday) + 1, month, args.sport, contest['id'], weekday))


if __name__ == '__main__':
    main()
