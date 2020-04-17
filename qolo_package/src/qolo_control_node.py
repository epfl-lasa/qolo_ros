#! /usr/bin/env python

import HighPrecision_ADDA_Double as converter
import time
import math
from itertools import groupby
# import threading
# import RPi.GPIO as GPIO
import numpy as np
import array as arr
# from scipy.signal import butter, lfilter, freqz
# import matplotlib.pyplot as plt
import heapq
import logging
from logging import handlers
import mraa
import signal
import datetime

import rospy
import threading

from std_msgs.msg import String, Bool, Float32MultiArray, Float32, Int32MultiArray
from std_msgs.msg import MultiArrayLayout, MultiArrayDimension 

from rds_network_ros.srv import *

# IMporting libraries for remote web control
import re
import os.path
import tornado.httpserver
import tornado.websocket
import tornado.ioloop
import tornado.web

# FLAG for fully manual control (TRUE) or shared control (FALSE)
#Tonado server port
PORT = 8080

JOYSTICK_MODE = True
MANUAL_MODE = False
threadLock = threading.Lock()
FLAG_debug = True
Stop_Thread_Flag = False

conv = converter.AD_DA()

# coefficient for vmax and wmax(outout curve)
forward_coefficient = 1
left_turning_coefficient = 1
right_turning_coefficient = 1
backward_coefficient = 0.5

# Global Constatns for Communication
# DAC0 --> Left Wheel Velocity
# DAC1 --> Right Wheel Velocity
# DAC2 --> Enable Qolo Motion
THRESHOLD_V = 1500;
ZERO_V = 2650;
High_DAC = 5000;
MBED_Enable = mraa.Gpio(36) #11 17
MBED_Enable.dir(mraa.DIR_OUT)

GEAR = 12.64
DSITANCE_CW = 0.548/2  # DSITANCE_CW bettween two wheels
RADIUS = 0.304/2 # meter

MaxSpeed = 1.5 # max Qolo speed: 1.51 m/s               --> Equivalent to 5.44 km/h
MinSpeed = MaxSpeed*backward_coefficient
MaxAngular = 4.124
W_ratio = 4 # Ratio of the maximum angular speed (232 deg/s)

Max_motor_v = (MaxSpeed/ (RADIUS*(2*np.pi))) *60*GEAR # max motor speed: 1200 rpm

# Setting for the RDS service
max_linear = MaxSpeed;
min_linear = -MinSpeed;
absolute_angular_at_min_linear = 0.;
absolute_angular_at_max_linear = 0.;
absolute_angular_at_zero_linear = MaxAngular/W_ratio;
linear_acceleration_limit = 1.1
angular_acceleration_limit = 1.5
feasible = 0
Output_V = 0.;
Output_W = 0.;
last_v = 0.;
last_w = 0.;
cycle=0.
y_coordinate_of_reference_point_for_command_limits = 0.5;
weight_scaling_of_reference_point_for_command_limits = 0.;
tau = 2.;
delta = 0.10;
clearance_from_axle_of_final_reference_point = 0.15;

last_msg = 0.
Command_V = 2500
Command_W = 2500
Comand_DAC0 = 0
Comand_DAC1 = 0
Send_DAC0 = 0
Send_DAC1 = 0 
# rpm_L = 0;
# rpm_R = 0;

# Global variables for logging
DA_time = 0.
RDS_time = 0.
Compute_time = 0. 
FSR_time = 0.
User_V = 0.;
User_W = 0.;
Out_CP = 0.;
Out_F = 0.;
t1=0.
t2=0.

counter1 = 0
number = 100

# real zero point of each sensor
a_zero, b_zero, c_zero, d_zero, e_zero, f_zero, g_zero, h_zero = 305.17, 264.7, 441.57, 336.46, 205.11, 441.57, 336.46, 205.11

# FsrZero = arr.array('d',[200.1 305.17, 264.7, 441.57, 336.46, 205.11, 441.57, 336.46, 205.11 200.1])
# FsrZero = np.array([100.1, 305.17, 264.7, 441.57, 336.46, 205.11, 150.57, 160.46, 150.11, 200.1])
# FsrZero = np.array([304.5, 298.99, 202.69, 405.66, 294.8, 296.8, 334.01, 282.98, 250.73, 208.32])
# Calibration Diego
# FsrZero = np.array([304.5, 298.99, 268.69, 441.66, 416.8, 305.8, 334.01, 202.98, 250.73, 220.32])
FsrZero = np.array([433.0, 1227.0, 803.0, 314.0, 906.0, 930.0, 1047.0, 195.0, 237.0, 159.0])
# default value for pre-configuration
# k1, k2, k3, k4, k5, k6, k7, k8 =    0.63, 1.04, 0.8, 0.57, 0.63, 0.8, 0.57, 0.63 # 2.48, 0.91, 1.59, 1.75, 1.46
# FsrK = np.array([0., 0.63, 1.04, 0.8, 0.57, 0.63, 0.8, 1.04, 0.7, 0.])
FsrK = np.array([0.0, 1.03, 1.07, 1.0, 1.0, 1.0, 1.0, 1.2, 1.35, 0.0])
# Vector input for all sensor data
# Xin = np.zeros((10))
Xin = np.array([0.0, 0., 0., 0., 0., 0., 0., 0., 0., 0.])
Xin_temp = np.array([0.0, 0., 0., 0., 0., 0., 0., 0., 0., 0.])
ComError = 0
RemoteE = 0

