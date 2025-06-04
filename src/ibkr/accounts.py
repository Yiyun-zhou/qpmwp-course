############################################################################
### QPMwP - IBQR API - ACCOUNTS
############################################################################

# --------------------------------------------------------------------------
# Cyril Bachelard
# This version:     16.05.2025
# First version:    2019
# --------------------------------------------------------------------------


# Load base and 3rd party packages
import time
from typing import Optional
import pandas as pd
import numpy as np

# Load IBKR modules
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.account_summary_tags import AccountSummaryTags

# Load project modules
from api import IBapi
from contracts import IBContracts, EquityContracts
from portfolios import EquityPortfolio








class IBAccount:

    '''
    A class to manage an Interactive Brokers (IBKR) account.

    This class provides functionalities to:
    - Initialize an IBKR account with a given account ID.
    - Request positions from the IBKR platform.
    - Handle multiple position requests and cancellations.

    Attributes
    ----------
    account_id : str
        The account ID for the IBKR account.
    positions : pd.DataFrame
        A DataFrame to store the positions of the account.
    '''

    def __init__(self, account_id: str):
        if not isinstance(account_id, str) or not account_id.strip():
            raise ValueError('account_id must be a non-empty string.')
        self._account_id = account_id
        self._positions = pd.DataFrame()

    @property
    def account_id(self) -> str:
        return self._account_id

    @property
    def positions(self) -> pd.DataFrame:
        return self._positions

    @positions.setter
    def positions(self, value: pd.DataFrame) -> None:
        if not isinstance(value, pd.DataFrame):
            raise TypeError('Input value must be a pandas DataFrame.')
        self._positions = value
        return None

    def request_acount_summary(self, connection: IBapi, reqId: int) -> None:
        connection.reqAccountSummary(reqId, 'All', AccountSummaryTags.AllTags)

    def request_positions(self, connection: IBapi) -> None:

        '''
        Call to EClient.reqPositions()
        Copies queried positions from connection.data_account to a dataframe
        and assigns it to self.positions.
        Eclient.reqPositions() subscribes to position updates for all accessible accounts.
        All positions sent initially, and then only updates as positions change
        See: https://www.interactivebrokers.com/campus/ibkr-api-page/twsapi-doc/#positions
        '''

        connection.clear_data_account()
        connection.reqPositions()
        time.sleep(1)
        df = pd.DataFrame(connection.data_account,
                          columns = ['Account', 'Contract', 'Position', 'AvgCost'])
        self.positions = df.copy()
        return None

    def cancel_request_positions(self, connection: IBapi) -> None:
        connection.cancelPositions()
        return None

    def request_positions_multi(self, connection: IBapi, model_code: str = '') -> None:

        '''
        Call to EClient.reqPositionsMulti()
        Copies queried positions from connection.data_account to a dataframe
        and assigns it to self.positions.
        Eclient.reqPositionsMulti() requests position subscription for account and/or model.
        Initially all positions are returned, and then updates are returned for any position changes in real time.
        See: https://www.interactivebrokers.com/campus/ibkr-api-page/twsapi-doc/#positions
        '''

        connection.clear_data_account()
        connection.reqPositionsMulti(reqId = connection.nextreqId,
                                     account = self.account_id,
                                     modelCode = model_code)
        time.sleep(1)
        df = pd.DataFrame(connection.data_account,
                          columns = ['RequestId', 'Account', 'ModelCode', 'Contract', 'Position', 'AvgCost'])
        self.positions = df.copy()
        return None

    def cancel_request_positions_multi(self, connection: IBapi) -> None:
        connection.cancelPositionsMulti()

    def get_equity_contracts(self, connection: IBapi, update: bool = False) -> EquityContracts:

        '''
        Retrieves equity contracts from the current positions.
        If update = True, requests updated positions from the IBKR platform (default is False).
        '''

        if self.positions.empty or update:
            self.request_positions(connection = connection)

        return EquityContracts(
            [contract for contract in self.positions['Contract'] if contract.secType == 'STK']
        )

    def get_equity_portfolio(self, connection: IBapi, update: bool = False) -> EquityPortfolio:

        '''
        Retrieves equity contracts from the current positions and creates an EquityPortfolio object.
        If update = True, requests updated positions from the IBKR platform (default is False).
        '''

        contracts = self.get_equity_contracts(connection = connection, update = update)
        portfolio = EquityPortfolio(contracts = contracts, nav = np.nan)  
        # TODO: 
        # Compute nav parameter from the account infos
        return portfolio

    def get_equity_positions(self, 
                             contracts: Optional[IBContracts] = None,
                             connection: Optional[IBapi] = None) -> dict[str, int]:

        # Extract the number of positions for each contract (as integers)
        # and set the index of n_positions to the symbols of the contracts.
        n_positions = self.positions['Position'].astype(int)
        n_positions.index = self.positions['Contract'].apply(lambda x: x.symbol)

        # If no contracts are provided, retrieve the equity contracts using the connection
        if contracts is None:
            contracts = self.get_equity_contracts(connection = connection)

        # Filter the positions to include only those that match the provided contracts' symbols
        # Return the filtered positions as a dictionary
        return n_positions[n_positions.index.isin(contracts.get_symbols())].to_dict()

    def get_equity_weights(self,
                           connection: IBapi,
                           update: bool = False,
                           tick_type: str = '') -> dict[str, float]:

        # Retrieve the equity portfolio
        portfolio = self.get_equity_portfolio(connection = connection, update = update)

        # Get quotes for the portfolio's contracts
        quotes = portfolio.get_quotes(connection = connection, tick_type = tick_type)

        # Get the number of positions for each contract in the portfolio
        n_positions = self.get_equity_positions(contracts = portfolio.contracts)

        # Calculate position values
        values = pd.Series(quotes).astype(float) * pd.Series(n_positions).astype(float)

        # Return the normalized values
        return {symbol: value / values.sum() for symbol, value in values.items()}




class IBAccounts:

    def __init__(self):
        self.positions = None
        self.accounts = None

    def request_account_summary(self, connection: IBapi, reqId: int, account: str) -> None:

        connection.reqAccountSummary(reqId = reqId,
                                     groupName = 'All',
                                     tags = AccountSummaryTags.AllTags)
        return None

    def cancel_request_account_summary(self, connection: IBapi, reqId: int) -> None:

        connection.cancelAccountSummary(reqId = reqId)
        return None

    def request_positions(self, connection: IBapi) -> None:
        connection.clear_data_account()
        connection.reqPositions()
        time.sleep(1)
        df = pd.DataFrame(connection.data_account,
                          columns = ['account', 'contract', 'n_positions', 'avg_cost'])
        self.positions = df.copy()
        return None

    def cancel_request_positions(self, connection: IBapi) -> None:
        connection.cancelPositions()
        return None

