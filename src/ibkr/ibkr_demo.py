############################################################################
### QPMwP - IBQR API - DEMO
############################################################################

# --------------------------------------------------------------------------
# Cyril Bachelard
# This version:     16.05.2025
# First version:    16.05.2025
# --------------------------------------------------------------------------



# Standard library imports
import os
import sys
import threading
import time
from datetime import datetime

# Third party imports
import pandas as pd
import numpy as np

# Load IBKR modules
from ibapi.ticktype import TickType, TickTypeEnum
from ibapi.order import Order

# Add the project root directory to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src_path = os.path.join(project_root, 'src')
sys.path.append(project_root)
sys.path.append(src_path)

# Local modules imports
from estimation.covariance import Covariance
from estimation.expected_return import ExpectedReturn
from optimization.constraints import Constraints
from optimization.optimization import MeanVariance
from optimization.optimization_data import OptimizationData
from api import IBapi
from contracts import (
    EquityContracts,
    FXContracts,
)
from portfolios import EquityPortfolio
from accounts import IBAccount





# Constants
TWS_SOCKET_PORT_DEMO = 7497
TWS_SOCKET_PORT_LIVE = 7496
CLIENT_ID = 123 # used to identify your script to the API. It can be any unique positive integer.
IP_ADDRESS = '127.0.0.1'
# ACCOUNT_ID = '' #<Change this to your account ID>
SYMBOLS_FX = ['CHF', 'EUR', 'GBP', 'JPY']

# Import symbols from csv file
path_to_data = f'{os.path.dirname(os.path.dirname(os.getcwd()))}\\data\\'
symbols = pd.read_csv(f'{path_to_data}symbols.csv') # <Change this path to your symbols.csv file>
SYMBOLS_EQTY_CH = symbols['id_exch_symbol'].tolist()
SYMBOLS_EQTY = SYMBOLS_EQTY_CH[0:10]  # Subset the list to the first 10 symbols


ACCOUNT_ID = 'DU6755222'




# --------------------------------------------------------------------------
# Launch the IBKR TWS API
# --------------------------------------------------------------------------

if 'conn' in locals() and conn is not None:
    conn.disconnect()
    conn = None
    api_thread = None
    

conn = IBapi()
conn.connect(
    host=IP_ADDRESS,
    port=TWS_SOCKET_PORT_DEMO,
    # port=TWS_SOCKET_PORT_LIVE,
    clientId=CLIENT_ID + 1,
)



# Start the socket in a thread
api_thread = threading.Thread(target=conn.run, daemon=True)
api_thread.start()
time.sleep(1) # Sleep interval to allow time for connection to server
api_thread.is_alive()
# api_thread.join()


conn.reqMarketDataType(3) # 3 = delayed data - Free, delayed data is 15 - 20 minutes delayed. Tick ID 66 - 76
# conn.reqMarketDataType(4) # 4 = delayed-frozen data for user without market data subscription




# --------------------------------------------------------------------------
# Initialize contracts objects and add ibapi.contract from symbol
# --------------------------------------------------------------------------


# Initialize contracts

# FX
fx_contracts = FXContracts([])
for symbol in SYMBOLS_FX:
    fx_contracts.add_contract_from_symbol(symbol=symbol)

# Equity
eqty_contracts = EquityContracts([])
for symbol in SYMBOLS_EQTY:
    eqty_contracts.add_contract_from_symbol(
        symbol=symbol,
        currency='CHF'
    )




# --------------------------------------------------------------------------
# Initialize a portfolio object and populate it with eqty_contracts and NAV
# --------------------------------------------------------------------------

# Initialize equity portfolio
eqty_portfolio = EquityPortfolio(
    contracts=eqty_contracts,
    nav=50_000
)

# The following should fail because of wrong secType:
# EquityPortfolio(contracts=fx_contracts, nav=50_000)






# --------------------------------------------------------------------------
# Query market data from the portfolio object
# --------------------------------------------------------------------------


# Enumerate all tick types
for i in range(91):
	print(TickTypeEnum.to_str(i), i)



# Request market data for all contracts in the portfolio
quotes_dict = eqty_portfolio.request_market_data(
    connection=conn,
    symbols=eqty_portfolio.contracts.get_symbols(),
    tick_type='',
)
quotes_dict

close_prices = {
    key: quotes_dict[key]['CLOSE'] for key in quotes_dict.keys()
}
close_prices