# # coefficient for calculate center of pressure: ox
Rcenter = np.array([0., -2.5, -1.875, -1.25, -0.625, 0.625, 1.25, 1.875, 2.5, 0.])

# classification point for center of pressure ox(calibration needed)
pl2, pl1, pr1, pr2 = -1.5, -0.7, 0.7, 1.5
# -1.72, 0.075, 1.455, 1.98 
# -2.42, 0.67, 1.27, 1.82  
# -0.97, -0.2, 0.2, 1.17

AA = []
BB = []
CC = []
DD = []
EE = []
FF = []
GG = []
HH = []
OX = []


level_relations = {
        # 'debug':logging.DEBUG,
        'info':logging.INFO,
        # 'warning':logging.WARNING,
        # 'error':logging.ERROR,
        # 'crit':logging.CRITICAL
    }

# Tornado Folder Paths
settings = dict(
    template_path = os.path.join(os.path.dirname(__file__), "templates"),
    static_path = os.path.join(os.path.dirname(__file__), "static")
    )


class MainHandler(tornado.web.RequestHandler):
  def get(self):
     print ("[HTTP](MainHandler) User Connected.")
     self.render("joy.html")

    
class WSHandler(tornado.websocket.WebSocketHandler):
  def open(self):
    print ('[WS] Connection was opened.')
 
  def on_message(self, message):
    print ('[WS] Incoming message:'), message
    print (type(message)) # result = re.findall(r"[-+]?\d*\.\d+|\d+", message)
    result = re.findall(r"[-\d]+", message) 
    # print (result)
    Output = [((float(i)/100)) for i in result]
    Comand_DAC0, Comand_DAC1 = transformTo_Lowevel((Output[1]*0.5), (Output[0]*0.5))

    print ('Joystick =', Output[0]*2, Output[1]*0.5)
    write_DA(Comand_DAC0, Comand_DAC1)
    # # Comand_DAC0 = Output[0]
    # # Comand_DAC1 = Output[1]
    # if Comand_DAC0 < 4500:
    #     Send_DAC0 = Comand_DAC0
    # else:
    #     Send_DAC0 = 4500
    # if Comand_DAC0 < 4500:
    #     Send_DAC1 = Comand_DAC1
    # else:
    #     Send_DAC1 = 4500
    # conv.SET_DAC0(Send_DAC0, conv.data_format.voltage)
    # conv.SET_DAC1(Send_DAC1, conv.data_format.voltage)
    # conv.SET_DAC2(High_DAC, conv.data_format.voltage)
    RemoteE = conv.ReadChannel(7, conv.data_format.voltage)
    ComError = conv.ReadChannel(6, conv.data_format.voltage)
    if ComError<=THRESHOLD_V:
        write_DA(ZERO_V, ZERO_V)
        enable_mbed()
        
    if RemoteE >= THRESHOLD_V:
        print('RemoteE', RemoteE)
        FlagEmergency=True
        last_msg=0.
        # threadLock.acquire()
        while FlagEmergency:
            pub_emg.publish(FlagEmergency)
            conv.SET_DAC2(0, conv.data_format.voltage)
            conv.SET_DAC0(ZERO_V, conv.data_format.voltage)
            conv.SET_DAC1(ZERO_V, conv.data_format.voltage)
            ResetFSR = conv.ReadChannel(5, conv.data_format.voltage)
            if ResetFSR >= THRESHOLD_V:
                print('ResetFSR ', ResetFSR)
                FlagEmergency=False
                pub_emg.publish(FlagEmergency)
                enable_mbed()
                last_msg=0.
            time.sleep(0.1)
    print ('Output =', Comand_DAC0, Comand_DAC1)

  def on_close(self):
    conv.SET_DAC2(0, conv.data_format.voltage)
    conv.SET_DAC0(ZERO_V, conv.data_format.voltage)
    conv.SET_DAC1(ZERO_V, conv.data_format.voltage)
    print ('[WS] Connection was closed.')

