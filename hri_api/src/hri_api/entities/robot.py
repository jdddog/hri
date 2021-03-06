# Copyright (c) 2014, James Diprose
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of the copyright holder nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from hri_msgs.msg import GestureAction, GestureGoal, ExpressionAction, TargetGoal, ExpressionGoal, TargetAction
from hri_msgs.srv import TextToSpeechSubsentenceDuration
import rospy
from .entity import Entity
from hri_api.entities import World
import actionlib
import threading
from hri_api.actions import MultiGoalActionClient
from hri_api.entities import IGesture, IExpression
from hri_msgs.msg import TextToSpeechAction, TextToSpeechGoal
from hri_api.util import *
import abc
from hri_api.query import Query
from actionlib import ClientGoalHandle
import random
from enum import Enum
import re
import xml.etree.ElementTree as ET
from threading import Thread
from std_msgs.msg import String


class IActionHandle():
    __metaclass__ = abc.ABCMeta

    def __init__(self):
        pass

    @abc.abstractmethod
    def cancel_action(self):
        """
        :return:
        """

    @abc.abstractmethod
    def wait_for_result(self):
        """

        :return:
        """


class SingleGoalActionHandle(IActionHandle):
    def __init__(self, action_client):
        IActionHandle.__init__(self)
        self.action_client = action_client

    def cancel_action(self):
        self.action_client.cancel_goal()

    def wait_for_result(self):
        self.action_client.wait_for_result()


class MultiGoalActionHandle(IActionHandle):
    def __init__(self, action_client, goal_handle):
        IActionHandle.__init__(self)
        self.action_client = action_client
        self.goal_handle = goal_handle

    def cancel_action(self):
        self.action_client.cancel_goal(self.goal_handle)

    def wait_for_result(self):
        self.action_client.wait_for_result(self.goal_handle)


class SayToActionHandle(IActionHandle):

    def __init__(self, say_to_plan):
        IActionHandle.__init__(self)
        self.say_to_plan = say_to_plan

    def cancel_action(self):
        self.say_to_plan.cancel()

    def wait_for_result(self):
        self.say_to_plan.wait()


