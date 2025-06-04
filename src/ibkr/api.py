############################################################################
### QPMwP - IBQR API - API
############################################################################

# --------------------------------------------------------------------------
# Cyril Bachelard
# This version:     16.05.2025
# First version:    2019
# --------------------------------------------------------------------------


# Load base and 3rd party packages
from decimal import Decimal

# Load IBKR modules
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.common import BarData, TickAttrib
from ibapi.ticktype import TickType, TickTypeEnum
from ibapi.contract import Contract




class IBapi(EWrapper, EClient):

    _nextreqId = 0
    _nextorderId = None

    def __init__(self, verbose: bool = True):
        EClient.__init__(self, self)
        self.data_current = {} # Initialize variable to store current quotes
        self.data_hist = [] # Initialize variable to store time series of prices and volume
        self.data_account = [] # Initialize variable to store account information
        self.verbose = verbose

    @property
    def nextreqId(self) -> int:
        id = self._nextreqId
        if id is None:
            self._nextreqId = 0
        else:
            self._nextreqId += 1
        return id

    def clear_data_current(self) -> None:
        self.data_current = {}
        return None

    def clear_data_hist(self) -> None:
        self.data_hist = []
        return None

    def clear_data_account(self) -> None:
        self.data_account = []
        return None

    # --------------------------------------------
    # EWrapper methods (receiving data from TWS)
    # --------------------------------------------

    # Receiving Tick Price (requires market data subscription)
    def tickPrice(self,
                  reqId: int,
                  tickType: TickType,
                  price: float, 
                  attrib: TickAttrib) -> None:
        self.data_current[TickTypeEnum.to_str(tickType)] = price
        return None

    def marketData(self,
                   reqId: int,
                   tickType: TickType, 
                   price: float, 
                   attrib: TickAttrib) -> None:
        self.data_current[TickTypeEnum.to_str(tickType)] = price
        return None

    # Receiving Historical Bar Data
    def historicalData(self,
                       reqId: int,
                       bar: BarData) -> None:
        if self.verbose:
            print(f'Time: {bar.date} Open: {bar.open} High: {bar.high} Low: {bar.low} Close: {bar.close} Volume: {bar.volume}')
        self.data_hist.append([bar.date, bar.open, bar.high, bar.low, bar.close, bar.volume])
        return None

    # Receiving account and portfolio information
    def accountSummary(self, reqId: int, account: str, tag: str, value: str,currency: str):
        print(
            'AccountSummary. ReqId:', reqId,
            'Account:', account,
            'Tag: ', tag,
            'Value:', value,
            'Currency:', currency
        )

    def accountSummaryEnd(self, reqId: int):
        print('AccountSummaryEnd. ReqId:', reqId)

    def position(self,
                 account: str,
                 contract: Contract,
                 position: Decimal,
                 avgCost: float) -> None:
        print(
            'Position.', 
            'Account:', account,
            'Contract:', contract,
            'Position:', position,
            'AvgCost:', avgCost
        )
        self.data_account.append([account, contract, position, avgCost])
        return None

    def positionEnd(self):
        print('PositionEnd')

    def positionMulti(self,
                      reqId: int,
                      account: str,
                      modelCode: str,
                      contract: Contract,
                      pos: Decimal,
                      avgCost: float) -> None:
        print(
            'PositionMulti',
            'RequestId:', reqId, 
            'Account:', account,
            'ModelCode:', modelCode,
            'Contract:', contract, 
            'Position:', pos,
            'AvgCost:', avgCost
        )
        self.data_account.append([reqId, account, modelCode, contract, pos, avgCost])
        return None

    def positionMultiEnd(self, reqId: int):
        print('')
        print('PositionMultiEnd. RequestId:', reqId)


    # --------------------------------------------
    # EClient methods (sending instructions to TWS)
    # --------------------------------------------

    # To fire an order, create a contract object with the asset details
    # and an order object with the order details.
    # Then call app.placeOrder to submit the order.
    # Note, the IB API requires an order id associated with all orders
    # and it needs to be a unique positive integer larger than the last order id used.

    def nextValidId(self, orderId: int) -> None:
        super().nextValidId(orderId)
        self.nextorderId = orderId
        print('The next valid order id is: ', self.nextorderId)
        return None

    def orderStatus(self,
                    orderId,
                    status,
                    filled,
                    remaining,
                    avgFullPrice,
                    permId,
                    parentId,
                    lastFillPrice,
                    clientId,
                    whyHeld,
                    mktCapPrice) -> None:
        '''
        This function is called when an order is placed via the .placeOrder method.
        '''

        print(
            'orderStatus - orderid:', orderId, 
            'status:', status, 
            'filled:', filled, 
            'remaining:', remaining, 
            'lastFillPrice:', lastFillPrice
        )
        return None

    def openOrder(self, orderId, contract, order, orderState) -> None:

        '''
        This function is called when an order is placed via the .placeOrder method.
        '''

        print(
            'openOrder id:', orderId,
            contract.symbol,
            contract.secType, '@', contract.exchange, ':', order.action,
            order.orderType,
            order.totalQuantity,
            orderState.status
        )
        return None

    def execDetails(self, reqId, contract, execution) -> None:

        '''
        This function is called when an order is placed via the .placeOrder method.
        '''

        print(
            'Order Executed: ', reqId, 
            contract.symbol,
            contract.secType,
            contract.currency,
            execution.execId,
            execution.orderId,
            execution.shares,
            execution.lastLiquidity
        )
        return None