application = tornado.web.Application([
  (r'/', MainHandler),
  (r'/ws', WSHandler),
  # (r"/(.*)", tornado.web.StaticFileHandler,
  #            {"path": r"{0}".format(os.path.join(os.path.dirname(__file__), "static"))}),
  ], **settings)


class FSR_thread (threading.Thread):
    def __init__(self, name, counter):
        threading.Thread.__init__(self)
        self.threadID = counter
        self.name = name
        self.counter = counter
    def run(self):
        # print("\nStarting " + self.name)
        # Acquire lock to synchronize thread
        while True:
            have_it = threadLock.acquire()
            try:
                if have_it:
                    read_FSR()
                    threadLock.release()
                    have_it = 0
                    user_input_thread()
            finally:
                if have_it:
                    threadLock.release()
                # Release lock for the next thread

            if Stop_Thread_Flag:
                break

        print("Exiting " + self.name)

    def get_id(self): 
        # returns id of the respective thread 
        if hasattr(self, '_thread_id'): 
            return self._thread_id 
        for id, thread in threading._active.items(): 
            if thread is self: 
                return id

    def raise_exception(self): 
        thread_id = self.get_id() 
        res = ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_id, 
              ctypes.py_object(SystemExit)) 
        if res > 1: 
            ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_id, 0) 
            print('Exception raised: Stopped User_input_thread')

# read data from ADDA board
def read_FSR():
    global Xin_temp, RemoteE, ComError
    # Checking emergency inputs
    RemoteE = conv.ReadChannel(7, conv.data_format.voltage)
    ComError = conv.ReadChannel(6, conv.data_format.voltage)
    Xin_temp[0] = float(conv.ReadChannel(5, conv.data_format.voltage))
    Xin_temp[1] = float(conv.ReadChannel(15, conv.data_format.voltage))
    Xin_temp[2] = float(conv.ReadChannel(14, conv.data_format.voltage))
    Xin_temp[3] = float(conv.ReadChannel(13, conv.data_format.voltage))
    Xin_temp[4] = float(conv.ReadChannel(12, conv.data_format.voltage))
    Xin_temp[5] = float(conv.ReadChannel(11, conv.data_format.voltage))
    Xin_temp[6] = float(conv.ReadChannel(10, conv.data_format.voltage))
    Xin_temp[7] = float(conv.ReadChannel(9, conv.data_format.voltage))
    Xin_temp[8] = float(conv.ReadChannel(8, conv.data_format.voltage))
    Xin_temp[9] = float(conv.ReadChannel(4, conv.data_format.voltage))

    # return Xin_temp
# execution command to DAC board based on the output curve
def execution():

    global pl2, pl1, pr1, pr2
    global Command_V, Command_W, Comand_DAC0, Comand_DAC1
    global Xin, FsrZero, FsrK, Out_CP
    
    a = Xin[1]
    b = Xin[2]
    c = Xin[3]
    d = Xin[4]
    e = Xin[5]
    f = Xin[6]
    g = Xin[7]
    h = Xin[8]
    ox = Out_CP

    treshold  = 700 # avoid unstoppable and undistinguishable
    
    forward, backward, left_angle_for, left_angle_turn, right_angle_for, right_angle_turn, left_around, right_around = output(a, b, c, d, e, f, g, h, ox)

    if ox <= pr1 and ox >= pl1 and d >= treshold and e >= treshold:
        Command_V = forward
        Command_W = 2500
        # continue
    # turn an angle
    elif (ox <= pl1 and ox >= pl2) and h <= treshold and (c >= treshold or b >= treshold):
        Command_V = left_angle_for
        Command_W = left_angle_turn
        # continue
    elif (ox >= pr1 and ox <= pr2) and a <= treshold and (f >= treshold or g >= treshold):
        Command_V = right_angle_for
        Command_W = right_angle_turn
        # continue
    # turn around
    elif ox <= pl2 and h <= treshold and (a >= treshold or b >= treshold):
        Command_V = 2500
        Command_W = left_around
        # continue
    elif ox >= pr2 and a<=treshold and (g >= treshold or h >= treshold):
        Command_V = 2500
        Command_W = right_around
        
    # backward
    elif a >= treshold and h >= treshold and d < 300 and e < 300:
        Command_V = backward
        Command_W = 2500
        
    else:
        Command_V = 2500
        Command_W = 2500
        
