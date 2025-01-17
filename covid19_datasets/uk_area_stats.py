import pandas as pd
import numpy as np
import datetime
from .constants import DATE_COLUMN_NAME

import logging
_log = logging.getLogger(__name__)


UK_CASES_PATH = 'https://api.coronavirus.data.gov.uk/v2/data?areaType=TOREPLACE&metric=cumCasesBySpecimenDate&metric=newCasesBySpecimenDate&metric=cumCasesBySpecimenDateRate&format=csv' # New link as of 29/4/21
ENGLAND_DEATHS_PATH = 'https://c19downloads.azureedge.net/downloads/csv/coronavirus-deaths_latest.csv'  # TODO: This has been deprecated, update to new dashboard source

SCOTLAND_PATH = 'https://raw.githubusercontent.com/DataScienceScotland/COVID-19-Management-Information/master/export/health-boards/cumulative-cases.csv'

def _backfill_missing_data(df):
    """
    Datasets might have some dates missing if there were no cases reported on these dates
    Backfill them with 0
    """
    # if there are NaNs, replace them with 0
    df = df.fillna(0.0)

    # Some dates are missing as there were no numbers reported
    # backfill them with 0
    all_days = pd.date_range(df.columns.min(), df.columns.max(), freq='D')
    missing_days = np.setdiff1d(all_days, df.columns)
    for missing_day in missing_days:
        df[missing_day] = 0.0

    df = df[np.sort(df.columns)]

    return df


def _load_cases_dataset(area_type, country="England"):
    _log.info(f"Loading {country} dataset from " + UK_CASES_PATH)
    df = pd.read_csv(UK_CASES_PATH.replace("TOREPLACE", area_type))
    _log.info("Loaded")
    df = df[df["areaCode"].str.startswith(country[0])]  
    df[DATE_COLUMN_NAME] = pd.to_datetime(df["date"].astype(str))

    # Convert so that
    # Each row corresponds to an area
    # Each column corresponds to a date
    df['Daily lab-confirmed cases'] = df['newCasesBySpecimenDate'].astype('float')#
    df["Area name"] = df["areaName"]
    df['Country'] = country

    df = df.pivot_table(index=['Country', 'Area name'], columns=DATE_COLUMN_NAME,
                        values='Daily lab-confirmed cases')
    df = _backfill_missing_data(df)

    return df


def _load_scotland_cases_dataset():
    _log.info("Loading dataset from " + SCOTLAND_PATH)
    df = pd.read_csv(SCOTLAND_PATH, error_bad_lines=False)
    _log.info("Loaded")

    # downloaded file is (dates x areas), and we want the opposite
    df = df.transpose()

    # turn first row into a header
    new_header = df.iloc[0]
    df = df[1:]
    df.columns = pd.to_datetime(new_header.astype(str))
    df.columns.name = None

    df = df.replace('*', 0.0).astype(float)

    # original has cumulative data, and we want new cases per day
    for i in range(len(df.columns) - 1, 1, -1):
        df.iloc[:, i] = df.iloc[:, i] - df.iloc[:, i-1]

    # set multi index by country and area
    df['Country'] = 'Scotland'
    df = df.reset_index().rename(columns={'index': 'Area name'}).set_index(['Country', 'Area name'])

    return df


class UKCovid19Data:
    """
    Provides COVID-19 data for various parts of the UK
    """
    
    england_cases_data = None
    wales_cases_data = None
    wales_tests_data = None
    scotland_cases_data = None
    ENGLAND_UPPER_TIER_AUTHORITY = 'utla'
    ENGLAND_LOWER_TIER_AUTHORITY = 'ltla'

    def __init__(self, force_load=False, england_area_type=ENGLAND_UPPER_TIER_AUTHORITY):
        """
        Loads datasets and store them in memory.
        Further instances of this class will reuse the same data

        :param force_load: If true, forces download of the dataset, even if it was loaded already
        """
        if UKCovid19Data.england_cases_data is None or force_load or UKCovid19Data.england_area_type != england_area_type:
            UKCovid19Data.england_area_type = england_area_type
            UKCovid19Data.england_cases_data = _load_cases_dataset(england_area_type)

        if UKCovid19Data.wales_cases_data is None or UKCovid19Data.wales_tests_data is None or force_load:
            UKCovid19Data.wales_cases_data = _load_cases_dataset(england_area_type, "Wales")

        if UKCovid19Data.scotland_cases_data is None or force_load:
            UKCovid19Data.scotland_cases_data = _load_scotland_cases_dataset()

    def get_cases_data(self):
        """
        Returns the dataset as Pandas dataframe

        Format:
        - Row index: Country (England, Wales or Scotland), Area name
        - Columns: Dates
        - Each cell value is a number of new cases registered on that day

        Note: Scotland provides data by NHS Board, not by county
        """
        df = pd.concat([UKCovid19Data.england_cases_data, UKCovid19Data.wales_cases_data, UKCovid19Data.scotland_cases_data])
        # in case they have uneven number of columns
        df = df.fillna(0.0)

        return df

