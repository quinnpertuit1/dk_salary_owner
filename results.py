import argparse
import csv
import datetime
import io
import logging
import logging.config
import unicodedata

# load the logging configuration
logging.config.fileConfig('logging.ini')
# logger = logging.getLogger(__name__)


def strip_accents(s):
    """Strip accents from a given string and replace with letters without accents."""
    return ''.join(c for c in unicodedata.normalize('NFD', s)
                   if unicodedata.category(c) != 'Mn')


class User(object):
    def __init__(self, rank, id, name, pmr, pts, lineup_str):
        self.rank = rank
        self.id = id
        self.name = name
        self.pmr = pmr
        self.pts = pts
        self.lineup_str = lineup_str

        # self.lineup = lineup_str.split()

    def __repr__(self):
        return "User({}, {}, {}, {}, {})".format(self.name, self.rank, self.pmr, self.pts, self.lineup_str)


class Player(object):
    def __init__(self, name, pos, salary, game_info, team_abbv, logger=None):
        self.logger = logger or logging.getLogger(__name__)

        self.name = name
        self.pos = pos
        self.salary = int(salary)
        self.game_info = game_info
        self.team_abbv = team_abbv

        # to be updated - update_stats
        self.standings_pos = ''
        self.perc = 0.0
        self.fpts = 0.0

        # to be updated - get_matchup_info
        self.matchup_info = ''

    def update_stats(self, pos, perc, fpts):
        """Update class variables from contest standings file (contest-standings-nnnnnnnn.csv)."""
        self.standings_pos = pos
        self.perc = float(perc.replace('%', '')) / 100
        self.fpts = float(fpts)

        # calculate value
        if self.fpts > 0:
            self.value = self.fpts / (self.salary / 1000)
        else:
            self.value = 0

        self.get_matchup_info()

    def get_matchup_info(self):
        # wth is this?
        # logger.debug(game_info)
        # this should take care of golf
        if '@' not in self.game_info:
            return

        if self.game_info in ['In Progress', 'Final', 'Postponed', 'UNKNOWN', 'Suspended', 'Delayed']:
            return

        # split game info into matchup_info
        home_team, a = self.game_info.split('@')
        away_team, match_time = a.split(' ', 1)
        # self.logger.debug("home_team: {} away_team: {} t: {}".format(
        #     home_team, away_team, match_time))
        home_team, away_team = self.game_info.split(' ', 1)[0].split('@')
        if self.team_abbv == home_team:
            matchup_info = "vs. {}".format(away_team)
        else:
            matchup_info = "at {}".format(home_team)
        return matchup_info

    def __str__(self):
        return "[Player] {} {} Sal: ${} - {:.4f} - {} pts Game_Info: {} Team_Abbv: {}".format(
            self.pos, self.name, self.salary, self.perc, self.fpts, self.game_info, self.team_abbv
        )

    def __repr__(self):
        return "Player({}, {}, {}, {}, {})".format(self.name, self.pos, self.salary, self.game_info, self.team_abbv)


