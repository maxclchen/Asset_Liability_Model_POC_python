# Main script for POC
from ImportData import GetEquityShare, GetSettings, importSWEiopa
from EquityClasses import *
from PathsClasses import Paths
from Curves import Curves
import datetime

paths = Paths() # Object used for folder navigation

# Import run parameters

settings = GetSettings(paths.input+"Parameters_2.csv")
end_date = settings.modelling_date + relativedelta(years=settings.n_proj_years)

# Import risk free rate curve
[maturities_country, curve_country, extra_param, Qb] = importSWEiopa(settings.EIOPA_param_file,settings.EIOPA_curves_file, settings.country)

curves = Curves(extra_param["UFR"]/100, settings.precision, settings.tau, settings.modelling_date , settings.country)

end_date = settings.modelling_date + relativedelta(years=settings.n_proj_years)

# Create generator that contains all equity positions
equity_input_generator = GetEquityShare(paths.input+"Equity_Portfolio_test.csv")
 
# Create equity portfolio class that will contain all positions
equity_portfolio = EquitySharePortfolio()

# Fill portfolio with positions
for equity_share in equity_input_generator:
    equity_portfolio.add(equity_share)

dividend_dates = equity_portfolio.create_dividend_dates(settings.modelling_date, end_date)
terminal_dates = equity_portfolio.create_terminal_dates(modelling_date=settings.modelling_date, terminal_date=end_date, terminal_rate=curves.ufr)

[all_date_frac, all_dates_considered] = equity_portfolio.create_dividend_fractions(settings.modelling_date, dividend_dates) 
[all_dividend_date_frac, all_dividend_dates_considered] = equity_portfolio.create_terminal_fractions(settings.modelling_date, terminal_dates)

print(equity_portfolio.equity_share)
print(settings.modelling_date)