def user_input_thread():
    global FSR_time, t2, Xin, Xin_temp, FsrZero, FsrK, Out_CP, User_V, User_W, Command_V, Command_W, Read_Flag

    # read_FSR()
    Xin = FsrK* (round(Xin_temp,4) - FsrZero)     # Values in [mV]
    # Calculating the Center of pressure
    ox = np.sum(Rcenter*Xin) / (Xin[1] + Xin[2] + Xin[3] + Xin[4] + Xin[5] + Xin[6] + Xin[7] + Xin[8])
    Out_CP = round(ox, 4)
    # Runs the user input and returns Command_V and Command_W --> in 0-5k scale
    execution()
    motor_v = 2*Max_motor_v*Command_V/5000 - Max_motor_v            # In [RPM]
    motor_w = (2*Max_motor_v/(DSITANCE_CW)*Command_W/5000 - Max_motor_v/(DSITANCE_CW)) / W_ratio # In [RPM]

    # Start lock
    User_V = round(((motor_v/GEAR)*RADIUS)*(np.pi/30),4)
    User_W = round(((motor_w/GEAR)*RADIUS)*(np.pi/30),4)
    # if Stop_Thread_Flag:
    #     break
    
    if FLAG_debug:
        FSR_time = round((time.clock() - t2),4)
        t2 = time.clock()


def enable_mbed():
    # threadLock.acquire()

    MBED_Enable.write(0)
    time.sleep(1)
    MBED_Enable.write(1)
    print("Initiating MBED")
    time.sleep(2)

    StartFlag = 1
    conv.SET_DAC2(High_DAC, conv.data_format.voltage)
    conv.SET_DAC0(ZERO_V, conv.data_format.voltage)
    conv.SET_DAC1(ZERO_V, conv.data_format.voltage)

    ComError = conv.ReadChannel(6, conv.data_format.voltage)    
    while StartFlag:
        print("Waiting MBED_Enable")
        time.sleep(0.5)
        ComError = conv.ReadChannel(6, conv.data_format.voltage)
        print("ComError = ",ComError)
        if ComError>THRESHOLD_V:
            StartFlag=0

    time.sleep(1)  
    # threadLock.release()


# for interruption
def exit(signum, frame):
    # global Stop_Thread_Flag
    # MBED_Enable = mraa.Gpio(36) #11 17
    # MBED_Enable.dir(mraa.DIR_OUT)
    MBED_Enable.write(0)
    conv.SET_DAC2(0, conv.data_format.voltage)
    conv.SET_DAC3(0, conv.data_format.voltage)
    conv.SET_DAC0(0, conv.data_format.voltage)
    conv.SET_DAC1(0, conv.data_format.voltage)
    # Stop_Thread_Flag = True
    # cleanup_stop_thread()

    print('----> You chose to interrupt')
    quit()



### Previous version:
        # MaxSpeed = 5.44 # max Qolo speed: km/h
        # MaxAngularVlocity = MaxSpeed*1000/3600/(DSITANCE_CW/2)
        # Max_motor_v = MaxSpeed*1000/3600/RADIUS/(2*np.pi)*60*GEAR # max motor speed: 1200 rpm

        # speed_L = linear_speed - DSITANCE_CW*angular_speed/2
        # speed_R = linear_speed + DSITANCE_CW*angular_speed/2

        # motor_L = Max_motor_v*speed_L / (MaxSpeed*1000/3600)
        # motor_R = Max_motor_v*speed_R / (MaxSpeed*1000/3600)
        # # print("left wheel = ",motor_v, "right wheel = ",motor_w)

        # # print("left wheel = ",rpm_L, "right wheel = ",rpm_R)
        # Command_L = 5000*motor_L/(2*Max_motor_v) + 2500
        # Command_R = 5000*motor_R/(2*Max_motor_v) + 2500
        # Command_L = round(Command_L, 2)
        # Command_R = round(Command_R, 2)

