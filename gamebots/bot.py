import json
import logging
from functools import partial
from pathlib import Path
from random import randint
from time import sleep, time
from typing import Callable
from typing import List, Union

from .device import Device
from .tm import TM

logger = logging.getLogger('bot')

INTERVAL_SHORT = 1
INTERVAL_MID = 10
INTERVAL_LONG = 25


class BattleBot:
    """
    A class of the bot that automatically plays.
    """

    def __init__(self,
                 quest: str = 'quest.png',
                 friend: Union[str, List[str]] = 'friend.png',
                 stage_count: int = 3,
                 ap: List[str] = None,
                 mode: int = 0,
                 threshold: float = 0.97
                 ):

        # A dict of the handler functions that are called repeatedly at each stage.
        # Use `at_stage` to register functions.
        self.stage_handlers = {}

        # A dict of configurations.
        self.config = {}

        self.stage_count = stage_count
        logger.info('Stage count set to {}.'.format(self.stage_count))

        # Device
        self.device = Device()

        self.mode = mode

        # Template matcher
        self.tm = TM(feed=partial(self.device.capture, method=Device.FROM_SHELL), mode=self.mode)

        # Target quest
        path = Path(quest).absolute()
        self.tm.load_image(path, name='quest')

        if isinstance(friend, str):
            friend = [friend]

        # Count of expected friend servants
        self.friend_count = len(friend)
        logger.info('Friend count is {}.'.format(self.friend_count))

        for fid in range(self.friend_count):
            path = Path(friend[fid]).absolute()
            self.tm.load_image(path, name='f_{}'.format(fid))

        # AP strategy
        self.ap = ap
        logger.info('AP strategy is {}.'.format(self.ap))

        self.threshold = threshold

        # Load button coords from config
        btn_path = Path(__file__).absolute().parent / 'config' / 'buttons.json'
        with open(btn_path) as f:
            self.buttons = json.load(f)

        logger.debug('Bot initialized.')

    def __button(self, btn):
        """
        Return the __button coords and size.

        :param btn: the name of __button
        :return: (x, y, w, h)
        """
        btn = self.buttons[btn]
        return btn['x'], btn['y'], btn['w'], btn['h']

    def __swipe(self, track):
        """
        Swipe in given track.

        :param track:
        :return:
        """
        x1, y1, x2, y2 = map(lambda x: x + randint(-5, 5), self.buttons['swipe'][track])
        self.device.swipe((x1, y1), (x2, y2))

    def __find_and_tap(self, im: str, threshold: float = None) -> bool:
        """
        Find the given image on screen and tap.

        :param im: the name of image
        :param threshold: the matching threshold
        :return: whether successful
        """
        x, y = self.tm.find(im, threshold=threshold)
        if (x, y) == (-1, -1):
            logger.warning('Failed to find image {} on screen.'.format(im))
            return False
        w, h = self.tm.getsize(im)
        return self.device.tap_rand(x, y, w, h)

    def __exists(self, im: str, threshold: float = None) -> bool:
        """
        Check if a given image exists on screen.

        :param im: the name of the image
        :param threshold: threshold of matching
        """
        return self.tm.exists(im, threshold=threshold)

    def __wait(self, sec):
        """
        Wait some seconds and update the screen feed.

        :param sec: the seconds to wait
        """
        logger.debug('Sleep {} seconds.'.format(sec))
        sleep(sec)
        self.tm.update_screen()

    def __wait_until(self, im: str):
        """
        Wait until the given image appears. Useful when try to use skills, etc.
        """
        logger.debug("Wait until image '{}' appears.".format(im))
        self.tm.update_screen()
        while not self.__exists(im):
            self.__wait(INTERVAL_SHORT)
            if self.__exists('reconnect'):
                self.__find_and_tap('reconnect')

    def __add_stage_handler(self, stage: int, f: Callable):
        """
        Register a handler function to a given stage of the battle.

        :param stage: the stage number
        :param f: the handler function
        """
        assert not self.stage_handlers.get(stage), 'Cannot register multiple function to a single stage.'
        logger.debug('Function {} registered to stage {}'.format(f.__name__, stage))
        self.stage_handlers[stage] = f

    def __get_current_stage(self) -> int:
        """
        Get the current stage in battle.

        :return: current stage. Return -1 if error occurs.
        """
        self.__wait_until('attack')
        max_prob, max_stage = 0.8, -1
        for stage in range(1, self.stage_count + 1):
            im = '{}_{}'.format(stage, self.stage_count)
            prob = self.tm.probability(im)
            if prob > max_prob:
                max_prob, max_stage = prob, stage

        if max_stage == -1:
            logger.error('Failed to get current stage.')
        else:
            logger.debug('Got current stage: {}'.format(max_stage))

        return max_stage

    def __find_friend(self) -> str:
        self.__wait_until('refresh_friends')
        for _ in range(6):
            self.__wait(INTERVAL_SHORT)
            for fid in range(self.friend_count):
                im = 'f_{}'.format(fid)
                if self.__exists(im, threshold=self.threshold):
                    return im
            self.__swipe('friend')
        return ''

    def __enter_battle(self) -> bool:
        """
        Enter the battle.

        :return: whether successful.
        """
        logger.info('Trying to enter the battle')
        self.__wait_until('menu')
        while not self.__find_and_tap('quest', threshold=self.threshold):
            self.__swipe('quest')
            self.__wait(INTERVAL_SHORT)
        self.__wait(INTERVAL_SHORT)

        # no enough AP
        if self.__exists('ap_regen'):
            if not self.ap:
                return False
            else:
                ok = False
                self.__wait(INTERVAL_SHORT)
                for ap_item in self.ap:
                    if ap_item == "apple_bronze":
                        self.device.swipe((640, 400), (640, 250))
                        self.__wait(INTERVAL_SHORT)
                    if self.__find_and_tap(ap_item):
                        self.__wait(INTERVAL_SHORT)
                        if self.__find_and_tap('decide'):
                            logger.info(ap_item + " used")
                            self.__wait_until('refresh_friends')
                            ok = True
                            break
                if not ok:
                    return False

        # look for friend servant
        friend = self.__find_friend()
        while not friend:
            self.__find_and_tap('refresh_friends')
            self.__wait(INTERVAL_SHORT)
            self.__find_and_tap('yes')
            self.__wait(INTERVAL_SHORT)
            friend = self.__find_friend()
        self.__find_and_tap(friend, threshold=self.threshold)
        self.__wait_until('start_quest')
        self.__find_and_tap('start_quest')
        self.__wait(INTERVAL_MID)
        return True

    def __reenter_battle(self) -> bool:
        """
        Enter the battle.

        :return: whether successful.
        """
        logger.info('Trying to re-enter the battle')
        while not self.__find_and_tap('cont'):
            self.__wait(INTERVAL_SHORT)
        self.__wait(INTERVAL_SHORT)

        # no enough AP
        if self.__exists('ap_regen'):
            logger.debug('Insufficient AP')
            if not self.ap:
                return False
            else:
                ok = False
                self.__wait(INTERVAL_SHORT)
                for ap_item in self.ap:
                    if ap_item == "apple_bronze":
                        self.device.swipe((640, 400), (640, 250))
                        self.__wait(INTERVAL_SHORT)
                    if self.__find_and_tap(ap_item):
                        self.__wait(INTERVAL_SHORT)
                        if self.__find_and_tap('decide'):
                            logger.info(ap_item + " used")
                            self.__wait_until('refresh_friends')
                            ok = True
                            break
                if not ok:
                    return False

        # look for friend servant
        friend = self.__find_friend()
        while not friend:
            self.__find_and_tap('refresh_friends')
            self.__wait(INTERVAL_SHORT)
            self.__find_and_tap('yes')
            self.__wait(INTERVAL_SHORT)
            friend = self.__find_friend()
        self.__find_and_tap(friend, threshold=self.threshold)
        self.__wait(INTERVAL_MID)
        return True

    def play_battle(self) -> int:
        """
        Play the battle.

        :return: count of rounds.
        """
        logger.info('Handling the battle')
        stage = 0
        while stage < self.stage_count:
            stage += 1
            self.__wait_until('attack')
            self.stage_handlers[stage]()
            self.__wait(INTERVAL_LONG)
        return stage

    def end_battle(self):
        self.__wait(INTERVAL_SHORT)
        logger.info('Finishing the battle.')
        while not self.__exists('next_step'):
            self.device.tap_rand(640, 360, 50, 50)
            self.__wait(INTERVAL_SHORT)
            if self.__exists('reconnect'):
                self.__find_and_tap('reconnect')

        self.__find_and_tap('next_step')
        self.__wait(INTERVAL_SHORT * 2)
        if self.__exists('next_step'):
            self.__find_and_tap('next_step')
            self.__wait(INTERVAL_SHORT)

        # not send friend application
        self.__wait(INTERVAL_SHORT * 2)
        if self.__exists('not_apply'):
            self.__find_and_tap('not_apply')
        self.__wait(INTERVAL_SHORT)

    def at_stage(self, stage: int):
        """
        A decorator that is used to register a handler function to a given stage of the battle.

        :param stage: the stage number
        """

        def decorator(f):
            self.__add_stage_handler(stage, f)
            return f

        return decorator

    def use_skill(self, servant: int, skill: int, obj=None):
        """
        Use a skill.

        :param servant: the servant id.
        :param skill: the skill id.
        :param obj: the object of skill, if required.
        """
        self.__wait_until('attack')

        x, y, w, h = self.__button('skill')
        x += self.buttons['servant_distance'] * (servant - 1)
        x += self.buttons['skill_distance'] * (skill - 1)
        self.device.tap_rand(x, y, w, h)
        logger.debug('Used skill ({}, {})'.format(servant, skill))
        self.__wait(INTERVAL_SHORT)

        if self.__exists('choose_object'):
            if obj is None:
                logger.error('Must choose a skill object.')
            else:
                x, y, w, h = self.__button('choose_object')
                x += self.buttons['choose_object_distance'] * (obj - 1)
                self.device.tap_rand(x, y, w, h)
                logger.debug('Chose skill object {}.'.format(obj))
        self.__wait(INTERVAL_SHORT)

    def use_master_skill(self, skill: int, obj=None, obj2=None):
        """
        Use a master skill.
        Param `obj` is needed if the skill requires a object.
        Param `obj2` is needed if the skill requires another object (Order Change).

        :param skill: the skill id.
        :param obj: the object of skill, if required.
        :param obj2: the second object of skill, if required.
        """
        self.__wait_until('attack')

        x, y, w, h = self.__button('master_skill_menu')
        self.device.tap_rand(x, y, w, h)
        self.__wait(INTERVAL_SHORT)

        x, y, w, h = self.__button('master_skill')
        x += self.buttons['master_skill_distance'] * (skill - 1)
        self.device.tap_rand(x, y, w, h)
        logger.debug('Used master skill {}'.format(skill))
        self.__wait(INTERVAL_SHORT)

        if self.__exists('choose_object'):
            if obj is None:
                logger.error('Must choose a master skill object.')
            elif 1 <= obj <= 3:
                x, y, w, h = self.__button('choose_object')
                x += self.buttons['choose_object_distance'] * (obj - 1)
                self.device.tap_rand(x, y, w, h)
                logger.debug('Chose master skill object {}.'.format(obj))
            else:
                logger.error('Invalid master skill object.')
        elif self.__exists('order_change'):
            if obj is None or obj2 is None:
                logger.error('Must choose two objects for Order Change.')
            elif 1 <= obj <= 3 and 4 <= obj2 <= 6:
                x, y, w, h = self.__button('change')
                x += self.buttons['change_distance'] * (obj - 1)
                self.device.tap_rand(x, y, w, h)

                x += self.buttons['change_distance'] * (obj2 - obj)
                self.device.tap_rand(x, y, w, h)
                logger.debug('Chose master skill object ({}, {}).'.format(obj, obj2))

                self.__find_and_tap('change')
                logger.debug('Order Change')
            else:
                logger.error('Invalid master skill object.')

        self.__wait(INTERVAL_SHORT)

    def attack(self, cards: list):
        """
        Tap attack __button and choose three cards.

        1 ~ 5 stands for normal cards, 6 ~ 8 stands for noble phantasm cards.

        :param cards: the cards id, as a list

        """
        assert len(cards) == 3, 'Number of cards must be 3.'
        assert len(set(cards)) == 3, 'Cards must be distinct.'
        self.__wait_until('attack')
        self.__find_and_tap('attack')
        self.__wait(INTERVAL_SHORT * 2)
        for card in cards:
            if 1 <= card <= 5:
                x, y, w, h = self.__button('card')
                x += self.buttons['card_distance'] * (card - 1)
                self.device.tap_rand(x, y, w, h)
            elif 6 <= card <= 8:
                x, y, w, h = self.__button('noble_card')
                x += self.buttons['card_distance'] * (card - 6)
                self.device.tap_rand(x, y, w, h)
            else:
                logger.error('Card number must be in range [1, 8]')
        logger.debug('Attack.')

    def run(self, max_loops: int = 999):
        """
        Start the bot.

        :param max_loops: the max number of loops.
        """
        count = 0
        enter_flag = 0
        starttime = time()
        battlestart = time()
        if not self.__enter_battle():
            logger.info('Quit...')
            enter_flag = 1
        if enter_flag == 0:
            rounds = self.play_battle()
            self.end_battle()
            count += 1
            battleend = time()
            logger.info(
                '{}-th Battle complete. {} rounds played. Time: {}'.format(count, rounds, battleend - battlestart))
        while (count < max_loops) and (enter_flag == 0):
            battlestart = time()
            if not self.__reenter_battle():
                logger.info('Quit...')
                break
            rounds = self.play_battle()
            self.end_battle()
            count += 1
            battleend = time()
            logger.info(
                '{}-th Battle complete. {} rounds played. Time: {}'.format(count, rounds, battleend - battlestart))

        endtime = time()
        logger.info(
            '{} Battles played.\nTotal time: {} sec, average time: {} sec\nEnd'.format(count, endtime - starttime,
                                                                                       (endtime - starttime) / count))


