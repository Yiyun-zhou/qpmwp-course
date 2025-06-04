############################################################################
### QPMwP - IBQR API - PORTFOLIOS
############################################################################

# --------------------------------------------------------------------------
# Cyril Bachelard
# This version:     16.05.2025
# First version:    2019
# --------------------------------------------------------------------------


# Load base and 3rd party packages
import time
from abc import ABC, abstractmethod
from typing import Optional
import pandas as pd
import numpy as np

# Load IBKR modules
from ibapi.contract import Contract
from ibapi.order import Order

# Load project modules
from api import IBapi
from contracts import IBContracts, EquityContracts




class IBPortfolio(ABC):

    '''
    Abstract base class for descendent portfolio classes.

    These classes are used to
    - manage contracts
    - place requests (market data and historical data)
    - prepare and place orders on the IBKR platform.
    '''

    def __init__(self,
                 contracts: IBContracts,
                 nav: float = 0) -> None:
        self.contracts = contracts
        self.nav = nav

    @property
    def contracts(self) -> IBContracts:
        return self._contracts

    @contracts.setter
    def contracts(self, value: IBContracts) -> None:
        if not isinstance(value, IBContracts):
            raise TypeError('Input value must be an instance of a child of IBContracts')
        self._contracts = value
        return None

    @property
    def nav(self) -> float:
        return self._nav

    @nav.setter
    def nav(self, value: float) -> None:
        if isinstance(value, int):
            value = float(value)
        if not isinstance(value, float):
            raise TypeError('Input value must be of type float')
        self._nav = value
        return None

    def get_quotes(self,
                   connection: IBapi,
                   tick_type: str = '') -> dict[str, dict]:

        quotes_dict = self.request_market_data(connection = connection,
                                               symbols = self.contracts.get_symbols(),
                                               tick_type = tick_type)
        if tick_type == '':
            tick_type = 'CLOSE'
        return {symbol: quotes_dict[symbol][tick_type] for symbol in quotes_dict.keys()}

    def calc_order_quantities(self,
                              w_init: dict[str, float],
                              w_new: dict[str, float],
                              quotes: dict[str, dict],
                              nav: Optional[float] = None) -> dict[str, float]:
        if nav is None:
            nav = self.nav
        quantities = {}
        for key in w_init.keys():
            quantity = (w_new[key] - w_init[key]) * nav / quotes[key]
            # Truncate the decimal part as fractional-sized orders cannot be placed via api.
            quantities[key] =  int(quantity)
        return quantities

    def prepare_orders(self,
                       connection: IBapi,
                       w_init: dict[str, float],
                       w_new: dict[str, float],
                       quotes: dict[str, float],
                       order_type = 'MKT') -> dict[str, Order]:

        order_quantities = self.calc_order_quantities(w_init = w_init,
                                                      w_new = w_new,
                                                      quotes = quotes)
        orders = {}

        for key, value in order_quantities.items():
            order = Order()
            order.orderId = connection.nextorderId
            connection.nextorderId += 1
            order.totalQuantity = np.abs(value)
            order.orderType = order_type    # Use the same type for all orders
            if value != 0:
                order.action = 'BUY' if value > 0 else 'SELL'
                orders[key] = order

        return orders

    def place_orders(self,
                     connection: IBapi,
                     orders: dict[str, Order]) -> None:

        for symbol, order in orders.items():
            self.place_order(connection = connection,
                             contract = self.contracts.get_contract(symbol),
                             order = order)
        return None

    def place_order(self,
                    connection: IBapi,
                    contract: Contract,
                    order: Order) -> None:

        connection.placeOrder(orderId = order.orderId,
                              contract = contract,
                              order = order)
        return None

    @abstractmethod
    def request_market_data(self,
                            connection: IBapi,
                            symbols: list[str],
                            tick_type: str) -> dict[str, dict]:
        raise NotImplementedError(
            'This method needs to be implemented in child classes.'
        )

    @abstractmethod
    def request_historical_data(self,
                                connection: IBapi,
                                durationStr: str,
                                barSizeSetting: str) -> pd.DataFrame:
        raise NotImplementedError(
            'This method needs to be implemented in child classes.'
        )