def transformTo_Lowevel(Desired_V, Desired_W):
    # A function to transform linear and angular velocities to output commands
    # print('received ', Command_V, Command_W)
    global DSITANCE_CW, RADIUS, User_V, User_W, MaxSpeed, GEAR, Max_motor_v

    # These lines should be commented to execute the RDS output
    # motor_v = 2*Max_motor_v*Command_V/5000 - Max_motor_v            # In [RPM]
    # motor_w = (2*Max_motor_v/(DSITANCE_CW)*Command_W/5000 - Max_motor_v/(DSITANCE_CW)) / W_ratio # In [RPM]
    # User_V = round(((motor_v/GEAR)*RADIUS)*(np.pi/30),4)
    # User_W = round(((motor_w/GEAR)*RADIUS)*(np.pi/30),4)

    # Using the desired velocity (linearn adn angular) --> transform to motor speed

    wheel_L = Desired_V - (DSITANCE_CW * Desired_W)    # Output in [m/s]
    wheel_R = Desired_V + (DSITANCE_CW * Desired_W)    # Output in [m/s]
    # print ('Wheels Vel =', wheel_L, wheel_R)

    # motor_v = round(((Desired_V*GEAR)/RADIUS)/(np.pi/30),8) 
    # motor_w = round(((Desired_W*GEAR)/RADIUS)/(np.pi/30),8) 

    # rpm_L = motor_v - DSITANCE_CW*motor_w
    # rpm_R = motor_v + DSITANCE_CW*motor_w
    # Transforming from rad/s to [RPM]
    motor_l = (wheel_L/RADIUS) * GEAR *(30/np.pi)
    motor_r = (wheel_R/RADIUS) * GEAR *(30/np.pi)
    # print ('Motor Vel =', motor_l, motor_r)    
    # Transforming velocities to mV [0-5000]
    Command_L = round( (ZERO_V + 5000*motor_l/2400), 4)
    Command_R = round ( (ZERO_V + 5000*motor_r/2400), 4)
    

    return Command_L, Command_R


def write_DA(Write_DAC0,Write_DAC1):
    global Send_DAC0, Send_DAC1

    # ADC Board output in mV [0-5000]
    if Write_DAC0 > 4500:
        Send_DAC0 = 4500
    elif Write_DAC0 < 500:
        Send_DAC0 = 500
    else:
        Send_DAC0 = Write_DAC0

    if Write_DAC1 > 4500:
        Send_DAC1 = 4500
    elif Write_DAC1 < 500:
        Send_DAC1 = 500
    else:
        Send_DAC1 = Write_DAC1

    # threadLock.acquire()
    conv.SET_DAC0(Send_DAC0, conv.data_format.voltage)
    conv.SET_DAC1(Send_DAC1, conv.data_format.voltage)
    conv.SET_DAC2(High_DAC, conv.data_format.voltage)
    # threadLock.release()


# output curve: Linear/Angular Velocity-Pressure Center
def output(a, b, c, d, e, f, g, h, ox):
    global forward_coefficient, left_turning_coefficient, right_turning_coefficient, backward_coefficient
    #sending value setting
    # static_value = 20
    dynamic_value = max(a,b,c,d,e,f,g,h)
    # drive = dynamic_value - static_value
    drive = dynamic_value

    forward = 2500 + forward_coefficient * drive
    if ox > 0 or ox < 0:
        left_around = 2500 + left_turning_coefficient * drive * ox / abs(ox)
    else:
        left_around = 2500
    if ox > 0 or ox < 0:
        right_around = 2500 + right_turning_coefficient * drive * ox / abs(ox)
    else:
        right_around = 2500

    global pl2, pl1, pr1, pr2

    wl = math.pi / (pl2 - pl1) # w for smooth fucntion: sin(wx)
    fai_l_for = math.pi / 2 - wl * pl1
    fai_l_turn = math.pi / 2 - wl * pl2

    wr = math.pi / (pr2 - pr1) # w for smooth fucntion: sin(wx)
    fai_r_for = math.pi / 2 - wr * pr1
    fai_r_turn = math.pi / 2 - wr * pr2

    left_angle_for = 2500 + forward_coefficient * drive / 2 + forward_coefficient * drive / 2 * math.sin(wl * ox + fai_l_for)
    left_angle_turn = 2500 - left_turning_coefficient * drive / 2 - left_turning_coefficient * drive / 2 * math.sin(wl * ox + fai_l_turn)
    right_angle_for = 2500 + forward_coefficient * drive / 2 + forward_coefficient * drive / 2 * math.sin(wr * ox + fai_r_for)
    right_angle_turn = 2500 + right_turning_coefficient * drive / 2 + right_turning_coefficient * drive / 2 * math.sin(wr * ox + fai_r_turn)

    backward = 2500 - backward_coefficient * drive

    # threshold value for keep safety(beyond this value, the joystick will report an error)
    if forward >= 4800:
        forward = 4800
    if left_angle_for >= 4800:
        left_angle_for = 4800
    if right_angle_for >= 4800:
        right_angle_for = 4800
    if right_around >= 4800:
        right_around = 4800
    if left_around <= 300:
        left_around = 300
    if right_angle_turn >= 4800:
        right_angle_turn = 4800
    if left_angle_turn <= 300:
        left_angle_turn = 300
    if backward <= 800:
        backward = 800

    return forward, backward, left_angle_for, left_angle_turn, right_angle_for, right_angle_turn, left_around, right_around

