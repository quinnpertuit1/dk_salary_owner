# logs into DraftKings automatically given a contest id (need id because the failed login
# page that you get is easier to run selenium on than the standard login page)
def login(browser, id):
    browser.get('https://www.draftkings.com/contest/exportfullstandingscsv/' + str(id))
    login_link = browser.find_element_by_id("login-link")
    webdriver.ActionChains(browser).move_to_element(login_link).click(login_link).perform()
    # stupid site has a hidden elem and a unhidden elem, we need the unhidden
    username_elements = browser.find_elements_by_id("Username")
    username_elements[1].send_keys("theyellowman86")
    password_elements = browser.find_elements_by_id("Password")
    password_elements[1].send_keys("george4mvp")

    login_button = browser.find_element_by_id("buttonText")
    webdriver.ActionChains(browser).move_to_element(login_button).click(login_button).perform()
    time.sleep(3) #sleep to let the server process that we've logged in

def download_csv(ids):
    browser = webdriver.Firefox()
    login(browser,ids[0])
    time.sleep(40) #use this time to select the folder you want to download to
    browser.get('https://www.draftkings.com/contest/exportfullstandingscsv/' + str(ids[0]))
    '''
    sleep for 10 secs here to let you set firefox settings to auto download.
    if you don't, you will get infinite pop up windows asking you what you want
    to do. technically, you can make a firefox profile to combat this, but its
    too annoying, and this is low-hassle solution
    '''
    time.sleep(10) #gives you a chance to set firefox settings to auto download / set location of downloads

    # download rest of results automatically!
    for i in range(1,len(ids)):
        browser.get('https://www.draftkings.com/contest/exportfullstandingscsv/' + str(ids[i]))
        time.sleep(1)
        print i

def get_our_contest_ids():
    file_names = ['11212014contests.html', '11212014contests2.html']
    ids = set()
    contests = {}
    pattern = re.compile('^\$(\d*)')
    for file_name in file_names:
        soup = BeautifulSoup(open(file_name))
        divs = soup.find_all('div')
        desired_divs = []
        for div in divs:
            if div.text == "11/22/2014":
                desired_divs.append(div.previous_sibling.previous_sibling.previous_sibling.previous_sibling.previous_sibling)

        for div in desired_divs:
            results = div.find_all('a')
            for result in results:
                attributes = result.attrs
                if "data-cid" in attributes.keys():
                    ids.add(attributes['data-cid'])
                    contest_description = str(result.text).split(' ')
                    for word in contest_description:
                        if pattern.match(word) != None:
                            contests[attributes['data-cid']] = word
                            break
    print ids

    return [id for id in ids], contests

# gets the cutoff value for a 50/50 contest given the contest_result csv file from DraftKings
def get_cutoff(contest_file):
    with open(contest_file, 'r') as csvfile:
        reader = csv.reader(csvfile)
        all_rows = list(reader)
        cutoff_index = (len(all_rows) - 1) / 2
        print contest_file, all_rows[cutoff_index][4]
        return all_rows[cutoff_index][4]

# calculates the average and median cutoff for different 50/50 stakes
def cutoffs_stats(ids, contests):
    cutoffs = {}
    average_cutoffs = {}
    median_cutoffs = {}
    for id in ids:
        try:
            cutoff = get_cutoff(os.path.join('11192014_draftkings_contests_results', 'contest-standings-' + str(id) + '.csv'))
        except Exception:
            print 'contest cancelled'
        game_type = contests[id]
        if game_type not in cutoffs.keys():
            cutoffs[game_type] = []
        cutoffs[game_type].append(float(cutoff))
    for k in cutoffs.keys():
        average_cutoffs[k] = np.average(np.array(cutoffs[k]))
        median_cutoffs[k] = np.median(np.array(cutoffs[k]))
    return average_cutoffs, median_cutoffs


if __name__ == "__main__":
    d = 'draftkings scrapes/'
    fn = '20141119_draftkings_nba_lobby.htm'
    html_page = d + fn
    matches = get_all_ids(html_page)
    print matches

    '''
    with open(d + fn.split('.')[0] + '_results.txt', 'wb') as f:
        for m in matches:
            f.write(m['n'] + " /// " + str(m['id']) + '\n')
    '''
    ids = []
    contests = {}
    for m in matches:
        if 'NBA' in str(m['n']) and '50/50' in str(m['n']):
            ids.append(m['id'])
            contests[m['id']] = m['a']

    pprint(cutoffs_stats(ids, contests))
    pdb.set_trace()
    #for m in matches:
    #   print m['n'] + " /// " + str(m['id'])
    download_csv(ids)
