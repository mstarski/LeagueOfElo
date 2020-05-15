from .team import *

class EloRatingSystem(object):
    """Elo Rating System for a single league"""
    def __init__(self, league, teamfile, K=20):
        self.league_name = league
        self.K = K
        self.teams = {}
        with open(teamfile, 'r') as teams:
            for team in teams:
                self._addTeam(team)
        self.alignment = [0]
        self.season_boundary = []
        self.brier_scores = []

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

    def loadGames(self, results, align=False):
        for result in results:
            t1, t2, t1s, t2s = result
            if not t1s:
                continue
            winloss_args = ((t1, t2, int(t1s), int(t2s)) if
                            int(t1s) > int(t2s) else
                            (t2, t1, int(t2s), int(t1s)))
            self._adjustRating(*winloss_args)
            if align:
                self._align()

    def loadRosters(self, rosters):
        pass

    def newSeasonReset(self):
        self._align()
        for _, team in self.teams.items():
            if not team.inactive:
                team.team_rating = team.getRating()*0.75 + 1500*0.25
            team.rating_history.append([team.getRating()])

    def predict(self, team1, team2):
        win_prob = self._getWinProb(self._getTeam(team1), self._getTeam(team2))
        if win_prob < 0.5:
            team1, team2 = team2, team1
            win_prob = 1 - win_prob
        print(f"{team1} {int(win_prob*100)}% over {team2}")

    def printStats(self):
        print(self._getBrier())
        print(self.getActiveTeamsRatings())
        data, colors = self._exportData()
        #EloPlotter.matplotlib_plot(self.league_name, data, colors)
        EloPlotter.plotly_plot(self.league_name, data, colors)

## Private
    def _addTeam(self, team):
        team_info = list(map(str.strip, team.split(',')))
        try:
            existing_team = self._getTeam(team_id=team_info[0])
        except ValueError:
            self.teams[team_info[2]] = Team(*team_info)
        else:
            existing_team.names.extend([team_info[2], team_info[1]])

    def _getTeam(self, team_name=None, team_id=None):
        team = self.teams.get(team_name)
        if not team:
            for _, t in self.teams.items():
                if team_name in t.names or team_id == t.team_id:
                    team = t
                    break
        if not team:
            raise ValueError(f"Team does not exist: {team_name}")
        return team

    def _getWinProb(self, team1, team2):
        """
        Get the probability that team1 will beat team2.
        @return win probability between 0 and 1.
        """
        rating_diff = team1.getRating() - team2.getRating()
        win_prob = 1 / (10**(-rating_diff/400) + 1)
        return win_prob

    def _getMatchScoreMultiplier(self, winner_score, loser_score):
        """
        Get a modifier value to scale rating adjustments with respect to match score.
        """
        w, l = winner_score, loser_score
        multiplier = ((w-l)*w/(w+l))**0.7
        return multiplier

    def _adjustRating(self, winner, loser, winner_score, loser_score):
        """
        Adjust the model's understanding of two teams based on the outcome of a
        match between the two teams.
        """
        winning_team, losing_team = self._getTeam(winner), self._getTeam(loser)
        forecast_delta = 1 - self._getWinProb(winning_team, losing_team)
        match_score_mult = self._getMatchScoreMultiplier(winner_score, loser_score)
        winning_team.updateRating(self.K * forecast_delta * match_score_mult)
        losing_team.updateRating(self.K * -forecast_delta * match_score_mult)
        self.brier_scores.append(forecast_delta**2)

    def _align(self):
        max_games = max([len(self.teams[team].rating_history[-1]) for team in self.teams])
        for _, team in self.teams.items():
            if len(set(team.rating_history[-1])) == 1:
                team.inactive = True
            else:
                team.inactive = False
            game_diff = max_games - len(team.rating_history[-1])
            team.rating_history[-1].extend([team.getRating()] * game_diff)

    def _getBrier(self):
        brier = sum(self.brier_scores)/len(self.brier_scores)
        return f"Brier Score: {brier:.4f}"

    def _exportData(self):
        data = {}
        colors = {}
        for _, team in sorted(self.teams.items(), key=lambda item: item[1].getRating(), reverse=True):
            abbrev = team.abbrev
            colors[abbrev] = team.color
            data[abbrev] = team.rating_history
        return data, colors


class PlayerEloRatingSystem(EloRatingSystem):
    """docstring for PlayerEloRatingSystem"""
    def __init__(self, league, teamfile, K=20):
        super(PlayerEloRatingSystem, self).__init__(league, teamfile, K)
        self.all_players = {}

## Public
    def loadRosters(self, rosters):
        for team_roster in rosters:
            team = self._getTeam(team_roster[0])
            team.clearRoster()
            for player in team_roster[1]:
                role, player_name = player
                if role not in ['Top Laner', 'Jungler', 'Mid Laner', 'Bot Laner', 'Support']:
                    continue
                player_obj = self.all_players.get(player_name)
                if not player_obj:
                    player_obj = Player(player_name)
                self.all_players[player_name] = player_obj
                team.addPlayer(role, player_obj)

    def getPlayerRatings(self):
        player_table = []
        for _, player in self.all_players.items():
            player_table.append((player.getRating(), f"{player.name:>25}  {int(player.getRating())}\n"))
        player_table.sort(key=lambda tup: tup[0], reverse=True)
        table_str = "{} Elo Ratings\n".format(self.league_name)
        for row in player_table:
            table_str += row[1]
        return table_str

    def newSeasonReset(self):
        self._align()
        for _, team in self.teams.items():
            team.rating_history.append([team.getRating()])

    def printStats(self):
        print(self._getBrier())
        print(self.getPlayerRatings())
        data, colors = self._exportData()
        EloPlotter.matplotlib_plot(self.league_name, data, colors)

