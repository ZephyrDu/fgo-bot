import logging
from gamebots import AssistBot

logging.basicConfig(level=logging.INFO)

bot = AssistBot(mode=0, n_iter=5, threshold=0.88)

if __name__ == '__main__':
    if not bot.device.connected():
        # 62001， 5555, 7555
        bot.device.connect('127.0.0.1:5555')
    bot.sort_mailbox(expstr=["exp_silver.png", "exp_1.png", "exp_2.png"])
