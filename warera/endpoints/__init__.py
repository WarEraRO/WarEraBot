"""Endpoint groups of `WarEraClient`, one class per area of the game."""
from warera.endpoints.battles import BattlesAPI, ContractsAPI, TournamentsAPI
from warera.endpoints.companies import CompaniesAPI
from warera.endpoints.countries import CountriesAPI, RegionsAPI
from warera.endpoints.game import GameAPI
from warera.endpoints.market import MarketAPI
from warera.endpoints.military_units import MilitaryUnitsAPI
from warera.endpoints.users import UsersAPI

__all__ = ['BattlesAPI', 'CompaniesAPI', 'ContractsAPI', 'CountriesAPI', 'GameAPI', 'MarketAPI', 'MilitaryUnitsAPI',
           'RegionsAPI', 'TournamentsAPI', 'UsersAPI']
