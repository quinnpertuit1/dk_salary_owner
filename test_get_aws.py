import requests


def pull_html():
    """Pull contest file (so far can be .zip or .csv file)."""
    # contest_csv_url = "https://www.draftkings.com/contest/exportfullstandingscsv/{0}".format(
    #     contest_id)

    url = 'https://www.rotogrinders.com'
    filename = 'test.txt'

    # ~/Library/Application Support/Google/Chrome/Default/Cookies

    cookies = {
        # this appears to be the only required cookie
        'remember_82e5d2c56bdd0811318f0cf078b78bfc': 'eyJpdiI6ImFYRGlpZzRBeXArQ1NXNTd3aURXb0E9PSIsInZhbHVlIjoiVjdRN1R4TndGRzdzZDdmdjFDVEx2XC9vWEwwWE4yKzZaelhFKytnVzhpT1JrUnRtM004cEgxWEZONDVlY2tUMGIiLCJtYWMiOiJjYzlmMDg1YmQ4ZjBmODExMWNlOTM3YmY2ZWQ5MGQ5ZDBjOGYwMjZjMDI4ZTIwZjY0MzU3YmFmMmE5MWYxMzc5In0%3D'
    }

    # Uses Chrome's default cookies filepath by default
    # cookies = chrome_cookies(contest_csv_url, cookie_file='~/Library/Application Support/Google/Chrome/Default/Cookies')
    # cookies = browsercookie.chrome()

    # retrieve exported contest csv
    # r = requests.get(contest_csv_url, cookies=cookies)
    r = requests.get(url, cookies=cookies)
    print(r.headers)

    # dump html to file to avoid multiple requests
    with open(filename, 'w') as outfile:
        print(r.text, file=outfile)


def main():
    """Use contest ID to update Google Sheet with DFS results."""
    pull_html()


if __name__ == '__main__':
    main()