def rds_service():
    global User_V, User_W, Output_V, Output_W, last_v, last_w, cycle, feasible
    # print "Waiting for RDS Service"

    rospy.wait_for_service('rds_velocity_command_correction')
    # try:
    RDS = rospy.ServiceProxy('rds_velocity_command_correction',VelocityCommandCorrectionRDS)

    request = VelocityCommandCorrectionRDSRequest()

    request.nominal_command.linear = User_V;
    request.nominal_command.angular = User_W;

    request.velocity_limits.max_linear = max_linear;
    request.velocity_limits.min_linear = min_linear;
    request.velocity_limits.abs_angular_at_min_linear = absolute_angular_at_min_linear;
    request.velocity_limits.abs_angular_at_max_linear = absolute_angular_at_max_linear;
    request.velocity_limits.abs_angular_at_zero_linear = absolute_angular_at_zero_linear;
    request.abs_linear_acceleration_limit = linear_acceleration_limit;
    request.abs_angular_acceleration_limit = angular_acceleration_limit;

    request.y_coordinate_of_reference_point_for_command_limits = y_coordinate_of_reference_point_for_command_limits;
    request.weight_scaling_of_reference_point_for_command_limits = weight_scaling_of_reference_point_for_command_limits;
    request.clearance_from_axle_of_final_reference_point = clearance_from_axle_of_final_reference_point;
    request.delta = delta;
    request.tau = tau;
    request.y_coordinate_of_reference_biasing_point = 1.;
    request.weight_of_reference_biasing_point = 0.;

    request.last_actual_command.linear = last_v;
    request.last_actual_command.angular = last_w;

    if cycle<=0.001:
        delta_time = 0.005;
    else:
        delta_time = time.clock() - cycle;

    request.command_cycle_time = delta_time
    request.abs_linear_acceleration_limit = 4;
    request.abs_angular_acceleration_limit = 2;

    response = RDS(request)
    Output_V = round(response.corrected_command.linear,4)
    Output_W = round(response.corrected_command.angular,4)
    feasible = response.feasible

    last_v = Output_V
    last_w = Output_W
    cycle = time.clock()
# print cycle 
# except:
    # Output_V = User_V
    # Output_W = User_W
# print "RDS Service failed"

def mds_service():
    global User_V, User_W, Output_V, Output_W, last_v, last_w, cycle, feasible
    # print "Waiting for RDS Service"

    rospy.wait_for_service('rds_velocity_command_correction')
    # try:
    RDS = rospy.ServiceProxy('rds_velocity_command_correction',VelocityCommandCorrectionRDS)

    request = VelocityCommandCorrectionRDSRequest()

    request.nominal_command.linear = User_V;
    request.nominal_command.angular = User_W;

    request.velocity_limits.max_linear = max_linear;
    request.velocity_limits.min_linear = min_linear;
    request.velocity_limits.abs_angular_at_min_linear = absolute_angular_at_min_linear;
    request.velocity_limits.abs_angular_at_max_linear = absolute_angular_at_max_linear;
    request.velocity_limits.abs_angular_at_zero_linear = absolute_angular_at_zero_linear;
    request.abs_linear_acceleration_limit = linear_acceleration_limit;
    request.abs_angular_acceleration_limit = angular_acceleration_limit;

    request.y_coordinate_of_reference_point_for_command_limits = y_coordinate_of_reference_point_for_command_limits;
    request.weight_scaling_of_reference_point_for_command_limits = weight_scaling_of_reference_point_for_command_limits;
    request.clearance_from_axle_of_final_reference_point = clearance_from_axle_of_final_reference_point;
    request.delta = delta;
    request.tau = tau;
    request.y_coordinate_of_reference_biasing_point = 1.;
    request.weight_of_reference_biasing_point = 0.;

    request.last_actual_command.linear = last_v;
    request.last_actual_command.angular = last_w;

    if cycle==0:
        delta_time = 0.005;
    else:
        delta_time = time.clock() - cycle;

    request.command_cycle_time = delta_time
    request.abs_linear_acceleration_limit = 4;
    request.abs_angular_acceleration_limit = 2;

    response = RDS(request)
    Output_V = round(response.corrected_command.linear,4)
    Output_W = round(response.corrected_command.angular,4)
    feasible = response.feasible

    last_v = Output_V
    last_w = Output_W
    cycle = time.clock()
# print cycle 
# except:
    # Output_V = User_V
    # Output_W = User_W
# print "RDS Service failed"


def joystick_control():
    try:
        http_server = tornado.httpserver.HTTPServer(application)
        http_server.listen(PORT)
        main_loop = tornado.ioloop.IOLoop.instance()

        print ("Tornado Server started")
        main_loop.start()

    except:
        print ("Exception triggered - Tornado Server stopped.")
        # GPIO.cleanup()

