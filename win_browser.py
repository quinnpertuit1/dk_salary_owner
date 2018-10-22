import csv
import io
from os import path
import requests
import zipfile

import browsercookie


def pull_csv(filename, csv_url):
    with requests.Session() as s:
        download = s.get(csv_url)

        decoded_content = download.content.decode('utf-8')

        cr = csv.reader(decoded_content.splitlines(), delimiter=',')
        my_list = list(cr)

        return my_list


def pull_contest_zip(filename, contest_id):
    contest_csv_url = 'https://www.draftkings.com/contest/exportfullstandingscsv/{0}'.format(contest_id)

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
        outfile = "{}_finished.txt".format(contest_id)
        z.extract(name)
        with z.open(name) as csvfile:
            print(name)
            print(csvfile)

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


def main():
    contest_id = 61945587
    CSV_URL = 'https://www.draftkings.com/lineup/getavailableplayerscsv?contestTypeId=21&draftGroupId=22168'

    fn = 'DKSalaries_week7_full.csv'

    with open(fn, mode='r') as f:
        cr = csv.reader(f, delimiter=',')
        slate_list = list(cr)

    salary_dict = {row[2]: row[5] for row in slate_list}

    # link to get csv export from contest id
    # https://www.draftkings.com/contest/exportfullstandingscsv/62252398


    # $50 week 7 contest id 61950009

    # my_list = pull_csv(fn, CSV_URL)
    # for row in my_list:
    #     print(row)

    fn2 = "contest-standings-{}.csv".format(contest_id)

    # contest_list = pull_contest_zip(fn2, contest_id)
    # fn2 = "contest-standings-61950009_finished.csv"
    if path.exists(fn2):
        with open(fn2, mode='r') as f:
            # lines = io.TextIOWrapper(f, newline='\r\n')
            # print(lines)
            cr = csv.reader(f, delimiter=',')
            contest_list = list(cr)
    else:
        contest_list = pull_contest_zip(fn2, contest_id)

    with open('output.csv', mode='w', newline='') as out:
        wrtr = csv.writer(out, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        for i, row in enumerate(contest_list[1:]):
            stats = row[7:]
            if stats:
                name = stats[0]
                pos = stats[1]
                salary = int(salary_dict[stats[0]])
                perc = float(stats[2].replace('%', '')) / 100
                pts = float(stats[3])
                # calculate value
                if pts > 0:
                    value = pts / (salary / 1000)
                else:
                    value = 0
                print([name, pos, salary, perc, pts, value])
                wrtr.writerow([name, pos, salary, perc, pts, value])
            # print("name {0}: salary {1} perc [{2}] pts {3}".format())
            # if row[7] == '':
            #     print(i)
            #     break

    # link to get salary for NFL main slate
    # 'https://www.draftkings.com/lineup/getavailableplayerscsv?contestTypeId=21&draftGroupId=22168'


if __name__ == "__main__":
    main()
