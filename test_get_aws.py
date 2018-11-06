import requests


def sessions_test():
    session = requests.session()
    r1 = session.get('https://www.draftkings.com/lobby#/NBA/0/All')

    gch = requests.cookies.create_cookie(
        'gch', 'eyJJZCI6MjIwNTg4Mzc3NiwiUmVzdHJpY3RlZCI6ZmFsc2UsIlNvdXJjZSI6MSwiU3RhdHVzIjoxLCJFeHBpcmVzIjoiMjAxOC0xMS0wNlQwMzo1MTo0OC4yMVoiLCJMb2NhdGlvbiI6IlVTLUZMIiwiSGFzaCI6ImhGWWQ0TzEzczk3ZUNLZysxeG1jMHdHNkovNEpuNWFzeVJycGc2ZldrWkU9IiwiU2l0ZUV4cGVyaWVuY2UiOiJVUy1ESyJ9')
    iv = requests.cookies.create_cookie(
        'iv', 'CORrtlZd11anmOIOXQ+cpg43+vusypQPtxCAL0LUHOc=')
    jwe = requests.cookies.create_cookie('jwe', 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiIsInZlcnNpb24iOiIxIn0.eyJ1bmlxdWVfbmFtZSI6ImFwbGV3YW5kb3dza2kiLCJ1ayI6IjJkZjg1NjNjLWQ4YTctNGI4My1hMjNiLTVmN2M1MDBiOWE3MiIsInJvbGUiOiJOb3JtYWwiLCJlbWFpbCI6InJlbG9teUBnbWFpbC5jb20iLCJyYWZpZCI6IiIsInZpZCI6IjExNzY5MzY2MzciLCJsaWQiOiIxIiwiamlkIjoiMzU2NzkzMTkwNSIsImprZXkiOiJjdXJyZW50IiwiZnRkYmUiOiJGYWxzZSIsImdlbyI6IlVTLUZMIiwiZnZzIjoiMCIsImNkYXRlIjoiMjAxOC0xMS0wNiAwMDo1MTo0N1oiLCJpdiI6IlB3RW90UXhZWGF6dzZyR1MxWlB1UGc9PSIsImV1aWQiOiJXR3YwbWVFRFU2MDBTWE9vTUx4V3VnPT0iLCJ1dnMiOlsiMC0xIiwiMC04IiwiMC0xIiwiMC04Il0sIkRLUC1EZW55QmVnaW5uZXJDb250ZXN0cyI6InRydWUiLCJES1AtRGVueUNhc3VhbENvbnRlc3RzIjoidHJ1ZSIsInN4cCI6IlVTLURLIiwiYXV0aCI6IjcwYzU0M2FjLTJjZWQtNGU0Mi05NDFlLTMxNDEwYjM3NGZkYyIsImx0IjoiZHJhZnRraW5ncyIsImlzcyI6InVybjpkay9jZXJiZXJ1cyIsImF1ZCI6InVybjpkayIsImV4cCI6MTU0MTQ2NTgwOCwibmJmIjoxNTQxNDY1NTA4fQ.H0eGJPkxCsaySZz6Wjge_TazBHkuRfMOYx45YKa3cGA')

    session.cookies.set_cookie(gch)
    session.cookies.set_cookie(iv)
    session.cookies.set_cookie(jwe)

    url = 'https://www.draftkings.com/lobby#/NBA/0/All'
    r2 = session.get(url)
    print(r2.headers)

    # dump html to file to avoid multiple requests
    with open('sessions_test.html', 'w') as outfile:
        print(r2.text, file=outfile)


def pull_DK():
    """Pull contest file (so far can be .zip or .csv file)."""
    # contest_csv_url = "https://www.draftkings.com/contest/exportfullstandingscsv/{0}".format(
    #     contest_id)

    url = 'https://www.draftkings.com/lobby#/featured'
    filename = 'test.html'

    # ~/Library/Application Support/Google/Chrome/Default/Cookies

    cookies = {
        'EXC': '6046350318:73',
        'LID': '1',
        'SIDN': '5963343938',
        'SINFN': 'PID=&AOID=&PUID=5490900&SSEG=&GLI=0&LID=1&site=US-DK',
        'SN': '1223548523',
        'SSIDN': '6046350318',
        'STE': '"2018-11-06T01:21:49.4133082Z"',
        'STH': 'cee6fea86d2072f786532b7d289b4b068aece9292082e2253b2029c0e1463650',
        'STIDN': 'eyJDIjoxMjIzNTQ4NTIzLCJTIjo1OTYzMzQzOTM4LCJTUyI6NjA0NjM1MDMxOCwiViI6MTE3NjkzNjYzNywiTCI6MSwiRSI6IjIwMTgtMTEtMDZUMDE6MjE6NDcuNjMwODU5N1oiLCJTRSI6IlVTLURLIn0=',
        'VIDN': '1176936637',
        '_csrf': 'dec559af-66ee-4eb1-9c0a-b94a1997af83',
        'gch': 'eyJJZCI6MjIwNTg4Mzc3NiwiUmVzdHJpY3RlZCI6ZmFsc2UsIlNvdXJjZSI6MSwiU3RhdHVzIjoxLCJFeHBpcmVzIjoiMjAxOC0xMS0wNlQwMzo1MTo0OC4yMVoiLCJMb2NhdGlvbiI6IlVTLUZMIiwiSGFzaCI6ImhGWWQ0TzEzczk3ZUNLZysxeG1jMHdHNkovNEpuNWFzeVJycGc2ZldrWkU9IiwiU2l0ZUV4cGVyaWVuY2UiOiJVUy1ESyJ9',
        'hgg': 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ2aWQiOiIzMTMzNzEyMDU1IiwiZGtlLTMzIjoiMjAwIiwiZGtlLTYwIjoiMjg1IiwiZGtlLTEwNyI6IjMxOSIsImRraC0xMTEiOiJ0bjlCSkFaSyIsImRrZS0xMTEiOiIwIiwiZGtlLTExNSI6IjM0MCIsImRrZS0xMTgiOiIzNTEiLCJka2gtMTE5IjoiaUdXR0VkTkciLCJka2UtMTE5IjoiMCIsImRrZS0xMjAiOiIzNTgiLCJka2gtMTI2Ijoicmt3ZTRVSngiLCJka2UtMTI2IjoiMCIsImRraC0xMjkiOiJ5SWVSYzVoRCIsImRrZS0xMjkiOiIwIiwiZGtlLTE0MCI6IjQyMCIsImRrZS0xNDIiOiI0MjUiLCJka2UtMTQ0IjoiNDMxIiwiZGtlLTE0NSI6IjQzNiIsImRrZS0xNDkiOiI0NTQiLCJka2UtMTUwIjoiNTY3IiwiZGtlLTE1MSI6IjQ1NyIsImRrZS0xNTIiOiI0NTgiLCJka2UtMTUzIjoiNDU5IiwiZGtlLTE1NCI6IjQ2MCIsImRrZS0xNTUiOiI0NjEiLCJka2UtMTU2IjoiNDYyIiwiZGtlLTE2OCI6IjUxOCIsImRraC0xNzYiOiI2ems0OHFoUCIsImRrZS0xNzYiOiIwIiwiZGtlLTE3OSI6IjU2OSIsImRrZS0xODMiOiIxMDU0IiwiZGtlLTE5MCI6IjYyMSIsImRrZS0yMDQiOiI3MTAiLCJka2UtMjA5IjoiNzQ3IiwiZGtlLTIxMyI6Ijc3MCIsImRrZS0yMTUiOiI3NzkiLCJka2UtMjE4IjoiODAzIiwiZGtlLTIxOSI6Ijk2MCIsImRrZS0yMjEiOiI4MTMiLCJka2UtMjI1IjoiODM3IiwiZGtoLTIyOSI6IlZjekJQTEZkIiwiZGtlLTIyOSI6IjAiLCJka2UtMjMwIjoiODU3IiwiZGtlLTIzNSI6Ijg5MSIsImRrZS0yMzgiOiI5MDQiLCJka2UtMjQ1IjoiMTAwOSIsImRrZS0yNDYiOiI5ODIiLCJka2UtMjUwIjoiOTY1IiwiZGtoLTI1MiI6InVyS2ZKYjVxIiwiZGtlLTI1MiI6IjAiLCJka2UtMjU5IjoiMTAwNSIsImRrZS0yNjkiOiIxMDUwIiwiZGtlLTI3NSI6IjEwNzgiLCJka2UtMjgwIjoiMTA5MyIsImRrZS0yODgiOiIxMTI4IiwiZGtlLTI4OSI6IjExMzYiLCJka2UtMjkwIjoiMTE0MyIsImRrZS0yOTEiOiIxMTQ5IiwiZGtlLTI5MyI6IjExNTkiLCJka2UtMjk1IjoiMTE3MiIsImRrZS0yOTYiOiIxMTc2IiwiZGtlLTI5NyI6IjExODAiLCJka2UtMzAwIjoiMTE4OCIsImRrZS0zMDEiOiIxMTkwIiwiZGtlLTMwMiI6IjExOTIiLCJka2UtMzAzIjoiMTE5NSIsImRraC0zMDQiOiJmRk9Sb1JTaSIsImRrZS0zMDQiOiIwIiwiZGtlLTMwNSI6IjEyMDciLCJka2UtMzA2IjoiMTIxMiIsImRrZS0zMDciOiIxMjE2IiwiaXNzIjoiZGsiLCJleHAiOjE1NDE0NjU3OTksIm5iZiI6MTU0MTQ2NTQ5OX0.4vbXtQ-P0e5UJ2pL9EbjlNeW7NQ981yvcAhVCZBucfg',
        'iv': 'CORrtlZd11anmOIOXQ+cpg43+vusypQPtxCAL0LUHOc=',
        'jwe': 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiIsInZlcnNpb24iOiIxIn0.eyJ1bmlxdWVfbmFtZSI6ImFwbGV3YW5kb3dza2kiLCJ1ayI6IjJkZjg1NjNjLWQ4YTctNGI4My1hMjNiLTVmN2M1MDBiOWE3MiIsInJvbGUiOiJOb3JtYWwiLCJlbWFpbCI6InJlbG9teUBnbWFpbC5jb20iLCJyYWZpZCI6IiIsInZpZCI6IjExNzY5MzY2MzciLCJsaWQiOiIxIiwiamlkIjoiMzU2NzkzMTkwNSIsImprZXkiOiJjdXJyZW50IiwiZnRkYmUiOiJGYWxzZSIsImdlbyI6IlVTLUZMIiwiZnZzIjoiMCIsImNkYXRlIjoiMjAxOC0xMS0wNiAwMDo1MTo0N1oiLCJpdiI6IlB3RW90UXhZWGF6dzZyR1MxWlB1UGc9PSIsImV1aWQiOiJXR3YwbWVFRFU2MDBTWE9vTUx4V3VnPT0iLCJ1dnMiOlsiMC0xIiwiMC04IiwiMC0xIiwiMC04Il0sIkRLUC1EZW55QmVnaW5uZXJDb250ZXN0cyI6InRydWUiLCJES1AtRGVueUNhc3VhbENvbnRlc3RzIjoidHJ1ZSIsInN4cCI6IlVTLURLIiwiYXV0aCI6IjcwYzU0M2FjLTJjZWQtNGU0Mi05NDFlLTMxNDEwYjM3NGZkYyIsImx0IjoiZHJhZnRraW5ncyIsImlzcyI6InVybjpkay9jZXJiZXJ1cyIsImF1ZCI6InVybjpkayIsImV4cCI6MTU0MTQ2NTgwOCwibmJmIjoxNTQxNDY1NTA4fQ.H0eGJPkxCsaySZz6Wjge_TazBHkuRfMOYx45YKa3cGA',
        'mlc': 'true',
        'site': 'US-DK',
        'uk': '1',
    }

    # r = requests.get(url, cookies=cookies)
    r = requests.get(url, cookies=cookies)
    print(r.headers)

    # dump html to file to avoid multiple requests
    with open(filename, 'w') as outfile:
        print(r.text, file=outfile)


def pull_roto():
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

    r = requests.get(url, cookies=cookies)
    print(r.headers)

    # dump html to file to avoid multiple requests
    with open(filename, 'w') as outfile:
        print(r.text, file=outfile)


def main():
    """Use contest ID to update Google Sheet with DFS results."""
    sessions_test()


if __name__ == '__main__':
    main()