def control():
    global A1, B1, C1, D1, E1, F1, G1, H1
    # global r1, r2, r3, r4, r5, r6, r7, r8
    global Rcenter
    global Command_V, Command_W, Comand_DAC0, Comand_DAC1, User_V, User_W, Output_V, Output_W
    global counter1
    global DA_time, RDS_time, Compute_time, FSR_time
    
    # Replace with a node subsription
    global Xin, Xin_temp, FsrZero, FsrK, Out_CP
    if FLAG_debug:
        t1 = time.clock()

    if JOYSTICK_MODE:
        read_Joystick()
    else:
        read_FSR()

    if FLAG_debug:
        FSR_time = round((time.clock() - t1),4)
        t1 = time.clock()
    # FSR Inputs calibration: 
    Xin = FsrK * (Xin_temp - FsrZero)     # Values in [mV]
    for i in range (0,10):
        if Xin[i] < 0.:
            Xin[i] = 0.

    # Calculating the Center of pressure
    ox = np.sum(Rcenter*Xin) / (Xin[1] + Xin[2] + Xin[3] + Xin[4] + Xin[5] + Xin[6] + Xin[7] + Xin[8])
    if math.isnan(ox):
        ox = 0.
    Out_CP = round(ox, 4);
    execution()  # Runs the user input with Out_CP and returns Command_V and Command_W --> in 0-5k scale
    motor_v = 2*Max_motor_v*Command_V/5000 - Max_motor_v            # In [RPM]
    motor_w = (2*Max_motor_v/(DSITANCE_CW)*Command_W/5000 - Max_motor_v/(DSITANCE_CW)) / W_ratio # In [RPM]
    User_V = round(((motor_v/GEAR)*RADIUS)*(np.pi/30),4)
    User_W = round(((motor_w/GEAR)*RADIUS)*(np.pi/30),4)
    
    if FLAG_debug:
        t1 = time.clock()
    
    
    if MANUAL_MODE:
        Output_V = User_V
        Output_W = User_W
    else:
        rds_service()


    if FLAG_debug:
        RDS_time = round((time.clock() - t1),4)

    # Debugging the speed controller
    # if counter1 < 20:
    #     Comand_DAC0 = 4000
    #     Comand_DAC1 = 4000
    # else:
    #     Comand_DAC0 = ZERO_V
    #     Comand_DAC1 = ZERO_V
    if FLAG_debug:
        t1 = time.clock()

    if Output_V > MaxSpeed:
        Output_V = MaxSpeed
    elif Output_V < -MinSpeed:
        Output_V = -MinSpeed

    if Output_W > MaxAngular:
        Output_W = MaxAngular
    elif Output_W < -MaxAngular:
        Output_W = -MaxAngular

    Comand_DAC0, Comand_DAC1 = transformTo_Lowevel(Output_V, Output_W)
    write_DA(Comand_DAC0, Comand_DAC1)
    if FLAG_debug:
        DA_time = round((time.clock() - t1),4)
    # print ('FSR_read: %s, FSR_read: %s, FSR_read: %s, FSR_read: %s,')

    counter1 += 1  # for estiamting frequency