## Private
    def _addTeam(self, team):
        team_info = list(map(str.strip, team.split(',')))
        try:
            existing_team = self._getTeam(team_id=team_info[0])
        except ValueError:
            self.teams[team_info[2]] = PlayerTeam(*team_info)
        else:
            existing_team.names.extend([team_info[2], team_info[1]])

    def _align(self):
        max_games = max([len(self.all_players[player].rating_history[-1]) for player in self.all_players])
        for _, player in self.all_players.items():
            if len(set(player.rating_history[-1])) == 1:
                player.inactive = True
            else:
                player.inactive = False
            game_diff = max_games - len(player.rating_history[-1])
            player.rating_history[-1].extend([player.getRating()] * game_diff)
        for _, team in self.teams.items():
            if len(set(team.rating_history[-1])) == 1:
                team.inactive = True
            else:
                team.inactive = False
            game_diff = max_games - len(team.rating_history[-1])
            team.rating_history[-1].extend([team.team_rating] * game_diff)

    def _exportData(self):
        data = {}
        colors = {}
        for player in self.all_players:
            name = self.all_players[player].name
            colors[name] = "#000000"
            data[name] = self.all_players[player].rating_history
        return data, colors


class EloPlotter(object):
    """Plots elo over time"""
    @staticmethod
    def matplotlib_plot(league, data, colors):
        import matplotlib.pyplot as plt
        import matplotlib.ticker as ticker
        import matplotlib.patheffects as path_effects

        fig, ax = plt.subplots(figsize=(15, 5))
        plt.subplots_adjust(left=0.05, right=0.95)
        ax.spines['top'].set_visible(False)
        ax.spines['bottom'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_visible(False)
        ax.xaxis.set_major_locator(ticker.MultipleLocator(10))
        plt.tick_params(axis='both', which='both', bottom=False, top=False,
                labelbottom=False, left=False, right=False, labelleft=True)
        plt.grid(True, 'major', 'y', ls='--', lw=.5, c='k', alpha=.3)
        plt.title(f"{league} Elo Ratings")

        label_positions = []
        end_idx = 0
        for team in data:
            team_data = data[team]
            start_idx = 0
            for split_data in team_data:
                end_idx = start_idx + len(split_data) - 1
                plt.axvline(x=end_idx, color='k', linewidth=1)
                x_series = list(range(start_idx, end_idx+1))
                start_idx = end_idx
                if len(set(split_data)) != 1:
                    plt.plot(x_series, split_data, colors[team])
            if len(set(team_data[-1])) != 1:
                label_positions.append((team_data[-1][-1], team))

        def distribute_labels(label_positions):
            from statistics import median
            median = median([val[0] for val in label_positions])
            label_positions.sort(key=lambda tup: abs(median-tup[0]))
            used_min = 9999
            used_max = 0
            adjusted_positions = []
            for item in label_positions:
                score = item[0]
                if score > used_max or score < used_min:
                    adjusted_positions.append(item)
                    used_max = max(used_max, score+15)
                    used_min = min(used_min, score-15)
                else:
                    if used_max - score < score - used_min:
                        adjusted_positions.append((used_max+1, item[1]))
                        used_max += 16
                    else:
                        adjusted_positions.append((used_min-1, item[1]))
                        used_min -= 16
            return adjusted_positions

        adjusted_positions = distribute_labels(label_positions)
        for team in adjusted_positions:
            text = plt.text(end_idx+1, team[0], team[1], color=colors[team[1]], weight='bold')
        plt.show()

    @staticmethod
    def plotly_plot(league, data, colors):
        import plotly.graph_objects as go
        import plotly.io as pio

        x = list(range(1,16))
        fig = go.Figure()
        for team in data:
            team_data = sum(data[team], [])
            for i, d in enumerate(team_data):
                if d == 1500 and team_data[i+1] == 1500:
                    team_data[i] = None
                else:
                    break
            x_series = list(range(0, len(team_data)))
            fig.add_trace(go.Scatter(
                x=x_series,
                y=team_data,
                name=f'{team}: {int(team_data[-1])}',
                text=team,
                hoverinfo='text+x+y',
                line={'color':colors[team]}))

        # Draw split boundaries
        split_bound = -1
        for split in data[list(data.keys())[0]]:
            split_bound += len(split)
            fig.add_shape(
                type="rect",
                xref="x",
                yref="paper",
                x0=split_bound,
                y0=0,
                x1=split_bound+1,
                y1=1,
                fillcolor="DarkGray",
                opacity=0.5,
                layer="above",
                line_width=0)

        pio.write_html(fig, file=f'../www/{league}_elo.html', auto_open=True)