class SayToPlan():
    valid_words_regex = "\w+[']{0,1}\w*[!?,.]{0,1}"
    punctuation = "[' ']"
    spaces = "[,.]"

    def __init__(self, robot):
        self.robot = robot
        self.audience = None
        self.current_gazee = None
        self.sentence = ''
        self.gesture_lookup = {}
        self.expression_lookup = {}
        self.gaze_change_locations = {}

        self.say_ah = None
        self.gaze_ah = None
        self.other_ahs = []
        self.preempt_requested = False
        self.lock = threading.RLock()
        self.thread = None

    def reset(self):
        self.audience = None
        self.current_gazee = None
        self.sentence = ''
        self.gesture_lookup = {}
        self.expression_lookup = {}
        self.gaze_change_locations = {}

        self.say_ah = None
        self.gaze_ah = None
        self.other_ahs = []
        self.preempt_requested = False
        self.lock = threading.RLock()
        self.thread = None

    def wait(self):
        self.thread.join()
        self.robot.wait(self.say_ah)
        self.robot.wait(*self.other_ahs)

    def cancel(self, robot):
        with self.lock:
            self.preempt_requested = True

            if self.say_ah:
                robot.cancel(self.gaze_ah)

            if self.gaze_ah:
                robot.cancel(self.gaze_ah)

            self.robot.cancel(*self.other_ahs)

    def execute(self):
        self.thread = Thread(target=self.__execute)
        self.thread.start()
        return SayToActionHandle(self)

    def __execute(self):
        audience = self.audience

        # Pick a person to gaze at initially
        if isinstance(audience, Entity):
            person = audience

            with self.lock:
                if not self.preempt_requested:
                    self.gaze_ah = self.robot.gaze(person.head)
        else:
            if isinstance(audience, list):
                audience = Query(audience)

            results = audience.sort_increasing(lambda p: p.distance_to(self.robot)).execute()

            if len(results) > 0:
                person = results[0]
                self.current_gazee = person

                with self.lock:
                    if not self.preempt_requested:
                        self.gaze_ah = self.robot.gaze(person.head)

        if self.gaze_ah is not None:
            self.robot.wait(self.gaze_ah)

        with self.lock:
            if not self.preempt_requested:
                self.say_ah = self.robot.say(self.sentence)

    def add_action_handle(self, action_handle):
        self.other_ahs.append(action_handle)

    @staticmethod
    def get_gaze_change_locations(text):
        sentences = re.split("[,.?!]", text)
        gaze_change_locs = {}

        length = 0
        for sentence in sentences:
            length += SayToPlan.num_words(sentence)
            gaze_change_locs[length + 1] = ''

        return gaze_change_locs

    @staticmethod
    def num_words(text):
        return len(re.findall(SayToPlan.valid_words_regex, text))

    @staticmethod
    def get_sentence(text):
        tree = ET.fromstring("<sayto>" + text + "</sayto>")
        text = ""

        for node in tree.iter():
            if node.tag == "sayto":
                if node.text is not None:
                    text += node.text + " "
            else:
                if node.text is not None:
                    text += node.text + " "

                if node.tail is not None:
                    text += node.text + " "

        return text.strip()

    @staticmethod
    def enum_contains(enum, name):
        for e in enum:
            if e.name == name:
                return True

        return False

    def parse_parameters(self, text, audience, expression_enum, gesture_enum, tts_duration_srv):
        self.reset()
        self.audience = audience

        ParamFormatting.assert_types(self.parse_parameters, text, str)
        ParamFormatting.assert_types(self.parse_parameters, audience, Entity, Query)

        # if not is_callable(tts_duration_srv):
        #     raise TypeError("parse_parameters() parameter tts_duration_srv={0} is not callable".format(tts_duration_srv))

        self.sentence = SayToPlan.get_sentence(text)  # Get sentence
        self.gaze_change_locations = SayToPlan.get_gaze_change_locations(self.sentence)

        # Get expressions and gestures
        xml_tree = ET.fromstring("<sayto>" + text + "</sayto>")
        seen_text = ''

        for node in xml_tree.iter():
            if node.tag == "sayto":
                if node.text is not None:
                    seen_text += node.text + " "
            else:
                start_word_i = SayToPlan.num_words(seen_text)

                if node.text is not None:
                    seen_text += node.text + " "

                end_word_i = SayToPlan.num_words(seen_text)

                goal_name = node.tag

                if SayToPlan.enum_contains(expression_enum, goal_name):
                    goal = ExpressionGoal()
                    goal.expression = goal_name
                    goal.intensity = 0.5
                    goal.speed = 0.5

                    if 'intensity' in node.attrib:
                        goal.intensity = float(node.attrib["intensity"])

                    if 'speed' in node.attrib:
                        goal.speed = float(node.attrib["speed"])

                    goal.duration = tts_duration_srv(self.sentence, start_word_i, end_word_i).duration
                    self.expression_lookup[start_word_i] = goal

                elif SayToPlan.enum_contains(gesture_enum, goal_name):
                    goal = GestureGoal()
                    goal.gesture = goal_name

                    if 'target' in node.attrib:     # Check if target is Entity
                        goal.target = node.attrib["target"]
                    else:
                        raise AttributeError('Please specify a target attribute for {0} gesture'.format(goal_name))

                    goal.duration = tts_duration_srv(self.sentence, start_word_i, end_word_i).duration
                    self.gesture_lookup[start_word_i] = goal

                else:
                    raise TypeError('No gesture or expression called: {0}'.format(goal_name))

                if node.tail is not None:
                    seen_text += node.tail + " "


