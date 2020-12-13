from gamebots import BattleBot
import logging

# 指定日志的输出等级（DEBUG / INFO / WARNING / ERROR）
logging.basicConfig(level=logging.INFO)

# 实例化一个bot
bot = BattleBot(
    quest='free_0.png',
    friend=['kongming_frd.png'],
    # friend=['skd_frd.png'],
    ap=[],
    # 要打的关卡有3面
    stage_count=3,
    mode=0,
    threshold=0.92
)

# 为了方便，使用了简写
s = bot.use_skill
m = bot.use_master_skill
a = bot.attack


# 第一面的打法
@bot.at_stage(1)
def stage_1():
    s(1, 3)
    a([7, 1, 2])


# 第二面的打法
@bot.at_stage(2)
def stage_2():
    s(3, 1, 2)
    s(3, 2)
    s(3, 3)
    s(2, 3)
    s(2, 2)
    s(2, 1)
    a([7, 1, 2])


# 第三面的打法
@bot.at_stage(3)
def stage_3():
    m(2, 1)
    m(1)
    s(1, 1)
    a([6, 1, 2])


if __name__ == '__main__':
    # 检查设备是否连接
    if not bot.device.connected():
        # 62001，62025, 7555
        bot.device.connect('127.0.0.1:5555')

    # 启动bot，最多打#次
    bot.run(max_loops=200)
