import argparse
import csv
import json
import re
import requests
from datetime import datetime
from dateutil import parser
from os import path
from bs4 import BeautifulSoup

import browsercookie


def pull_salary_csv(filename, csv_url):
    """Pull CSV for salary information."""
    with requests.Session() as s:
        download = s.get(csv_url)

        decoded_content = download.content.decode('utf-8')

        cr = csv.reader(decoded_content.splitlines(), delimiter=',')
        my_list = list(cr)

        return my_list


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
    contest_dict = {}
    for type in ['upcoming', 'live']:
        print("\n{}".format(type.upper()))
        pattern = re.compile(r"{}: (.*),".format(type))
        json_str = pattern.search(js_contest_data).group(1)
        contest_json = json.loads(json_str)

        bool_quarters = False
        now = datetime.now()
        # iterate through json
        for contest in contest_json:
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

            contest_dict[id] = {
                'name': name,
                'group_id': group_id,
                'game_type': game_type,
                'start_time': dt_starttime
            }

            print("ID: {} buyin: {} payout: {} est_startime: {} starts in: {} [{}]".format(
                id, buyin, top_payout, est_starttime, time_until, name))
            print("group_id: {} game_type: {}".format(group_id, game_type))
            print("https://www.draftkings.com/lineup/getavailableplayerscsv?contestTypeId={}&draftGroupId={}".format(game_type, group_id))
    return contest_dict


def get_csv_url(sport, contests):
    for k, v in contests.items():
        if sport in v['name']:
            game_type = v['game_type']
            group_id = v['group_id']
            csv_url = "https://www.draftkings.com/lineup/getavailableplayerscsv?contestTypeId={0}&draftGroupId={1}".format(game_type, group_id)
            return csv_url


def get_sport_day(sport, contests):
    for k, v in contests.items():
        if sport in v['name']:
            dt = v['start_time']
            return "{0:%A}".format(dt)


def main():
    # parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('-s', '--sport', choices=['NBA', 'NFL', 'CFB', 'PGA'], help='Type of contest (NBA, NFL, PGA, or CFB)')
    args = parser.parse_args()

    contests = pull_dk_contests()

    if args.sport:
        csv_url = get_csv_url(args.sport, contests)
        day = get_sport_day(args.sport, contests)
        print(day)
        filename = "DKSalaries_{0}_{1}.csv".format(args.sport, day)
        print(csv_url)
        print(filename)
        pull_soup_data(filename, csv_url)


if __name__ == '__main__':
    main()
