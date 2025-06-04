############################################################################
### QPMwP - IBQR API - CONTRACTS
############################################################################

# --------------------------------------------------------------------------
# Cyril Bachelard
# This version:     16.05.2025
# First version:    2019
# --------------------------------------------------------------------------


# Standard library imports
from abc import ABC, abstractmethod
from typing import Union

# Load ibapi modules
from ibapi.contract import Contract




class IBContracts(ABC):

    '''
    Abstract base class for descendent classes that hold a list of Contract objects.
    For a description of possible contract types supported by IB visit:
    https://interactivebrokers.github.io/tws-api/classIBApi_1_1Contract.html
    '''

    def __init__(self, contract_list: list[Contract]):
        self.contract_list = contract_list

    @property
    def contract_list(self) -> list[Contract]:
        return self._contract_list

    @contract_list.setter
    def contract_list(self, value: list[Contract]) -> None:
        if not isinstance(value, list) or (
            value and not all(isinstance(i, Contract) for i in value)
        ):
            raise TypeError('Input argument must be a list of Contract instances.')
        self._contract_list = value
        return None

    def remove_contract(self, symbol: str) -> None:
        self.contract_list.remove(self.get_contract(symbol))
        return None

    def get_contract(self, symbol: str) -> Union[Contract, None]:
        symbols = self.get_symbols()
        if symbol in symbols:
            contract = self.contract_list[symbols.index(symbol)]
            return contract
        else:
            print(f'No contract found for symbol {symbol}')
            return None

    def get_symbols(self):
        return [contract.symbol for contract in self.contract_list]

    @abstractmethod
    def add_contract_from_symbol(self, symbol: str) -> None:
        raise NotImplementedError(
            'This method needs to be implemented in child classes.'
        )

    @abstractmethod
    def add_contract(self, contract: Contract) -> None:
        raise NotImplementedError(
            'This method needs to be implemented in child classes.'
        )



class EquityContracts(IBContracts):

    '''
    A class to manage a list of equity contracts.
    '''

    def add_contract(self, contract: Contract) -> None:
        if contract.secType == 'STK':
            self.contract_list.append(contract)
        else:
            raise ValueError('Contract.secType must be of type STK')
        return None

    def add_contract_from_symbol(self, 
                                 symbol: str,
                                 currency: str = 'USD',
                                 exchange: str = 'SMART') -> None:

        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError('Symbol must be a non-empty string.')

        # TODO:
        # Add funther checks to ensure that currency and exchange are valid

        contract = Contract()
        contract.secType = 'STK'
        contract.symbol = symbol
        contract.currency = currency
        contract.exchange = exchange
        self.add_contract(contract = contract)
        return None


class FXContracts(IBContracts):

    '''
    A class to manage a list of FX contracts.
    '''

    def add_contract(self, contract: Contract) -> None:
        if contract.secType == 'CASH':
            self.contract_list.append(contract)
        else:
            raise ValueError('Contract.secType must be of type CASH')
        return None

    def add_contract_from_symbol(self, 
                                 symbol: str, 
                                 currency: str = 'USD',
                                 exchange: str = 'IDEALPRO') -> None:

        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError('Symbol must be a non-empty string.')

        # TODO:
        # Add funther checks to ensure that currency and exchange are valid

        contract = Contract()
        contract.secType = 'CASH'
        contract.symbol = symbol
        contract.currency = currency
        contract.exchange = exchange
        self.add_contract(contract = contract)
        return None
