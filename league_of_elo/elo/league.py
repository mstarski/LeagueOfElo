from .team import *
from .rating_system import RatingSystem
from statistics import mean
import re


class League(object):
    """League class manages teams and historical ratings"""
    def __init__(self, league_name:str, rating_system:RatingSystem):
        self.league_name = league_name
        self.rating_system = rating_system
        self.teams = {}
        self.teams_by_region = {}
        self.alignment = [0]
        self.season_boundary = []
        self.seasons = []

    def __repr__(self):
        team_table = []
        for _, team in self.teams.items():
            team_table.append((team.getRating(), f"  {team.abbrev:>3}  {int(team.getRating())}\n"))
        team_table.sort(key=lambda tup: tup[0], reverse=True)
        table_str = "{} Elo Ratings\n".format(self.league_name)
        for row in team_table:
            table_str += row[1]
        return table_str

## Public
    def getActiveTeamsRatings(self):
        team_table = []
        for _, team in self.teams.items():
            if team.inactive:
                continue
            team_table.append((team.getRating(), f"  {team.abbrev:>3}  {int(team.getRating())}\n"))
        team_table.sort(key=lambda tup: tup[0], reverse=True)
        table_str = "{} Elo Ratings\n".format(self.league_name)
        for row in team_table:
            table_str += row[1]
        return table_str

    def loadTeams(self, teamfile, region):
        self.teams_by_region[region] = []
        with open(teamfile, 'r') as teams:
            for team in teams:
                team_info = Team.info(*list(map(str.strip, team.split(','))))
                self._addTeam(team_info, region)

    def loadGames(self, results, playoffs=False, using_ids=False):
        for result in results:
            t1, t2, t1s, t2s, date, best_of, match_round = result
            if not t1s or not match_round:
                continue
            try:
                if using_ids:
                    t1 = self._getTeam(team_id=t1)
                    t2 = self._getTeam(team_id=t2)
                else:
                    t1 = self._getTeam(team_name=t1)
                    t2 = self._getTeam(team_name=t2)
            except ValueError:
                # print(f"Unknown team. Ignoring match. {t1}, {t2}")
                continue

            winloss_args = (t1.getRating(), t2.getRating(), int(t1s), int(t2s))
            t1_updated, t2_updated = self.rating_system.process_outcome(*winloss_args)
            t1.updateRating(t1_updated)
            t2.updateRating(t2_updated)

    def loadRosters(self, rosters):
        pass

    def newSeasonReset(self, season_name, rating_reset=None):
        try:
            self.seasons.append(season_name[re.search(r'\d\d\d\d', season_name).start():])
        except:
            self.seasons.append(season_name)
        self._align()
        for region, teams in self.teams_by_region.items():
            regional_avg = self._getRegionalAverage(region)
            for t in teams:
                team = self._getTeam(team_id=t)
                if rating_reset:
                    team.team_rating = team.getRating()*0.75 + regional_avg*0.25
                team.rating_history.append([team.getRating()])

    def printStats(self):
        print(self.rating_system.getBrier())
        print(self.rating_system.getUpDown())

    def genResult(self):
        self._align()

        data, colors, seasons = self._exportData()
        result = {}

        for team, rating_hist in data.items():
            end_rating = rating_hist[-1][-1]
            full_name = self._getNameFromAbbrev(team)
            result[full_name] = {}
            result[full_name]['rating'] = end_rating
            result[full_name]['abbrev'] = team 
        
        return result


    ## Private
    def _addTeam(self, team_info, region='Default'):
        try:
            existing_team = self._getTeam(team_id=team_info.id)
        except ValueError:
            self.teams_by_region[region].append(team_info.id)
            self.teams[team_info.id] = Team(*team_info)
        else:
            existing_team.names.extend([team_info.name, team_info.abbrev])

    def _getNameFromAbbrev(self, abbrev):
        for id in self.teams:
            if self.teams[id].abbrev == abbrev:
                return self.teams[id].name

    def _getTeam(self, team_name=None, team_id=None, default=None):
        team = self.teams.get(team_name)
        if not team:
            for _, t in self.teams.items():
                if team_name in t.names or team_id == t.team_id:
                    team = t
                    break
        if not team:
            if not default:
                raise ValueError(f'Team does not exist: {team_name}')
            else:
                print(f"Using dummy team instead of {team_name}")
                team = default
        return team

    def _align(self):
        max_games = max([len(self.teams[team].rating_history[-1]) for team in self.teams])
        for _, team in self.teams.items():
            if len(set(team.rating_history[-1])) == 1:
                team.inactive = True
            else:
                team.inactive = False
            game_diff = max_games - len(team.rating_history[-1])
            team.rating_history[-1].extend([team.getRating()] * game_diff)

    def _getRegionalAverage(self, region):
        ratings = [self._getTeam(t).getRating() for t in self.teams_by_region[region]]
        return mean(ratings)

    def _exportData(self):
        data = {}
        inactive = {}
        colors = {}

        for _, team in sorted(self.teams.items(), key=lambda item: item[1].getRating()):
            abbrev = team.abbrev
            colors[abbrev] = team.color
            if team.inactive:
                inactive[abbrev] = team.rating_history
            else:
                data[abbrev] = team.rating_history
        data.update(inactive)
        return data, colors, self.seasons