import json
import logging
import pickle
import requests

from datetime import datetime

logger = logging.getLogger(__name__)


def cj_from_cookies_json(working_cookies):
    filename = 'cookies.json'

    # create empty cookie jar
    cj = requests.cookies.RequestsCookieJar()

    now = datetime.now()
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
                        cookie_expiration = datetime.fromtimestamp(r_cookie.expires)
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


def main():

    s = requests.Session()

    contest_id = 72328846
    contest_csv_url = "https://www.draftkings.com/contest/exportfullstandingscsv/{0}".format(
        contest_id)

    # s.get(contest_csv_url)

    # works_cookies is the last successful set of cookies
    works_cookies = ''
    with open('pickled_cookies_works.txt', 'rb') as f:
        works_cookies = pickle.load(f)

    cj = cj_from_cookies_json(works_cookies)
    cookie_count = 0

    logger.info("removing cookies from cj [cookies.json] already in session")
    for c in cj:
        if c.name in s.cookies:
            # logger.info("found {} in s.cookies - removing from cj".format(c.name))
            cj.clear(c.domain, c.path, c.name)
        else:
            cookie_count += 1
            logger.info("did not find {} in s.cookies, adding below".format(c.name))

    logger.info("adding all missing cookies [{}] to session.cookies".format(cookie_count))
    # logger.info(cj)
    s.cookies.update(cj)

    r = s.get(contest_csv_url)
    logger.info("r.status_code: {}".format(r.status_code))
    logger.info("r.url: {}".format(r.url))

    print(r.headers)
    # if headers say file is a CSV file
    if r.headers['Content-Type'] == 'text/csv':
        print("text/csv")
        # write working cookies
        with open('pickled_cookies_works.txt', 'wb') as f:
            pickle.dump(s.cookies, f)
    elif 'text/html' in r.headers['Content-Type']:
        # print(r)
        # write broken cookies
        with open('pickled_cookies_broken.txt', 'wb') as f:
            pickle.dump(s.cookies, f)
        exit('We cannot do anything with html!')
    else:
        print("zip file?")
        # write working cookies
        with open('pickled_cookies_works.txt', 'wb') as f:
            pickle.dump(s.cookies, f)


if __name__ == "__main__":
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter(fmt='%(asctime)s %(funcName)11s %(levelname)5s %(message)s',
                                  datefmt='%Y-%m-%d %H:%M:%S')

    # configure and add stream handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    main()