class AssistBot:
    def __init__(self, n_iter, mode: int = 0,
                 threshold: float = 0.98):
        self.device = Device()
        self.mode = mode
        self.n_iter = n_iter
        self.threshold = threshold
        self.tm = TM(feed=partial(self.device.capture, method=Device.FROM_SHELL), mode=self.mode)

    def __find_and_tap(self, im: str, threshold: float = 0.97) -> bool:
        """
        Find the given image on screen and tap.

        :param im: the name of image
        :param threshold: the matching threshold
        :return: whether successful
        """
        x, y = self.tm.find(im, threshold=threshold)
        if (x, y) == (-1, -1):
            logger.warning('Failed to find image {} on screen.'.format(im))
            return False
        w, h = self.tm.getsize(im)
        return self.device.tap_rand(x, y, w, h)

    def __exists(self, im: str, threshold: float = 0.97) -> bool:
        """
        Check if a given image exists on screen.

        :param im: the name of the image
        :param threshold: threshold of matching
        """
        return self.tm.exists(im, threshold=threshold)

    def __wait_until(self, im: str):
        """
        Wait until the given image appears. Useful when try to use skills, etc.
        """
        logger.debug("Wait until image '{}' appears.".format(im))
        self.tm.update_screen()
        while not self.__exists(im):
            self.__wait(INTERVAL_SHORT)
            if self.__exists('reconnect'):
                self.__find_and_tap('reconnect')

    def __wait(self, sec):
        """
        Wait some seconds and update the screen feed.

        :param sec: the seconds to wait
        """
        logger.debug('Sleep {} seconds.'.format(sec))
        sleep(sec)
        self.tm.update_screen()

    def __find_exp(self, length):
        for eid in range(length):
            im = 'e_{}'.format(eid)
            if self.__exists(im, threshold=self.threshold):
                return im

    def sort_mailbox(self, expstr=None):
        if expstr is None:
            expstr = ["exp_1.png"]
        if len(expstr) >= 1:
            explength = len(expstr)
            for eid in range(explength):
                path = Path(expstr[eid]).absolute()
                self.tm.load_image(path, name='e_{}'.format(eid))
        else:
            return -1
        self.__wait_until('close1')
        start = time()
        if explength > 0:
            counter = 0
            for _ in range(9999):
                exp = self.__find_exp(explength)
                if not exp:
                    self.device.swipe((640, 650), (640, 250))
                    counter += 1
                    logger.info("Counter: {} .".format(counter))
                    self.__wait(0.2)
                else:
                    self.__find_and_tap(exp, threshold=self.threshold)
                    self.__wait(INTERVAL_SHORT)
                if counter >= self.n_iter:
                    end = time()
                    logger.info("Time: {} sec.".format(end - start))
                    return 0

    def drawcard(self):
        start = time()
        i = 0
        for i in range(self.n_iter):
            self.__wait_until('draw10cards')
            self.__find_and_tap('draw10cards', self.threshold)
            self.__wait(INTERVAL_SHORT)
            if self.__find_and_tap('decide1', self.threshold):
                self.__wait(INTERVAL_SHORT * 3)
                self.device.tap_rand(20, 700, 10, 10)
                logger.info("{}-th draw".format(i + 1))
                self.__wait(INTERVAL_SHORT * 2)
                self.device.tap_rand(20, 700, 10, 10)
            else:
                break
        end = time()
        logger.info("{}-th draw. Time: {} sec.".format(i + 1, end - start))

    def drawreward(self):
        i = 0
        self.__wait_until('menu')
        start = time()
        while i < self.n_iter:
            if self.__exists('0_300', self.threshold):
                end = time()
                logger.info("{}-th pool. Time: {} sec.".format(i + 1, end - start))
                i += 1
                self.__find_and_tap('reset', 0.9)
                self.__wait_until('confirm')
                self.__find_and_tap('confirm', 0.9)
                self.__wait_until('close')
                self.__find_and_tap('close', 0.9)
                start = time()
                continue
            self.__wait(INTERVAL_SHORT)
            self.device.tap_rand(330, 445, 10, 10)
