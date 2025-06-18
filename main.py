import asyncio
import json

from aiogram import Bot, Dispatcher
from aiogram.types import ParseMode
from aiogram.utils import executor
from loguru import logger
from web3 import Web3, HTTPProvider

from trader import Trader

logger.add('app.log', format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}")

bot: Bot
dp: Dispatcher

web3: Web3
trader: Trader
TX_URL: str

accounts = []
channel_id: int

INTERVAL: int


def load_config():
    logger.info('Loading config...')
    with open('config.json') as f:
        return json.load(f)


def load_accounts():
    """Load ethereum wallets private keys from keys.txt file for making swaps"""
    logger.info('Loading accounts...')
    with open('keys.txt') as f:
        for key in f:
            key = key.strip()
            address = web3.eth.account.from_key(key).address
            accounts.append((address, key))


async def boost_volume():
    logger.info('Volume Booster Start...')
    while True:
        for account in accounts:
            address, key = account
            pls = trader.get_pls_balance(address)  # Changed from get_bnb_balance
            if pls > 0 and trader.can_buy(pls, wallet=address):
                result = trader.buy(address, key, pls)
                await bot.send_message(channel_id,
                                       f'Bought {result["amount"]} {trader.symbol} tokens with {result["bnb"]} PLS\n{TX_URL % result["tx"]}')
                await asyncio.sleep(10)
            tokens_amount = trader.get_token_balance(address)
            if tokens_amount > 0:
                result = trader.sell(address, key, tokens_amount)
                await bot.send_message(channel_id,
                                       f'Sold {result["amount"]} {trader.symbol} tokens for {result["bnb"]} PLS\n{TX_URL % result["tx"]}')
            # logger.error(f"Account {address} can't buy and sell\nPLS: {pls}\nTokens amount:{tokens_amount}")
            # await bot.send_message(channel_id,
            #                        f"Account {address} can't buy and sell\nPLS balance: {trader.wei_to_eth(pls)}\nTokens balance:{tokens_amount / trader.decimals}")
            await asyncio.sleep(INTERVAL)


def init():
    global bot, dp, web3, trader, TX_URL, INTERVAL, channel_id
    config = load_config()
    web3 = Web3(HTTPProvider(config['pulseChainNode']))  # Changed from bscNode
    TX_URL = config['txUrl']
    channel_id = config['channelId']
    INTERVAL = config['intervalInSeconds']

    router_abi = json.loads(config['pulseXRouterABI'])  # Changed from pancakeswapRouterABI
    router_address = Web3.toChecksumAddress(config['pulseXRouterAddress'])  # Changed from pancakeSwapRouterAddress

    logger.info(f'Connected: {web3.isConnected()}')
    logger.info(f'Chain ID: {web3.eth.chainId}')

    token_address = Web3.toChecksumAddress(config['tokenAddress'])
    token_abi = json.loads(config['tokenABI'])
    token_contract = web3.eth.contract(address=token_address, abi=token_abi)

    bot = Bot(token=config['telegramBotToken'], parse_mode=ParseMode.HTML)
    dp = Dispatcher(bot)
    load_accounts()
    trader = Trader(web3, router_address, router_abi, token_contract, token_address)


async def on_bot_start_up(dispatcher) -> None:
    """List of actions which should be done before bot start"""
    logger.info('Start up')
    asyncio.create_task(boost_volume())


if __name__ == '__main__':
    init()
    executor.start_polling(dp, skip_updates=True, on_startup=on_bot_start_up)
