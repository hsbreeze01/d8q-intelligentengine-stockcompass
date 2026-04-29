#!/usr/bin/python
# -*- coding: UTF-8 -*-
import akshare as ak

import logging

from datetime import datetime

class StockData:
    def __init__(self, symbol):
        self.symbol = symbol

    def get_daily_data(self, start_date, end_date):
        stock_zh_a_daily_qfq_df = ak.stock_zh_a_daily(symbol=self.symbol, start_date=start_date, end_date=end_date, adjust="qfq")
        return stock_zh_a_daily_qfq_df

    def get_bid_ask(self):
        stock_bid_ask_em_df = ak.stock_bid_ask_em(symbol=self.symbol)
        return stock_bid_ask_em_df

    def get_realtime_data(self):
        stock_zh_a_spot_em_df = ak.stock_zh_a_spot_em()
        return stock_zh_a_spot_em_df[stock_zh_a_spot_em_df['代码'] == self.symbol]

    def get_news(self):
        stock_news_em_df = ak.stock_news_em(symbol=self.symbol)
        return stock_news_em_df

    def get_ggcg(self):
        stock_ggcg_em_df = ak.stock_ggcg_em(symbol=self.symbol)
        return stock_ggcg_em_df

    def get_jgdy_tj(self, date):
        stock_jgdy_tj_em_df = ak.stock_jgdy_tj_em(date=date)
        return stock_jgdy_tj_em_df[stock_jgdy_tj_em_df['代码'] == self.symbol].to_string()

    def get_jgcyd(self, symbol):
        stock_comment_detail_zlkp_jgcyd_em_df = ak.stock_comment_detail_zlkp_jgcyd_em(symbol=symbol)
        return stock_comment_detail_zlkp_jgcyd_em_df

    def get_scrd_focus(self, symbol):
        stock_comment_detail_scrd_focus_em_df = ak.stock_comment_detail_scrd_focus_em(symbol=symbol)
        return stock_comment_detail_scrd_focus_em_df

    def get_scrd_desire_daily(self, symbol):
        stock_comment_detail_scrd_desire_daily_em_df = ak.stock_comment_detail_scrd_desire_daily_em(symbol=symbol)
        return stock_comment_detail_scrd_desire_daily_em_df

    def get_scrd_cost(self, symbol):
        stock_comment_detail_scrd_cost_em_df = ak.stock_comment_detail_scrd_cost_em(symbol=symbol)
        return stock_comment_detail_scrd_cost_em_df

    def get_scrd_desire(self, symbol):
        stock_comment_detail_scrd_desire_em_df = ak.stock_comment_detail


def main():
    symbol = "sz000001"  # Example stock symbol
    symbol2 = "000001"  # Example stock symbol

    start_date = "20220101"
    end_date = "20221231"
    date = "20221231"

    stock_data = StockData(symbol)
    symbols = [symbol, symbol2]

    for sym in symbols:
        stock_data = StockData(sym)
        try:
            logging.info(f"Daily Data for {sym}:")
            print(stock_data.get_daily_data(start_date, end_date))
        except Exception as e:
            logging.error(f"Error getting daily data for {sym}: {e}")

        try:
            logging.info(f"Bid Ask Data for {sym}:")
            print(stock_data.get_bid_ask())
        except Exception as e:
            logging.error(f"Error getting bid ask data for {sym}: {e}")

        try:
            logging.info(f"Realtime Data for {sym}:")
            print(stock_data.get_realtime_data())
        except Exception as e:
            logging.error(f"Error getting realtime data for {sym}: {e}")

        try:
            logging.info(f"News Data for {sym}:")
            print(stock_data.get_news())
        except Exception as e:
            logging.error(f"Error getting news data for {sym}: {e}")

        try:
            logging.info(f"GGCg Data for {sym}:")
            print(stock_data.get_ggcg())
        except Exception as e:
            logging.error(f"Error getting GGCg data for {sym}: {e}")

        try:
            logging.info(f"JGdy TJ Data for {sym}:")
            print(stock_data.get_jgdy_tj(date))
        except Exception as e:
            logging.error(f"Error getting JGdy TJ data for {sym}: {e}")

        try:
            logging.info(f"JGCyd Data for {sym}:")
            print(stock_data.get_jgcyd(sym))
        except Exception as e:
            logging.error(f"Error getting JGCyd data for {sym}: {e}")

        try:
            logging.info(f"SCRD Focus Data for {sym}:")
            print(stock_data.get_scrd_focus(sym))
        except Exception as e:
            logging.error(f"Error getting SCRD Focus data for {sym}: {e}")

        try:
            logging.info(f"SCRD Desire Daily Data for {sym}:")
            print(stock_data.get_scrd_desire_daily(sym))
        except Exception as e:
            logging.error(f"Error getting SCRD Desire Daily data for {sym}: {e}")

        try:
            logging.info(f"SCRD Cost Data for {sym}:")
            print(stock_data.get_scrd_cost(sym))
        except Exception as e:
            logging.error(f"Error getting SCRD Cost data for {sym}: {e}")

        try:
            logging.info(f"SCRD Desire Data for {sym}:")
            print(stock_data.get_scrd_desire(sym))
        except Exception as e:
            logging.error(f"Error getting SCRD Desire data for {sym}: {e}")
            
    logging.info("Daily Data:")
    print(stock_data.get_daily_data(start_date, end_date))

    logging.info("Bid Ask Data:")
    print(stock_data.get_bid_ask())

    logging.info("Realtime Data:")
    print(stock_data.get_realtime_data())

    logging.info("News Data:")
    print(stock_data.get_news())

    logging.info("GGCg Data:")
    print(stock_data.get_ggcg())

    logging.info("JGdy TJ Data:")
    print(stock_data.get_jgdy_tj(date))

    logging.info("JGCyd Data:")
    print(stock_data.get_jgcyd(symbol))

    logging.info("SCRD Focus Data:")
    print(stock_data.get_scrd_focus(symbol))

    logging.info("SCRD Desire Daily Data:")
    print(stock_data.get_scrd_desire_daily(symbol))

    logging.info("SCRD Cost Data:")
    print(stock_data.get_scrd_cost(symbol))

    logging.info("SCRD Desire Data:")
    print(stock_data.get_scrd_desire(symbol))


if __name__ == "__main__":
    main()