#!/bin/bash

#----- Colored Terminal -----
NORMAL="\e[0m"
IMP_INFO="\e[34;1m"
IMP_RED="\e[31;1m"
IMP_GREEN="\e[32;1m"

#----- Ctrl-C stop -----
_kill() {
    echo -e "${IMP_RED}Killing all subprocesses${NORMAL}"
    for PID in ${PID_LIST[@]};do
        kill -INT $PID
    done
}
trap "exit" INT TERM ERR
trap _kill EXIT

#----- Get Test Number -----
TEST_NO=0
while [ -d "csv_logs/flon/shared${TEST_NO}" ]; do
   TEST_NO=$(( $TEST_NO + 1 ))
done
LOG_FOLDER="$(pwd)/csv_logs/flon/shared${TEST_NO}"
eval "mkdir -p ${LOG_FOLDER}/compliance"
echo -e "${IMP_INFO}Current Test Number : ${TEST_NO}${NORMAL}"

#----- Launch and record force sensors -----
echo -e "${IMP_INFO}Launching FT Sensors...${NORMAL}"
eval "source /home/qolo/collision_ws/devel/setup.bash"
eval ". /home/qolo/collision_ws/src/rokubimini_interface/run_rokubimini_ros.sh -f ${LOG_FOLDER} &"
PID_LIST+="$! "
sleep 5

#----- Launch Rear Lidar  -----
echo -e "${IMP_INFO}Launching REAR LIDAR...${NORMAL}"
eval ". devel/setup.bash"
eval "roslaunch qolo rear_lidar-cloud.launch &"
PID_LIST+="$! "

sleep 5


#----- Launch and record realsense camera -----
# echo -e "Launching RealSense Camera..."
# eval "source devel/setup.bash"
# eval "roslaunch realsense2_camera rs_qolo_front_test.launch &"
# PID_LIST+="$! "

# sleep 10

# eval "rostopic echo -p /camera_front/accel/sample \
#     &> ${LOG_FOLDER}/imu/accel.csv &"
# PID_LIST+="$! "
# eval "rostopic echo -p /camera_front/gyro/sample \
#     &> ${LOG_FOLDER}/imu/gyro.csv &"
# PID_LIST+="$! "

# sleep 5

#----- Launch qolo control -----
echo -e "${IMP_INFO}Launching QOLO Control Shared Node...${NORMAL}"
# eval "roslaunch qolo compliance_qolo.launch log_folder:=${LOG_FOLDER} &"
eval "roslaunch qolo shared_qolo.launch log_folder:=${LOG_FOLDER} &"
PID_LIST+="$! "
sleep 15

#----- Launch qolo control -----
echo -e "${IMP_INFO}Launching QOLO Odometry Node...${NORMAL}"
# eval "roslaunch qolo compliance_qolo.launch log_folder:=${LOG_FOLDER} &"
eval "rosrun qolo t265_pose_qolo.py "
PID_LIST+="$! "
sleep 3

# Wait till all pids to be finished or killed
echo -e "${IMP_GREEN}All PIDs : ${PID_LIST}${NORMAL}"
for PID in ${PID_LIST[@]};do
    wait $PID
done
