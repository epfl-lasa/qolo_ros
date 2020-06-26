#!/usr/bin/env python
import rospy
import math
from os.path import expanduser

class RobotMetricsEvaluation:
    def __init__(self, goal_x, goal_y):
        self.goal_x = goal_x
        self.goal_y = goal_y
        self.reached_goal_radius = 1.0
        self.reached_goal_time = None
        self.initial_timestamp = None
        self.mean_velocity = 0.0
        self.duration = 0.0
        self.previous_x = None
        self.previous_y = None

    def print_result(self):
        if self.reached_goal_time == None:
            print ("Did not reach the goal")
        else:
            print ("Time to reach the goal: ", self.reached_goal_time)
        print ("Mean velocity: ", self.mean_velocity)
        with open(expanduser('~/Robot_Metrics_Evaluation.txt'), 'w+') as file:
            if self.reached_goal_time == None:
                file.write("Did not reach the goal\n")
            else:
                file.write('Time to reach the goal: ' + str(self.reached_goal_time) + "\n")
            file.write('Mean velocity: ' + str(self.mean_velocity) + "\n")

    def update(self, position_x, position_y, time_now):
        if self.initial_timestamp == None:
            self.initial_timestamp =time_now

        t = time_now - self.initial_timestamp

        diff_x = position_x - self.goal_x
        diff_y = position_y - self.goal_y
        distance = math.sqrt(diff_y*diff_y + diff_x*diff_x)
        if distance < self.reached_goal_radius and self.reached_goal_time == None:
            self.reached_goal_time = t

        dt = t - self.duration
        w_old = self.duration/(dt + self.duration)
        w_new = dt/(dt + self.duration)

        if self.previous_y != None:
            v_x = (position_x - self.previous_x)/dt
            v_y = (position_y - self.previous_y)/dt
            v = math.sqrt(v_x*v_x + v_y*v_y)
            self.mean_velocity = w_old*self.mean_velocity + w_new*v

        self.previous_x = position_x
        self.previous_y = position_y
        self.duration = t