class Results(object):
    def __init__(self, sport, contest_id, salary_csv_fn, logger=None):
        self.logger = logger or logging.getLogger(__name__)

        self.sport = sport
        self.contest_id = contest_id
        self.players = []
        self.complete_players = []
        self.users = []

        # if there's no salary file specified, use the sport/day for the filename
        if not salary_csv_fn:
            salary_csv_fn = "DKSalaries_{}_{}.csv".format(
                args.sport, datetime.datetime.now().strftime('%A'))

        self.players_salary_csv(salary_csv_fn)
        self.logger.debug(self.players)

        self.vips = ['aplewandowski', 'FlyntCoal', 'Cubbiesftw23', 'Mcoleman1902',
                     'cglenn91', 'Notorious', 'Bra3105', 'ChipotleAddict']
        self.vip_list = []

        contest_fn = 'contest-standings-73165360.csv'

        # this pulls the DK users and updates the players stats
        self.parse_contest_standings(contest_fn)

        for player in self.complete_players:
            self.logger.debug(player)

        for vip in self.vip_list:
            self.logger.debug("VIP: {}".format(vip))

        for p in self.complete_players[:5]:
            self.logger.info(p)

    def players_salary_csv(self, fn):
        with open(fn, mode='r') as f:
            cr = csv.reader(f, delimiter=',')
            slate_list = list(cr)

            for row in slate_list[1:]:  # [1:] to skip header
                if len(row) < 2:
                    continue
                # TODO: might use roster_pos in the future
                pos, _, name, _, roster_pos, salary, game_info, team_abbv, appg = row
                self.players.append(Player(name, pos, salary, game_info, team_abbv))

    def parse_contest_standings(self, fn):
        list = self.load_standings(fn)
        # create a copy of player list
        player_list = self.players
        for row in list[1:]:
            rank, id, name, pmr, points, lineup = row[:6]

            # create User object and append to users list
            u = User(rank, id, name, pmr, points, lineup)
            self.users.append(u)

            # find lineup for friends
            if name in self.vips:
                # if we found a VIP, add them to the VIP list
                self.logger.info("found VIP {}".format(name))
                self.vip_list.append(u)

            player_stats = row[7:]
            if player_stats:
                # continue if empty (sometimes happens on the player columns in the standings)
                if all('' == s or s.isspace() for s in player_stats):
                    continue

                name, pos, perc, fpts = player_stats
                name = strip_accents(name)

                for i, player in enumerate(player_list):
                    if name == player.name:
                        self.logger.debug(
                            "name {} MATCHES player.name {}!".format(name, player.name))
                        player.update_stats(pos, perc, fpts)
                        # update player list
                        self.complete_players.append(player)
                        del(player_list[i])
                        break
                    # else:
                    #     self.logger.debug(
                    #         "name {} DOES NOT MATCH player.name {}!".format(name, player.name))

                # for i, player in enumerate(self.players):
                #     if name == player.name:
                #         self.logger.debug(
                #             "name {} MATCHES player.name {}!".format(name, player.name))
                #         player.update_stats(pos, perc, fpts)
                #         # update player list
                #         self.players[i] = player
                #         self.logger.info(self.players[i])
                #         break
                #     else:
                #         self.logger.debug(
                #             "name {} DOES NOT MATCH player.name {}!".format(name, player.name))

    def load_standings(self, fn):
        with open(fn, 'rb') as csvfile:
            lines = io.TextIOWrapper(csvfile, encoding='utf-8', newline='\r\n')
            rdr = csv.reader(lines, delimiter=',')
            return list(rdr)


if __name__ == "__main__":
    """Use contest ID to update Google Sheet with DFS results.

    Example export CSV/ZIP link
    https://www.draftkings.com/contest/exportfullstandingscsv/62753724

    Example salary CSV link
    https://www.draftkings.com/lineup/getavailableplayerscsv?contestTypeId=70&draftGroupId=22401
    12 = MLB 21 = NFL 9 = PGA 24 = NASCAR 10 = Soccer 13 = MMA
    """

    # parse arguments
    parser = argparse.ArgumentParser()
    choices = ['NBA', 'NFL', 'CFB', 'PGAMain',
               'PGAWeekend', 'PGAShowdown', 'NHL', 'MLB', 'TEN']
    parser.add_argument('-i', '--id', type=int, required=True,
                        help='Contest ID from DraftKings',)
    parser.add_argument('-c', '--csv', help='Slate CSV from DraftKings',)
    parser.add_argument('-s', '--sport', choices=choices,
                        required=True, help='Type of contest (NBA, NFL, PGA, CFB, NHL, or MLB)')
    parser.add_argument('-v', '--verbose', help='Increase verbosity')
    args = parser.parse_args()

    now = datetime.datetime.now()

    Results(args.sport, args.id, args.csv)