class Robot(Entity):
    ENTITY_TYPE = 'robot'

    def __init__(self, expression_enum, gesture_enum):
        Entity.__init__(self, Robot.ENTITY_TYPE, Robot.ENTITY_TYPE + str(1), None)
        self.expression_enum = expression_enum
        self.gesture_enum = gesture_enum

        self.gaze_client = actionlib.SimpleActionClient('gaze', TargetAction)
        self.gaze_found = False

        self.expression_client = MultiGoalActionClient('expression', ExpressionAction)
        self.expression_found = False

        self.tts_client = actionlib.SimpleActionClient('text_to_speech', TextToSpeechAction)
        self.tts_found = False

        self.gesture_client = MultiGoalActionClient('gesture', GestureAction)
        self.gesture_found = False

        self.tts_duration_srv = rospy.ServiceProxy('tts_subsentence_duration', TextToSpeechSubsentenceDuration)
        self.tts_duration_found = False

        self.event = None
        self.action_handles = []
        self.say_to_plan = SayToPlan(self)
        self.gaze_ah = None
        self.say_ah = None

        self.lock = threading.RLock()
        self.listen_cb = None
        self.listen_sub = None

    def register_listen_callback(self, callback):
        self.listen_cb = callback
        self.listen_sub = rospy.Subscriber("itf_listen", String, self.__listen, queue_size=10)

    def __listen(self, msg):

        if msg.data == 'BADINPUT':
            text = None
        else:
            text = msg.data

        self.listen_cb(text)

    # Text to speech
    def say(self, text):
        if not self.tts_found:
            self.wait_for_action_servers(self.tts_client)
            self.tts_found = True

        ParamFormatting.assert_types(self.say, text, str)
        goal = TextToSpeechGoal()
        goal.sentence = text
        self.tts_client.send_goal(goal, feedback_cb=self.say_feedback, done_cb=self.say_done)
        ah = SingleGoalActionHandle(self.tts_client)
        self.say_ah = ah
        self.add_action_handle(ah)
        return ah

    def say_and_wait(self, text):
        self.say(text)
        self.tts_client.wait_for_result()

    def say_done(self, state, result):
        with self.lock:
            self.remove_action_handle(self.say_ah)
            self.say_ah = None

    # Gaze
    def gaze(self, target, speed=0.5):
        if not self.gaze_found:
            self.wait_for_action_servers(self.gaze_client)
            self.gaze_found = True

        ParamFormatting.assert_types(self.gaze, target, Entity)
        ParamFormatting.assert_types(self.gaze, speed, float)
        ParamFormatting.assert_range(self.gaze, speed, 0.0, 1.0)

        World().add_to_world(target)
        goal = TargetGoal()
        goal.target = target.get_id()
        goal.speed = speed
        goal.acceleration = 0.3

        self.gaze_client.send_goal(goal, feedback_cb=self.gaze_feedback, done_cb=self.gaze_done)
        ah = SingleGoalActionHandle(self.gaze_client)
        self.gaze_ah = ah
        self.add_action_handle(ah)
        return ah

    def gaze_and_wait(self, target, speed=0.5, timeout=rospy.Duration()):
        self.gaze(target, speed)
        self.gaze_client.wait_for_result(timeout)

    def gaze_feedback(self, feedback):
        pass

    def gaze_done(self, state, result):
        with self.lock:
            self.remove_action_handle(self.gaze_ah)
            self.gaze_ah = None

    # Blinking
    def blink(self, blink_duration, blink_rate_mean, blink_rate_sd):
        """
        :param blink_duration:
        :param blink_rate_mean:
        :param blink_rate_sd:
        :return:
        """
        raise NotImplementedError("Please implement the blink method")

    # Facial expressions
    def expression(self, expression, intensity=None, speed=None, duration=None):
        if not self.expression_found:
            self.wait_for_action_servers(self.expression_client)
            self.expression_found = True

        ParamFormatting.assert_types(self.expression, expression, IExpression)

        goal = ExpressionGoal()
        goal.expression = expression.name

        if intensity is None:
            goal.intensity = -1
        else:
            ParamFormatting.assert_types(self.expression, intensity, float)
            ParamFormatting.assert_range(self.expression, intensity, 0.0, 1.0)
            goal.intensity = intensity

        if speed is None:
            goal.speed = -1
        else:
            ParamFormatting.assert_types(self.expression, speed, float)
            ParamFormatting.assert_range(self.expression, speed, 0.0, 1.0)
            goal.speed = speed

        if duration is None:
            goal.duration = -1
        else:
            ParamFormatting.assert_types(self.expression, duration, float)
            ParamFormatting.assert_greater_than(self.expression, duration, 0.0)
            goal.duration = duration

        gh = self.expression_client.send_goal(goal, done_cb=self.expression_done)
        ah = MultiGoalActionHandle(self.expression_client, gh)
        self.add_action_handle(ah)
        return ah

    def expression_and_wait(self, expression, intensity=None, speed=None, duration=None, timeout=rospy.Duration()):
        ah = self.expression(expression, intensity, speed, duration)
        self.expression_client.wait_for_result(ah.goal_handle, timeout)

    def expression_done(self, goal_handle):
        with self.lock:
            ah = self.get_action_handle(goal_handle)
            self.remove_action_handle(ah)

    # Gestures
    def gesture(self, gesture, target=None, duration=None):
        if not self.gesture_found:
            self.wait_for_action_servers(self.gesture_client)
            self.gesture_found = True

        ParamFormatting.assert_types(self.gesture, gesture, IGesture)

        goal = GestureGoal()
        goal.gesture = gesture.name

        if target is None:
            goal.target = ''
        else:
            World().add_to_world(target)
            ParamFormatting.assert_types(self.gesture, target, Entity)
            goal.target = target.get_id()

        if duration is None:
            goal.duration = -1
        else:
            ParamFormatting.assert_types(self.expression, duration, float)
            ParamFormatting.assert_greater_than(self.expression, duration, 0.0)
            goal.duration = duration

        gh = self.gesture_client.send_goal(goal, done_cb=self.gesture_done)

        ah = MultiGoalActionHandle(self.gesture_client, gh)
        self.add_action_handle(ah)
        return ah

    def gesture_and_wait(self, gesture, target=None, duration=None, timeout=rospy.Duration()):
        ah = self.gesture(gesture, target, duration)
        self.gesture_client.wait_for_result(ah.goal_handle, timeout)

    def gesture_done(self, goal_handle):
        with self.lock:
            ah = self.get_action_handle(goal_handle)
            self.remove_action_handle(ah)

    # Speaking, gazing and gesturing simultaneously
    def say_to(self, text, audience):
        if not self.tts_duration_found:
            self.wait_for_services(self.tts_duration_srv)
            self.tts_duration_found = True

        ParamFormatting.assert_types(self.say_to, text, str)
        ParamFormatting.assert_types(self.say_to, audience, Entity, Query, list)

        self.say_to_plan.parse_parameters(text, audience, self.expression_enum, self.gesture_enum, self.tts_duration_srv)

        ah = self.say_to_plan.execute()
        self.add_action_handle(ah)
        return ah

    def say_to_and_wait(self, text, audience):
        ah = self.say_to(text, audience)
        self.wait(ah)

    def say_feedback(self, feedback):
        if feedback.current_word_index in self.say_to_plan.gaze_change_locations:
            if isinstance(self.say_to_plan.audience, Entity):
                person = self.say_to_plan.audience
                self.say_to_plan.current_gazee = person
                self.say_to_plan.gaze_ah = self.gaze(person.head)

            elif isinstance(self.say_to_plan.audience, Query):
                people = self.say_to_plan.audience.execute()

                if len(people) > 1:
                    #if self.say_to_plan.current_gazee in people:
                    #    people.remove(self.say_to_plan.current_gazee)

                    person = random.choice(people)
                    self.say_to_plan.current_gazee = person
                    self.say_to_plan.gaze_ah = self.gaze(person.head)
                elif len(people) == 1:
                    person = people[0]
                    self.say_to_plan.current_gazee = person
                    self.say_to_plan.gaze_ah = self.gaze(person.head)

        if feedback.current_word_index in self.say_to_plan.expression_lookup:
            expression = self.say_to_plan.expression_lookup[feedback.current_word_num]
            ahs = self.do(expression)
            self.say_to_plan.add_action_handle(ahs[0])

        if feedback.current_word_index in self.say_to_plan.gesture_lookup:
            gesture = self.say_to_plan.gesture_lookup[feedback.current_word_index]
            ahs = self.do(gesture)
            self.say_to_plan.add_action_handle(ahs[0])

    def add_action_handle(self, action_handle):
        with self.lock:
            ParamFormatting.assert_types(self.add_action_handle, action_handle, IActionHandle)
            self.action_handles.append(action_handle)

    def get_action_handle(self, goal_handle):
        with self.lock:
            for ah in self.action_handles:
                if isinstance(ah, MultiGoalActionHandle):
                    if ah.goal_handle == goal_handle:
                        return ah

    def remove_action_handle(self, action_handle):
        with self.lock:
            ParamFormatting.assert_types(self.remove_action_handle, action_handle, IActionHandle)
            if action_handle in self.action_handles:
                    self.action_handles.remove(action_handle)

    def do(self, *goals):
        action_handles = []

        with self.lock:
            for goal in goals:
                if isinstance(goal, TextToSpeechGoal):
                    self.tts_client.send_goal(goal)
                    ah = SingleGoalActionHandle(self.tts_client)
                    self.add_action_handle(ah)
                    action_handles.append(ah)

                elif isinstance(goal, TargetGoal):
                    self.gaze_client.send_goal(goal)
                    ah = SingleGoalActionHandle(self.gaze_client)
                    self.add_action_handle(ah)
                    action_handles.append(ah)

                elif isinstance(goal, ExpressionGoal):
                    gh = self.expression_client.send_goal(goal)
                    ah = MultiGoalActionHandle(self.expression_client, gh)
                    self.add_action_handle(ah)
                    action_handles.append(ah)

                elif isinstance(goal, GestureGoal):
                    gh = self.gesture_client.send_goal(goal)
                    ah = MultiGoalActionHandle(self.gesture_client, gh)
                    self.add_action_handle(ah)
                    action_handles.append(ah)
                else:
                    raise TypeError('robot.do parameter goals has a goal with a unsupported type {0}, at index {1}. Should be one of: TextToSpeechGoal, TargetGoal, ExpressionGoal or GestureGoal'.format(type(goal), goals.index(goal)))

        return action_handles

    # Wait for one or more goals to finish
    def wait(self, *action_handles):
        for ah in action_handles:
            ParamFormatting.assert_types(self.wait, ah, IActionHandle)
            ah.wait_for_result()
            self.remove_action_handle(action_handle=ah)

    # Cancel one or more goals
    def cancel(self, *action_handles):
        for ah in action_handles:
            ParamFormatting.assert_types(self.wait, ah, IActionHandle)
            ah.cancel_action()
            self.remove_action_handle(action_handle=ah)

    def default_tf_frame_id(self):
        raise NotImplementedError("Please implement this method")

    def tf_frame_id(self):
        raise NotImplementedError("Please implement this method")

    # Wait for a period of time
    def wait_for_period(self, period):
        self.event = threading.Event()
        self.event.wait(timeout=period)

    def cancel_wait_for_period(self):
        if self.event is not None:
            self.event.set()




