"""Connects and sends signals to the Binance server."""

import math
import json
import traceback
import time
from typing import List, Callable, Optional
import numpy as np
from binance.client import Client
from binance.enums import ORDER_TYPE_MARKET


class SendOrderSignal:
    """Connects and sends signals to the Binance server."""

    def __init__(self):
        self._client = self._set_client()

    def respect_request_limit(
        fn: Optional[Callable] = None,
        *args,
        **kwargs
    ) -> Callable:
        """Delays a call whilst if the headers are asking us to limit the
        number of request.

        Args:
            fn - (Callable) Function/method to call.

        Returns:
            Callable - A decorator function.
        """

        def decorate(self, *args, **kwargs):
            retryAfter = self.get_client().response.headers.get('Retry-After')
            if retryAfter:
                print(
                    f'\033[93mREQUEST LIMIT REACHED. SLEEPING FOR {retryAfter} SECONDS.\033[0m'
                )
                time.sleep(int(retryAfter))

            if fn:
                fn(self, *args, **kwargs)

        return decorate

    @staticmethod
    def _set_client() -> Client:
        """Set the client object to connect to Binance."""
        with open('.keys.json', 'r') as keysFile:
            keys = json.load(keysFile)

        return Client(keys['BINANCE_API_KEY'], keys['BINANCE_SECRET_KEY'])

    def get_client(self) -> Client:
        """Returns the client object."""
        return self._client

    @respect_request_limit
    def send_signal(
        self,
        side: str,
        tradeSymbol: str,
        quantity: float,
        testMode: bool,
        orderType=ORDER_TYPE_MARKET,
    ) -> dict:
        """Sends a buy/sell request.

        Args:
            side - (str) Buy or sell command.
            tradeSymbol - (str) Trade symbol.
            quantity - (float) Quantity.
            testMode: (bool) Run in test mode? If `True`, this will not create
                live orders.
            orderType - (str) Order type, limit, market, etc.

        Returns:
            dict - Contains information describing whether or not the buy/sell
            request was successful (key=`success`). Where the request was
            successfull, results will also contain a `results` key containing
            the response from the API. Otherwise, a `params` key will exist
            with the paramaters provided an a `error` key with the traceback
            message.
        """

        # Set the order method to use based on whether the order is a test
        # order or not.
        if testMode:
            order = self.get_client().create_test_order
        else:
            order = self.get_client().create_order

        try:
            print("\033[94mSENDING SIGNAL.\033[0m")
            res = order(
                symbol=tradeSymbol,
                side=side,
                type=orderType,
                quantity=quantity
            )

            return {
                'success': bool(res.get('clientOrderId')),
                'results': res
            }

        except Exception:
            return {
                'success': False,
                'params': {
                    'side': side,
                    'quantity': quantity
                },
                'error': traceback.format_exc()
            }

    @respect_request_limit
    def apply_filters(self, tradeSymbol: str, quantity: float) -> float:
        """Applies filters onto the `quantity` so that the value send later
        for trade is valid.

        Args:
            tradeSymbol - (str) Trade symbol.
            quantity - (float) Quantity.

        Returns:
            float - Quantity to buy/sell.
        """

        symbolInfo = self.get_client().get_symbol_info(tradeSymbol)

        filters = symbolInfo['filters']
        for filt in filters:
            if filt['filterType'] == 'LOT_SIZE':
                stepSize = float(filt['stepSize'])

                # Adding an higher level round to remove any floating point
                # errors.
                quantity = round(
                    math.floor(quantity / stepSize) * stepSize,
                    symbolInfo['quotePrecision']
                )
                break

        return np.format_float_positional(quantity)

    @respect_request_limit
    def asset_balance(self, asset: str) -> float:
        """Fetch the asset balance.

        Args:
            asset - (str) Asset name.

        Returns:
            float - Asset balance.
        """
        return float(self.get_client().get_asset_balance(asset=asset)['free'])

    @respect_request_limit
    def has_coins(self, asset: str, tradeSymbol: str) -> bool:
        """Checks if the user has coins that they can trade. This will require
        the `tradeSymbol` to be provided as supposed to just the `asset`. By
        doing so, we can check if the quantity owned, is greater than the
        minimum quantity needed to initiate an order.

        Args:
            asset - (str) Asset name.
            tradeSymbol - (str) Trade symbol.

        Returns
            bool - Indicate whether the user has coins they can trade.
        """
        balance = float(
            self.get_client().get_asset_balance(asset=tradeSymbol.replace(
                asset,
                ''
            ))['free']
        )

        filters = self.get_client().get_symbol_info(tradeSymbol)['filters']
        for filt in filters:
            if filt['filterType'] == 'LOT_SIZE':
                return balance >= float(filt['minQty'])
        else:
            return False

    @respect_request_limit
    def historical_data(
        self,
        tradeSymbol: str,
        interval: str = Client.KLINE_INTERVAL_1MINUTE,
        dateFromStr: str = '20 mins ago UTC'
    ) -> List[float]:
        """Returns a set of historical closing data.

        Args:
            tradeSymbol - (str) Trade symbol.
            interval - (str) Interval.
            dateFromStr - (str) Date from which to start collecting historical
                data.

        Returns:
            list - Collection of closing prices.
        """
        data = self.get_client().get_historical_klines(
            tradeSymbol,
            interval,
            dateFromStr
        )
        return [float(d[4]) for d in data]
