#!/usr/bin/env python3

from .elo import league, rating_system
from .get_league_data import Leaguepedia_DB

from typing import Dict
from time import strftime
from pathlib import Path
import argparse
import re
import pickle
import os


SRC_PATH = Path(__file__).resolve().parent
CFG_PATH = Path(SRC_PATH / 'cfg')
DOCS_PATH = Path(SRC_PATH / '..' / 'docs')
CACHE_PATH = Path(SRC_PATH / '..' / 'cache')

TEAMFILES = {
    'NA': ('LCS_teams.csv', 2015),
    'EU': ('LEC_teams.csv', 2015),
    'KR': ('LCK_teams.csv', 2015),
    'CN': ('LPL_teams.csv', 2015),
    'INT': ('INT_teams.csv', 2015),
}
IGNORE_TOURNAMENTS = [
    'Promotion',
    'Play-In',
    'Rift Rivals',
    'EU Face-Off',
    'Mid-Season Showdown 2020',
    'IWCT']


class DataCache():
    def __init__(self, regen=False):
        self.lpdb = None
        self.force_lpdb = regen

    def lpdb_connect(self):
        self.lpdb = Leaguepedia_DB()

    def getTournaments(self, regions, start_year, stop_date):
        if not self.lpdb:
            self.lpdb_connect()
        season_list = self.lpdb.getTournaments(regions, start_year, stop_date)
        season_list = [tname for tname, tdate in season_list]
        season_list = list(filter(lambda x: all([t not in x for t in IGNORE_TOURNAMENTS]), season_list))
        return season_list

    def getMatchResults(self, season, force_fetch=False):
        results_file = Path(CACHE_PATH / 'results' / f'{season}.p')
        os.makedirs(os.path.dirname(results_file), exist_ok=True)

        if results_file.is_file() and not force_fetch:
            results = pickle.load(open(results_file, 'rb'))
            # print(f'Using cached: {season}')
        else:
            # print(f'Fetching: {season}')
            if not self.lpdb:
                self.lpdb_connect()
            results = self.lpdb.getSeasonResults(season)
            pickle.dump(results, open(results_file, 'wb'))
        return results


def runMultiRegion(region, model = rating_system.Elo, stop_date = strftime('%Y-%m-%d')):
    regions = ['NA', 'EU', 'KR', 'CN', 'INT'] if region == 'INT' else [region]
    start_year = 2010
    rating_model = model()
    rating_league = league.League('_'.join(regions), rating_model)
    for region in regions:
        teamfile, region_start_year = TEAMFILES.get(region)
        start_year = max(start_year, region_start_year)
        rating_league.loadTeams(CFG_PATH / teamfile, region)

    cache = DataCache()
    season_list = cache.getTournaments(regions, start_year, stop_date)

    split = None
    split_transitions = []

    for season in season_list:
        # Declare new season when split transitions between any of the following
        new_split = re.search('(Spring|Summer|MSI|Worlds|Mid-Season Cup|Lock In)', season)
        if new_split and new_split[0] != split:
            split = new_split[0]
            split_transitions.append(season)

    year = None
    last_year = None
    split = None
    force_fetch = False

    for season in season_list:
        # Declare new season when split transitions between any of the following
        if season in split_transitions:
            year = re.search(r'\d\d\d\d', season)[0]
            split = re.search(r'(Spring|Summer|MSI|Worlds|Mid-Season Cup|Lock In)', season)[0]
            # print(f'{year} {split}')
            if year != last_year or split == 'Summer':
                rating_league.newSeasonReset(f'{year} {split}', rating_reset=True)
            else:
                rating_league.newSeasonReset(split, rating_reset=False)
            if season == split_transitions[-1]:
                force_fetch = True
            last_year = year
        results = cache.getMatchResults(season, force_fetch=force_fetch)
        rating_league.loadGames(results, 'Playoffs' in season)

    result = rating_league.genResult()
    # print(result)
    return result


def parseArgs() -> Dict:
    parser = argparse.ArgumentParser()
    parser.add_argument('region', choices=['NA', 'EU', 'KR', 'CN', 'INT', 'ALL'], default='INT',
                        help='Region to run the model on.', nargs='?')
    parser.add_argument('stop_date', nargs='?', type=str, default=strftime('%Y-%m-%d'),
                        help='Date to stop processing data in YYYY-MM-DD format. Defaults to current day.')
    parser.add_argument('--naive_model', dest='model', action='store_const',
                        const=rating_system.Naive, default=rating_system.Elo,
                        help='Use the naive rating system rather than Elo')

    return vars(parser.parse_args())


if __name__ == '__main__':
    args = parseArgs()

    print(args)

    if args['region'] == 'ALL':
        for region in TEAMFILES:
            # print(f'Running {region}')
            args['region'] = region
            runMultiRegion(**args)
    else:
        runMultiRegion(**args)
