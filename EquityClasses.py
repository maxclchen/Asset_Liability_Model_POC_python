from typing import List
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import date
from dataclasses import dataclass
from dateutil.relativedelta import relativedelta
from FrequencyClass import Frequency
from TraceClass import Trace, tracer


@dataclass
class EquityShare:
    asset_id: int
    nace: str
    issuer: str
    issue_date: date
    dividend_yield: float
    frequency: Frequency
    market_price: float
    growth_rate: float

    # @property Look into what property does
    @tracer
    def dividend_amount(self, current_market_price: float) -> float:
        out = current_market_price * self.dividend_yield
        return out

    @tracer
    def terminal_amount(self, market_price: float, growth_rate: float, terminal_rate: float) -> float:
        return market_price / (terminal_rate - growth_rate)

    @tracer
    def generate_market_value(self, modelling_date: date, evaluated_date: date, market_price: float,
                              growth_rate: float):
        t = (evaluated_date - modelling_date).days / 365.5
        return market_price * (1 + growth_rate) ** t

    @tracer
    def generate_dividend_dates(self, modelling_date: date, end_date: date) -> date:
        """
        Generator yielding the dividend payment date starting from the first dividend
        paid after the modelling date. 
        
        :type modelling_date: date
        :type end_date: date
        
        """
        delta = relativedelta(months=(12 // self.frequency))
        this_date = self.issue_date - delta
        while this_date < end_date:  # Coupon payment dates
            this_date = this_date + delta
            if this_date < modelling_date:  # Not interested in past payments
                continue
            if this_date <= end_date:
                yield this_date  # ? What is the advantage of yield here?


class EquitySharePortfolio():
    def __init__(self, equity_share: dict[int, EquityShare] = None):
        """
        Initialize the EquitySharePortfolio instance with the first EquityShare instance

        Parameters
        ----------        
        :type equity_share: dict[int,EquityShare]
        """
        self.equity_share = equity_share

    def IsEmpty(self) -> bool:
        if self.equity_share is None:
            return True
        if len(self.equity_share) == 0:
            return True
        return False

    def add(self, equity_share: EquityShare):
        """
        Add a new EquityShare to the EquitySharePortfolio instance

        Parameters
        ----------
        self: EquitySharePortfolio class instance
            The EquitySharePortfolio instance with populated initial portfolio.
        :type equity_share: EquityShare
            The EquityShare instance representing a single equity instrument.

        """
        if self.equity_share is None:
            self.equity_share = {equity_share.asset_id: equity_share}
        else:
            self.equity_share.update({equity_share.asset_id: equity_share})

    def create_dividend_dates(self, modelling_date: date, end_date: date) -> list:
        """
        Create the list of dictionaries containing dates at which the dividends are paid out and the total amounts for
        all equity shares in the portfolio, for dates on or after the modelling date but not after the terminal date.

        Parameters
        ----------
        self: EquitySharePortfolio class instance
            The EquitySharePortfolio instance with populated initial portfolio.
        :type modelling_date: datetime.date
            The date from which the dividend dates and values start.
        :type end_date: datetime.date
            The last date that the model considers (end of the modelling window).

        Returns
        -------
        :rtype all_dividends
            A list of dictionaries with datetime keys and cash-flow size values, containing all the dates at which the coupons are paid out.
        """
        all_dividends = []
        dividends: dict[date, float] = {}
        equity_share: EquityShare
        dividend_date: date
        for asset_id in self.equity_share:
            equity_share = self.equity_share[asset_id]  # Select one asset position
            dividend_amount = 0
            dividends = {}
            for dividend_date in equity_share.generate_dividend_dates(modelling_date, end_date):
                if dividend_date in dividends:  # If two cash flows on same date
                    pass
                    # Do nothing since dividend amounts are calibrated afterwards for equity
                    # dividends[dividend_date] = dividend_amount + dividends[dividend_date] # ? Why is here a plus? (you agregate coupon amounts if same date?)
                else:  # New cash flow date
                    market_price = equity_share.generate_market_value(modelling_date, dividend_date,
                                                                      equity_share.market_price,
                                                                      equity_share.growth_rate)
                    dividend_amount = equity_share.dividend_amount(current_market_price=market_price)
                    dividends.update({dividend_date: dividend_amount})
            all_dividends.append(dividends)
        return all_dividends

    def create_terminal_dates(self, modelling_date: date, terminal_date: date, terminal_rate: float) -> list:
        """
        Create the list of dictionaries containing dates at which the terminal cash-flows are paid out and the total amounts for
        all equity shares in the portfolio, for dates on or after the modelling date but not after the terminal date.

        Parameters
        ----------
        self: EquitySharePortfolio class instance
            The EquitySharePortfolio instance with populated portfolio.
        :type modelling_date: datetime.date
            The date from which the terminal dates and market values start.
        :type end_date: datetime.date
            The last date that the model considers (end of the modelling window).
        :type terminal_rate: float
            The assumed ultimate forward rate. The long term interest rate used in the Gordon growth model to calculate the terminal cash-flow

        Returns
        -------
        :rtype all_terminals
            A list of dictionaries with datetime keys and cash-flow size values, containing all the dates at which the terminal cash-flows are paid out.
        """
        all_terminals = []
        terminals: dict[date, float] = {}
        equity_share: EquityShare
        terminal_date: date

        for asset_id in self.equity_share:
            terminals = {}
            equity_share = self.equity_share[asset_id]
            market_price = equity_share.generate_market_value(modelling_date, terminal_date, equity_share.market_price,
                                                              equity_share.growth_rate)
            terminal_amount = equity_share.terminal_amount(market_price, equity_share.growth_rate, terminal_rate)
            terminals.update({terminal_date: terminal_amount})
            all_terminals.append(terminals)
        return all_terminals

    def create_dividend_fractions(self, modelling_date: date, dividend_array: list) -> dict:
        """
        Create the list of year-fractions at which each dividend is paid out (compared to the modelling date) and the list of
        relevant indices (aka. indices of cash flows that are within the modelling period)

        Parameters
        ----------
        self: EquitySharePortfolio class instance
            The EquitySharePortfolio instance with populated portfolio.
        :type modelling_date: datetime.date
            The date from which the dividend fraction is calculated.
        :type dividend_array: list of dictionaries
            Each element of the list represents a single equity asset. Each element contains a dictionary where has keys as dates at which the dividend cash flows are paid out
            and the values are the size of payment amount in local currency
            
        Returns
        -------
        :rtype dict Array with two elements: 
            all_dividend_date_frac: A list of numpy arrays, Each element in the list represents a sigle asset. Each numpy array represents the time fraction
            between the modelling date and the date of the cash flow (ex. 18 months from modelling date is 1.5).
            all_dividend_dates_considered: list of numpy arrays. Each element in the list represents a single asset. Each numpy array represents the indices of
            the cash flows from the dividend_array that mature within the period between the modelling date and the terminal date.
        """


        # other counting conventions MISSING
        # Remove numpy arrays in construction

        # Data structures list of lists for dividend payments
        all_date_frac = ([])  # this will save the date fractions of dividends for the portfolio
        all_dates_considered = (
            [])  # this will save if a cash flow is already expired before the modelling date in the portfolio

        for one_dividend_array in dividend_array:
            # equity_share = self.equity_share[asset_id]
            #            one_dividend_array = dividend_array[asset_id]

            # Reset objects for the next asset
            equity_date_frac = np.array([])  # this will save date fractions of dividends of a single asset
            equity_dates_considered = np.array(
                [])  # this will save the boolean, if the dividend date is after the modelling date

            dividend_counter = 0  # Counter of future dividend cash flows initialized to 0

            for one_dividend_date in list(one_dividend_array.keys()):  # for each dividend date of the selected equity
                one_dividend_days = (one_dividend_date - modelling_date).days
                if one_dividend_days > 0:  # dividend date is after the modelling date
                    equity_date_frac = np.append(
                        equity_date_frac, one_dividend_days / 365.25
                    )  # append date fraction
                    equity_dates_considered = np.append(
                        equity_dates_considered, int(dividend_counter)
                    )  # append "is after modelling date" flag
                dividend_counter += 1
                # else skip
            all_date_frac.append(
                equity_date_frac
            )  # append what fraction of the date is each cash flow compared to the modelling date
            all_dates_considered.append(
                equity_dates_considered.astype(int)
            )  # append which cash flows are after the modelling date

        return [
            all_date_frac,
            all_dates_considered
        ]  # return all generated data structures (for now)

    def create_terminal_fractions(self, modelling_date: date, terminal_array: dict) -> dict:
        """
        Create the list of year-fractions at which the terminal amount is paid out (compared to the modelling date) and the list of
        relevant indices (aka. indices of cash flows that are within the modelling period)

        Parameters
        ----------
        self: EquitySharePortfolio class instance
            The EquitySharePortfolio instance with populated portfolio.
        :type modelling_date: datetime.date
            The date from which the terminal fraction is calculated.
        :type terminal_array: list of dictionaries
            Each element of the list represents a single equity asset. Each element contains a dictionary where keys are the dates at which the terminal cash flow is paid out
            and the values are the size of payment in local currency
            
        Returns
        -------
        :rtype dict Array with two elements: 
            all_terminal_date_frac: A list of numpy arrays, Each element in the list represents a sigle asset. Each numpy array represents the time fraction
            between the modelling date and the terminal date (ex. 18 months from modelling date is 1.5).
            all_terminal_dates_considered: list of numpy arrays. Each element in the list represents a single asset. Each numpy array represents the index of
            the cash flow from the terminal_array that matures within the period between the modelling date and the terminal date.
        """

        # other counting conventions MISSING
        # Remove numpy arrays in construction

        # Data structures list of lists for dividend payments
        all_terminal_date_frac = ([])  # this will save the date fractions of dividends for the portfolio
        all_terminal_dates_considered = (
            [])  # this will save if a cash flow is already expired before the modelling date in the portfolio

        for one_terminal_array in terminal_array:

            # Reset objects for the next asset
            equity_terminal_date_frac = np.array([])  # this will save date fractions of dividends of a single asset
            equity_terminal_dates_considered = np.array(
                [])  # this will save the boolean, if the dividend date is after the modelling date

            one_dividend_date = list(one_terminal_array.keys())[0]  # for each dividend date of the selected equity
            one_dividend_days = (one_dividend_date - modelling_date).days
            if one_dividend_days > 0:  # if terminal sale date is after modelling date
                equity_terminal_date_frac = np.append(
                    equity_terminal_date_frac, one_dividend_days / 365.25
                )  # append date fraction
                equity_terminal_dates_considered = np.append(
                    equity_terminal_dates_considered, int(1)
                )  # append "is after modelling date" flag
            # else skip
            all_terminal_date_frac.append(
                equity_terminal_date_frac
            )  # append what fraction of the date is each cash flow compared to the modelling date
            all_terminal_dates_considered.append(
                equity_terminal_dates_considered.astype(int)
            )  # append which cash flows are after the modelling date

        return [
            all_terminal_date_frac,
            all_terminal_dates_considered
        ]

    def unique_dates_profile(self, cashflow_profile: List):
        """
        Create a sorted list of dates at which there is an cash-flow event in any of the assets inside the portfolio and
        a single numpy array (matrix) representing those cash flows.


        Parameters
        ----------
        self: EquitySharePortfolio class instance
            The EquitySharePortfolio instance with populated portfolio.
        :type cashflow_profile: list of dictionaries containing the size and date of each 
            cash-flow for the equity portfolio

        :rtype dict list with two elements:
            unique_dates
            cash_flow_matrix
        """

        # define list of unique dates
        unique_dates = []
        for one_dividend_array in cashflow_profile:
            for one_dividend_date in list(one_dividend_array.keys()):  # for each dividend date of the selected equity
                if one_dividend_date in unique_dates:  # If two cash flows on same date
                    pass
                    # Do nothing since dividend amounts are calibrated afterwards for equity
                    # dividends[dividend_date] = dividend_amount + dividends[dividend_date] # ? Why is here a plus? (you agregate coupon amounts if same date?)
                else:  # New cash flow date
                    unique_dates.append(one_dividend_date)

        return sorted(unique_dates)

    def cash_flow_profile_list_to_matrix(self, cash_flow_profile: list) -> list:

        unique_dates = self.unique_dates_profile(cash_flow_profile)
        width = len(unique_dates)
        height = len(cash_flow_profile)

        cash_flow_matrix = np.zeros((height, width))
        row = 0
        for one_cash_flow_array in cash_flow_profile:
            count = 0
            values = list(one_cash_flow_array.values())
            for one_cash_flow in one_cash_flow_array:
                column = unique_dates.index(one_cash_flow)
                cash_flow_matrix[row, column] = values[count]
                count += 1
            row += 1
        return [
            unique_dates,
            cash_flow_matrix]

    def save_equity_matrices_to_csv(self, unique_dividend, unique_terminal, dividend_matrix, terminal_matrix, paths):

        filepath_1 = Path(paths.intermediate + 'unique_dividend_dates.csv')
        filepath_2 = Path(paths.intermediate + 'unique_terminal_dates.csv')
        filepath_3 = Path(paths.intermediate + 'cashflow_dividend_matrix.csv')
        filepath_4 = Path(paths.intermediate + 'cashflow_terminal_matrix.csv')

        filepath_1.parent.mkdir(parents=True, exist_ok=True)
        filepath_2.parent.mkdir(parents=True, exist_ok=True)
        filepath_3.parent.mkdir(parents=True, exist_ok=True)
        filepath_4.parent.mkdir(parents=True, exist_ok=True)

        pd.DataFrame(unique_dividend).to_csv(filepath_1)
        pd.DataFrame(unique_terminal).to_csv(filepath_2)
        pd.DataFrame(dividend_matrix).to_csv(filepath_3)
        pd.DataFrame(terminal_matrix).to_csv(filepath_4)

    def init_equity_portfolio_to_dataframe(self, modelling_date: date)->list:

        asset_keys = self.equity_share.keys()

        market_price_tmp = []
        growth_rate_tmp = []
        asset_id_tmp = []
        for key in asset_keys:
            market_price_tmp.append(self.equity_share[key].market_price)
            growth_rate_tmp.append(self.equity_share[key].growth_rate)
            asset_id_tmp.append(self.equity_share[key].asset_id)

        market_price = pd.DataFrame(data=market_price_tmp, index=asset_id_tmp, columns=[modelling_date])

        growth_rate = pd.DataFrame(data=growth_rate_tmp, index=asset_id_tmp, columns=[modelling_date])

        return [market_price, growth_rate]

    #    def create_terminal_cashflow(self, modelling_date: date, end_date: date) -> dict:
    #        """
    #        self : EquitySharePortfolio class instance
    #            The EquitySharePortfolio instance with populated initial portfolio.
    #        :type modelling_date: date
    #        :type end_date: date

    #        :rtype: dict
    #        """
    #        all_terminals = np.array([])
    #        terminals: dict[date, float] = {}
    #        equity_share: EquityShare
    #        terminal_date: date

    #        for asset_id in self.equity_share:
    #            equity_share = self.equity_share[asset_id]
    #
    #            terminal_amount = 0
    #            terminal_date = end_date
    #            if terminal_date in terminals:
    #                pass
    #                # Do nothing since dividend amounts are calibrated afterwards for equity
    #                #terminals[terminal_date] = terminal_amount + terminals[terminal_date]
    #            else:
    #                terminals.update({terminal_date:terminal_amount})
    #            all_terminals = np.append(all_terminals,np.array(terminals))
    #        return all_terminals

    # Calculate terminal value given growth rate, ultimate forward rate and vector of cash flows
    def equity_gordon(self, dividendyield, yieldrates, dividenddatefrac, ufr, g):

        num = np.power((1 + g), dividenddatefrac)
        den = np.power((1 + yieldrates), dividenddatefrac)
        termvalue = 1 / ((1 + yieldrates[-1]) ** dividenddatefrac[-1]) * 1 / (ufr - g)

        lhs = 1 / dividendyield
        return np.sum(num / den) + termvalue - lhs

    ## Bisection

    def bisection_spread(x_start, x_end, dividendyield, r_obs_est, dividenddatefrac, ufr, Precision, maxIter,
                         growth_func):
        """
        Bisection root finding algorithm for finding the root of a function. The function here is the allowed difference between the ultimate forward rate and the extrapolated curve using Smith & Wilson.

        Args:
            cbPriced =  CorporateBondPriced object containing the list of priced bonds, spreads and cash flows
            xStart =    1 x 1 floating number representing the minimum allowed value of the convergence speed parameter alpha. Ex. alpha = 0.05
            xEnd =      1 x 1 floating number representing the maximum allowed value of the convergence speed parameter alpha. Ex. alpha = 0.8
            M_Obs =     n x 1 ndarray of maturities of bonds, that have rates provided in input (r). Ex. u = [[1], [3]]
            r_Obs =     n x 1 ndarray of rates, for which you wish to calibrate the algorithm. Each rate belongs to an observable Zero-Coupon Bond with a known maturity. Ex. r = [[0.0024], [0.0034]]
            ufr  =      1 x 1 floating number, representing the ultimate forward rate. Ex. ufr = 0.042
            Tau =       1 x 1 floating number representing the allowed difference between ufr and actual curve. Ex. Tau = 0.00001
            Precision = 1 x 1 floating number representing the precision of the calculation. Higher the precision, more accurate the estimation of the root
            maxIter =   1 x 1 positive integer representing the maximum number of iterations allowed. This is to prevent an infinite loop in case the method does not converge to a solution         
            approx_function
        Returns:
            1 x 1 floating number representing the optimal value of the parameter alpha 

        Example of use:
            >>> import numpy as np
            >>> from SWCalibrate import SWCalibrate as SWCalibrate
            >>> M_Obs = np.transpose(np.array([1, 2, 4, 5, 6, 7]))
            >>> r_Obs =  np.transpose(np.array([0.01, 0.02, 0.03, 0.032, 0.035, 0.04]))
            >>> xStart = 0.05
            >>> xEnd = 0.5
            >>> maxIter = 1000
            >>> alfa = 0.15
            >>> ufr = 0.042
            >>> Precision = 0.0000000001
            >>> Tau = 0.0001
            >>> BisectionAlpha(xStart, xEnd, M_Obs, r_Obs, ufr, Tau, Precision, maxIter)
            [Out] 0.11549789285636511

        For more information see https://www.eiopa.europa.eu/sites/default/files/risk_free_interest_rate/12092019-technical_documentation.pdf and https://en.wikipedia.org/wiki/Bisection_method
        
        Implemented by Gregor Fabjan from Qnity Consultants on 17/12/2021.
        """

        yStart = growth_func(dividendyield, r_obs_est, dividenddatefrac, ufr, x_start)
        yEnd = growth_func(dividendyield, r_obs_est, dividenddatefrac, ufr, x_end)
        if np.abs(yStart) < Precision:
            return x_start
        if np.abs(yEnd) < Precision:
            return x_end  # If final point already satisfies the conditions return end point
        iIter = 0
        while iIter <= maxIter:
            xMid = (x_end + x_start) / 2  # calculate mid-point
            yMid = growth_func(dividendyield, r_obs_est, dividenddatefrac, ufr,
                               xMid)  # What is the solution at midpoint
            if ((yStart) == 0 or (x_end - x_start) / 2 < Precision):  # Solution found
                return xMid
            else:  # Solution not found
                iIter += 1
                if np.sign(yMid) == np.sign(
                        yStart):  # If the start point and the middle point have the same sign, then the root must be in the second half of the interval
                    x_start = xMid
                else:  # If the start point and the middle point have a different sign than by mean value theorem the interval must contain at least one root
                    x_end = xMid
        return "Did not converge"

# Missing create cash flows


# class Equity:
#    def __init__(self, nace, issuedate, issuername, dividendyield, frequency, marketprice,terminalvalue,enddate):
#        """
#        Equity class saves
#
#        Properties
#        ----------
#        nace
#        issuedate
#        frequency
#        marketprice
#        dividendyield
#        terminalvalue
#        growthrate
#        dividenddates
#        dividendfrac
#        terminaldates
#        dividendcfs
#        terminalcfs
#
#        """
#        self.nace = nace
#        self.issuedate = issuedate
#        self.issuername = issuername
#        self.frequency = frequency
#        self.marketprice = marketprice
#        self.dividendyield = dividendyield
#        self.terminalvalue = terminalvalue
#        self.enddate = enddate
#        self.terminaldates = []
#        self.growthrate = []
#        self.dividenddates = []
#        self.dividendfrac = []
#        self.terminaldates =[]
#        self.dividendcfs = []
#        self.terminalcfs = []
#
#    def createcashflowdates(self):
#        """
#        Create the vector of dates at which the dividends and terminal value are paid out.
#
#        Needs numpy as np and datetime as dt
#
#        Parameters
#        ----------
#        self : CorporateBond class instance
#            The CorporateBond instance with populated initial portfolio.
#
#        Returns
#        -------
#        Equity.dividenddates
#            An array of datetimes, containing all the dates at which the coupons are paid out.
#        Equity.terminaldates
#            An array of datetimes, containing the dates at which the principal is paid out
#        """
#
#        nAssets = self.issuedate.size
#
#        for iEquity in range(0,nAssets):
#            issuedate = self.issuedate[iEquity]
#            enddate   = self.enddate[iEquity]
#
#            dates = np.array([])
#            thisdate = issuedate
#
#            while thisdate <= enddate:
#                if self.frequency == 1:
#                    thisdate = dt.date(thisdate.year + 1, thisdate.month, thisdate.day)
#                    if thisdate <=enddate:
#                        dates = np.append(dates,thisdate)
#                    else:
#                        #return dates
#                        break
#                elif self.frequency == 2:
#                    thisdate = thisdate + dt.timedelta(days=182)
#                    if thisdate <= enddate:
#                        dates = np.append(dates, thisdate)
#                    else:
#                        break
#
#            self.dividenddates.append(dates)
#
#            # Notional payoff date is equal to maturity
#            self.terminaldates.append(np.array([self.enddate[iEquity]]))
#
#
# class EquityPriced:
#    def __init__(self, modellingdate,compounding, enddate, dividendyield, marketprice, terminalvalue, growthrates):
#        """
#        Equity class saves
#
#        Properties
#        ----------
#        modellingdate
#        compounding
#        enddate
#        dividendyield
#        growthrate
#        marketprice
#        terminalvalue
#        bookprice
#        dividenddatefrac
#        terminaldatefrac
#        dividendcfs
#        terminalcfs
#        """
#
#        self.modellingdate = modellingdate
#        self.compounding = compounding
#        self.enddate = enddate
#        self.dividendyield = dividendyield
#        self.growthrate = growthrates
#        self.marketprice = marketprice
#        self.terminalvalue = terminalvalue
#        self.bookprice = []
#        self.dividenddatefrac = []
#        self.terminaldatefrac =[]
#        self.dividendcfs = []
#        self.terminalcfs = []
#
#
#    def createcashflows(self):
#        """
#        Convert information about the equity into a series of cash flows and a series of dates at which the cash flows are paid.
#
#        Needs numpy as np
#        Parameters
#        ----------
#        self : EquityPriced object
#
#
#        Modifies
#        -------
#        EquityPriced
#            ToDo.
#
#        """
#        # Produce array of dates when coupons are paid out
#
#        nAssets = self.marketprice.size
#
#        # Missing what if date is 31,30
#        # Missing other frequencies
#
#        # Cash flow of each dividend
#        #dividendsize = self.marketprice*self.dividendyield
#
#        self.dividendcfs = []
#        self.dividenddates = []
#        self.terminaldates = []
#        self.terminalcfs = []
#
#        for iEquity in range(0,nAssets):
#            startyear = self.issuedate[iEquity].year
#            endyear   = self.maturitydate[iEquity].year
#            month     = self.issuedate[iEquity].month
#            day       = self.issuedate[iEquity].day
#
#            coupondateone = np.array([])
#
#            if self.frequency[iEquity] == 1:
#                for selectedyear in range(startyear,endyear+1): # Creates array of dates for selected ZCB
#                    dividenddateone = np.append(dividenddateone,dt.date(selectedyear,month,day))
#            elif self.frequency[iEquity] == 2:
#                #todo
#                print("Not completed")
#            else:
#                #todo
#                print("Not completed")
#
#            self.dividendcfs.append(np.ones_like(dividenddateone)*dividendsize[iEquity])
#            self.dividenddates.append(dividenddateone)
#
#            # Terminal payoff date is equal to maturity
#            self.terminaldates.append(np.array([self.maturitydate[iEquity]]))
#
#            # Cash flow of the principal payback
#            self.terminalcfs.append(np.array(self.terminal[iEquity]))