# Alternatively, use wrapper method to get quotes
quotes = eqty_portfolio.get_quotes(connection=conn, tick_type='')
quotes



# Query historical market prices
data_hist = eqty_portfolio.request_historical_data(
    connection=conn,
    durationStr='1 Y',
    barSizeSetting='1 day'
)
data_hist


prices = data_hist.pivot_table(index='date', columns='symbol', values='close')
volume = data_hist.pivot_table(index='date', columns='symbol', values='volume')
return_series = prices.ffill().pct_change().dropna()

prices
volume
return_series

np.log((1 + return_series).cumprod()).plot()











# --------------------------------------------------------------------------
# Account
# --------------------------------------------------------------------------

account = IBAccount(account_id=ACCOUNT_ID)

account.request_acount_summary(connection=conn, reqId=1)
conn.data_account

account.request_positions(connection=conn)
account.positions

current_eqty_portfolio = account.get_equity_portfolio(connection=conn)
current_eqty_portfolio.contracts.get_symbols()

account.get_equity_weights(connection=conn, update=True)






# --------------------------------------------------------------------------
# Optimize portfolio weights
# --------------------------------------------------------------------------

today = datetime.today().strftime('%Y-%m-%d')
today

# Estimators
expected_return = ExpectedReturn(method='geometric')
covariance = Covariance(method='pearson')

# Constraints
constraints = Constraints(ids=return_series.columns.to_list())
constraints.add_budget()
constraints.add_box(lower=0, upper=0.3)

# Construct an equally-weighted initial portfolio
initial_weights = {key: 1/len(return_series.columns) for key in return_series.columns}

# Optimization
optimization = MeanVariance(
    solver_name='cvxopt',
    x_init=initial_weights,
    constraints=constraints,
    expected_return=expected_return,
    covariance=covariance,
)

# Optimization data
optimization_data = OptimizationData(return_series=return_series)

# Solve
optimization.set_objective(optimization_data=optimization_data)
optimization.solve()
optimization.results




# --------------------------------------------------------------------------
# Generate orders
# --------------------------------------------------------------------------

x_init = optimization.params['x_init']
x_new = optimization.results['weights']
pd.concat({
    'initial_weights': pd.Series(x_init),
    'optimized_weights': pd.Series(x_new),
}, axis=1)

# Calculate order quantities based on current quotes
quotes = eqty_portfolio.get_quotes(connection=conn, tick_type='')
quotes
order_quantities = eqty_portfolio.calc_order_quantities(
    w_init=x_init,
    w_new=x_new,
    quotes=quotes
)
order_quantities    


# Checks
pd.Series(x_init) * eqty_portfolio.nav
pd.Series(x_new) * eqty_portfolio.nav
pd.Series(x_new) * eqty_portfolio.nav - pd.Series(x_init) * eqty_portfolio.nav
pd.Series(quotes) * pd.Series(order_quantities)  # same same



# Prepare orders
orders = eqty_portfolio.prepare_orders(
    connection=conn,
    w_init=x_init,
    w_new=x_new,
    quotes=quotes,
)
orders









# Check if the API is connected via orderid
while True:
	if isinstance(conn.nextorderId, int):
		print('connected')
		break
	else:
		print('waiting for connection')
		time.sleep(1)

# Create buy order object
order = Order()
order.action = 'BUY'
order.totalQuantity = 5
# order.orderType = 'MKT'
order.orderType = 'LMT'
order.lmtPrice = 26


dir(order)
order.orderId


order
orders[2]


# Create sell order object
order = Order()
order.action = 'SELL'
order.totalQuantity = 5
order.orderType = 'MKT'
# order.orderType = 'LMT'
# order.lmtPrice = 26



contract = contracts.get_contract('UBSG')

# Place order
conn.placeOrder(conn.nextorderId, contract, order)
# conn.nextorderId += 1








time.sleep(3)

# Cancel order
print('cancelling order')
conn.cancelOrder(conn.nextorderId)









# --------------------------------------------------------------------------
# Trade, i.e., place orders
# --------------------------------------------------------------------------


orders = eqty_portfolio.prepare_orders(
    connection=conn,
    w_init=x_init,
    w_new=x_new,
    quotes=quotes
)
orders

eqty_portfolio.place_orders(connection=conn, orders=orders)





# Disconnect from the API
time.sleep(10)
conn.disconnect()