def control_node():
    global Comand_DAC0, Comand_DAC1, Send_DAC0, Send_DAC1, Xin
    global RemoteE, ComError
    global DA_time, RDS_time, Compute_time, FSR_time, extra_time, MANUAL_MODE,last_msg
    prevT = 0
    FlagEmergency=False
    # threadLock = threading.Lock()
    # Setting ROS Node
    
    # Call the calibration File
    # load_calibration()
    

    ########### Starting Communication and MBED Board ###########

    ComError = conv.ReadChannel(6, conv.data_format.voltage)
    if ComError<=THRESHOLD_V:
        enable_mbed()

    ########### creating threads  ##############
    # try:
    #     thread_user = FSR_thread("user_input", 1)
    #     Stop_Thread_Flag = False
    #     # thread_user = threading.Thread(target=user_input_thread)
    #     print "FSR Thread started"
    # except:
    #    print "Error: unable to start FSR thread"
    # start input thread
    # thread_user.run(threadLock)
    # thread_user.start()

    ########### Starting ROS Node ###########
    # pub = rospy.Publisher('qolo', String, queue_size=1)
    # rospy.init_node('qolo_control', anonymous=True)
    # rate = rospy.Rate(50) #  20 hz

    ########### Starting ROS Node ###########
    dat_user = Float32MultiArray()
    dat_user.layout.dim.append(MultiArrayDimension())
    dat_user.layout.dim[0].label = 'FSR_read'
    dat_user.layout.dim[0].size = 11
    dat_user.data = [0]*11
    dat_vel = Float32MultiArray()
    dat_vel.layout.dim.append(MultiArrayDimension())
    dat_vel.layout.dim[0].label = 'Velocities: Input - Output'
    dat_vel.layout.dim[0].size = 4
    dat_vel.data = [0]*4

    dat_wheels = Float32MultiArray()
    dat_wheels.layout.dim.append(MultiArrayDimension())
    dat_wheels.layout.dim[0].label = 'Wheels Output'
    dat_wheels.layout.dim[0].size = 2
    dat_wheels.data = [0]*2

    pub_wheels = rospy.Publisher('qolo/wheels', Float32MultiArray, queue_size=1)
    pub_vel = rospy.Publisher('qolo/velocity', Float32MultiArray, queue_size=1)
    pub_emg = rospy.Publisher('qolo/emergency', Bool, queue_size=1)
    pub_user = rospy.Publisher('qolo/user_input', Float32MultiArray, queue_size=1)
    
    pub = rospy.Publisher('qolo', String, queue_size=1)
    rospy.init_node('qolo_control', anonymous=True)
    rate = rospy.Rate(100) #  20 hz

    
    if MANUAL_MODE:
        print('STARTING MANUAL MODE')
    else:
        print('STARTING SHARED CONTROL MODE')


    while not rospy.is_shutdown():
        if JOYSTICK_MODE:
            joystick_control()
            break
        else:
            control()   # Function of control for Qolo
        # # Checking emergency inputs
        # threadLock.acquire()
        RemoteE = conv.ReadChannel(7, conv.data_format.voltage)
        ComError = conv.ReadChannel(6, conv.data_format.voltage)
        # threadLock.release()
        # print('Comerror', ComError)
        if ComError<=THRESHOLD_V:
            enable_mbed()
        if RemoteE >= THRESHOLD_V:
            print('RemoteE', RemoteE)
            FlagEmergency=True
            last_msg=0.
            # threadLock.acquire()
            while FlagEmergency:
                pub_emg.publish(FlagEmergency)
                conv.SET_DAC2(0, conv.data_format.voltage)
                conv.SET_DAC0(ZERO_V, conv.data_format.voltage)
                conv.SET_DAC1(ZERO_V, conv.data_format.voltage)
                ResetFSR = conv.ReadChannel(5, conv.data_format.voltage)
                if ResetFSR >= THRESHOLD_V:
                    print('ResetFSR ', ResetFSR)
                    FlagEmergency=False
                    pub_emg.publish(FlagEmergency)
                    enable_mbed()
                    last_msg=0.
                time.sleep(0.1)
                # threadLock.release()

        cycle_T = time.clock() - prevT
        prevT = time.clock()
        now = datetime.datetime.now()
        current_time = now.strftime("%H:%M:%S")
        RosMassage = "%s %s %s %s %s %s %s %s %s %s %s %s %s %s %s %s %s %s %s %s %s" % (current_time, cycle_T, RDS_time,Xin[0],Xin[1],Xin[2],Xin[3],Xin[4],Xin[5],Xin[6],Xin[7],Xin[8],Xin[9],Out_CP,Send_DAC0, Send_DAC1, User_V, User_W, feasible, Output_V, Output_W)
        # RosMassage = "%s %s %s %s %s %s %s %s" % (cycle_T, RDS_time, DA_time, feasible, User_V, User_W, round(Output_V,4), round(Output_W,4) )
        # RosMassage = "%s %s %s %s %s" % (User_V, User_W, Output_V, Output_W, feasible)
        dat_wheels.data = [Send_DAC0, Send_DAC1]
        dat_vel.data = [last_msg, User_V, User_W, Output_V, Output_W]
        dat_user.data = [Xin[0],Xin[1],Xin[2],Xin[3],Xin[4],Xin[5],Xin[6],Xin[7],Xin[8],Xin[9],Out_CP]
        
        # rospy.loginfo(RosMassage)
        pub_emg.publish(FlagEmergency)
        pub_vel.publish(dat_vel)
        pub_wheels.publish(dat_wheels)
        pub_user.publish(dat_user)

        # rospy.loginfo(dat_user)
        rospy.loginfo(RosMassage)
        pub.publish(RosMassage)
        rate.sleep()

    # Stop_Thread_Flag = True
    # thread_user.raise_exception()
    # thread_user.join()

# for interruption
signal.signal(signal.SIGINT, exit)
signal.signal(signal.SIGTERM, exit)
if __name__ == '__main__':
    try:
        control_node()
    except rospy.ROSInterruptException:
        pass