class EquityPortfolio(IBPortfolio):

    '''
    A class to manage EquityContracts and 
    to place requests and to prepare and place orders on the IBKR platform.
    '''

    def __init__(self,
                 contracts: EquityContracts,
                 nav: float = 0) -> None:
        if not isinstance(contracts, EquityContracts):
            raise TypeError('contracts must be an instance of EquityContracts')
        super().__init__(contracts = contracts, nav = nav)

    def request_market_data(self,
                            connection: IBapi,
                            symbols: list[str],
                            tick_type: str = '') -> dict[str, dict]:

        # Clear any previous price data
        connection.clear_data_current()

        # Get quotes by symbol
        quotes = {}
        for symbol in symbols:
            contract = self.contracts.get_contract(symbol)
            connection.reqMktData(
                reqId = connection.nextreqId,  # Must be a unique value. When the market data returns, it will be identified by this tag. This is also used when canceling the market data.
                contract = contract,
                genericTickList = tick_type,   # A commma delimited list of generic tick types.
                snapshot = False,              # Check to return a single snapshot of Market data and have the market data subscription cancel. Do not enter any genericTicklist values if you use snapshots.
                regulatorySnapshot = False,
                mktDataOptions = []
            )
            time.sleep(1)
            quotes[symbol] = connection.data_current.copy()
        return quotes

    def request_historical_data(self,
                                connection: IBapi,
                                durationStr: str = '1 Y',
                                barSizeSetting: str = '1 day') -> pd.DataFrame:

        #// Data Type options: BID, ASK, MIDPOINT. 
        #// For full list see: https://interactivebrokers.github.io/tws-api/historical_bars.html

        # TODO: 
        # Change 'whatToShow
        
        # Get historical data
        data_hist = pd.DataFrame()
        for reqId, contract in enumerate(self.contracts.contract_list):

            # Clear any previous historical price data
            connection.clear_data_hist()
        
            connection.reqHistoricalData(
                reqId = reqId + 1,                # :tickerId, A unique identifier which will serve to identify the incoming data.
                contract = contract,              # The IBapi.Contract you are interested in.
                endDateTime = '',                 # The request's end date and time (the empty string indicates current present moment).
                durationStr = durationStr,        # The amount of time (or Valid Duration String units) to go back from the request's given end date and time.
                barSizeSetting = barSizeSetting,  # The data's granularity or Valid Bar Sizes
                whatToShow = 'TRADES',           # The type of data to retrieve. See Historical Data Types
                # whatToShow = 'ADJUSTED_LAST', # dvd adjusted
                useRTH = 0,                       # Whether (1) or not (0) to retrieve data generated only within Regular Trading Hours (RTH)
                formatDate = 1,                   # :int, The format in which the incoming bars' date should be presented. Note that for day bars, only yyyyMMdd format is available. 1 - dates connectionlying to bars returned in the format: yyyymmdd{space}{space}hh:mm:dd 2 - dates are returned as a long integer specifying the number of seconds since
                chartOptions = False,             # For internal use only.
                keepUpToDate = False              # Whether a subscription is made to return updates of unfinished real time bars as they are available (True), or all data is returned on a one-time basis (False).
            )
            time.sleep(1)

            data_hist_tmp = pd.DataFrame(connection.data_hist, columns = ['date', 'open', 'high', 'low', 'close', 'volume'])
            data_hist_tmp['symbol'] = contract.symbol
            data_hist_tmp['date'] = pd.to_datetime(data_hist_tmp['date'])
            data_hist_tmp.set_index(['date', 'symbol'], inplace=True)

            data_hist = pd.concat([data_hist, data_hist_tmp])

        return data_hist



