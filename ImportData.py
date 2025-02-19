import os
import pandas as pd
import csv
import configparser
from ConfigurationClass import Configuration
from BondClasses import CorpBond
from EquityClasses import EquityShare
from SettingsClasses import Settings
from datetime import datetime
from CashClass import Cash
from LiabilityClasses import Liability


def get_configuration(ini_file: str, op_sys, config_parser=configparser.ConfigParser()) -> Configuration:
    """

    :rtype: object
    """
    configuration = Configuration()
    config_parser.read(ini_file)

    if "BASE" in config_parser:
        configuration.base_folder = config_parser["BASE"]["base_folder"]
    else:
        configuration.base_folder = op_sys.getcwd()

    if "TRACE" in config_parser:
        configuration.trace_enabled = bool(config_parser["TRACE"]["enabled"])
    else:
        configuration.trace_enabled = False

    if "INTERMEDIATE" in config_parser:
        intermediate = config_parser["INTERMEDIATE"]
        configuration.intermediate_enabled = bool(intermediate["enabled"])
        intermediate_path = os.path.join(configuration.base_folder, intermediate["file_path"])
        configuration.intermediate_path = intermediate_path
        configuration.intermediate_cash_portfolio = op_sys.path.join(intermediate_path,
                                                                     intermediate["cash_portfolio_file"])
        configuration.intermediate_equity_portfolio_file = op_sys.path.join(intermediate_path,
                                                                            intermediate["equity_portfolio_file"])

    else:
        configuration.intermediate_enabled = False

    if "INPUT" in config_parser:
        inp = config_parser["INPUT"]
        input_path = os.path.join(configuration.base_folder, inp["file_path"])
        configuration.input_path = input_path
        configuration.input_bond_portfolio = op_sys.path.join(input_path, inp["bonds"])
        configuration.input_cash_portfolio = op_sys.path.join(input_path, inp["cash"])
        configuration.input_curves = op_sys.path.join(input_path, inp["curves"])
        configuration.input_equity_portfolio = op_sys.path.join(input_path, inp["equities"])
        configuration.input_param_no_VA = op_sys.path.join(input_path, inp["param_no_VA"])
        configuration.input_spread = op_sys.path.join(input_path, inp["sector_spread"])
        configuration.input_parameters = op_sys.path.join(input_path, inp["parameters"])
        configuration.input_liability_cashflow = op_sys.path.join(input_path,
                                                                         inp["liability"])
    return configuration


def import_SWEiopa(selected_param_file, selected_curves_file, country):
    param_raw = pd.read_csv(selected_param_file, sep=",", index_col=0)
    maturities_country_raw = param_raw.loc[:, country + "_Maturities"].iloc[6:]
    param_country_raw = param_raw.loc[:, country + "_Values"].iloc[6:]
    extra_param = param_raw.loc[:, country + "_Values"].iloc[:6]
    relevant_positions = pd.notna(maturities_country_raw.values)
    maturities_country = maturities_country_raw.iloc[relevant_positions]
    Qb = param_country_raw.iloc[relevant_positions]
    curve_raw = pd.read_csv(selected_curves_file, sep=",", index_col=0)
    curve_country = curve_raw.loc[:, country]
    return [maturities_country, curve_country, extra_param, Qb]


def get_corporate_bonds(filename: str) -> CorpBond:
    with open(filename, mode="r", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            corp_bond = CorpBond(asset_id=int(row["Asset_ID"]),
                                 nace=row["NACE"],
                                 issuer=None,
                                 issue_date=datetime.strptime(row["Issue_Date"], "%d/%m/%Y").date(),
                                 maturity_date=datetime.strptime(row["Maturity_Date"], "%d/%m/%Y").date(),
                                 coupon_rate=float(row["Coupon_Rate"]),
                                 notional_amount=float(row["Notional_Amount"]),
                                 frequency=int(row["Frequency"]),
                                 recovery_rate=float(row["Recovery_Rate"]),
                                 default_probability=float(row["Default_Probability"]),
                                 market_price=float(row["Market_Price"]))
            yield corp_bond


def get_EquityShare(filename: str):
    """
    :type filename: str
    """

    with open(filename, mode="r", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            equity_share = EquityShare(asset_id=int(row["Asset_ID"]),
                                       nace=row["NACE"],
                                       issuer=None,
                                       issue_date=datetime.strptime(row["Issue_Date"], "%d/%m/%Y").date(),
                                       dividend_yield=float(row["Dividend_Yield"]),
                                       frequency=int(row["Frequency"]),
                                       market_price=float(row["Market_Price"]),
                                       growth_rate=float(row["Growth_Rate"]))
            yield equity_share


def get_Cash(filename: str) -> Cash:
    """
    :type filename: str
    """

    with open(filename, mode="r", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            cash = Cash(asset_id=int(row["Asset_ID"]),
                        bank_account=float(row["Bank_Account"]))
    return cash


def get_Liability(filename: str) -> Liability:
    """
    :type filename: str
    """
    liability_id = 1  # To Remove and abstract away
    with open(filename, mode="r", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file)
        cash_flow_series = []
        cash_flow_date = []
        for row in reader:
            cash_flow_date.append(datetime.strptime(row["Liability_Date"], '%d/%m/%Y').date())
            cash_flow_series.append(float(row["Liability_Size"]))
        liabilities = Liability(liability_id=liability_id, cash_flow_dates=cash_flow_date,
                                cash_flow_series=cash_flow_series)
        return liabilities


def get_settings(filename: str) -> Settings:
    """
    :type filename: str
    """
    with open(filename, mode="r", encoding="utf-8-sig") as csvfile:
        read_dict = {}
        reader = csv.DictReader(csvfile)
        for row in reader:
            read_dict[row["Parameter"]] = row["Value"]

        setting = Settings(EIOPA_param_file=read_dict["EIOPA_param_file"],
                           EIOPA_curves_file=read_dict["EIOPA_curves_file"],
                           country=read_dict["country"],
                           run_type=read_dict["run_type"],
                           n_proj_years=int(read_dict["n_proj_years"]),
                           precision=float(read_dict["Precision"]),
                           tau=float(read_dict["Tau"]),
                           compounding=int(read_dict["compounding"]),
                           modelling_date=datetime.strptime(read_dict["Modelling_Date"], '%d/%m/%Y').date())

        return setting
