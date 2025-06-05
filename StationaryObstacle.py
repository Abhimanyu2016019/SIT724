import time
import logging
from threading import Event

import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
from cflib.crazyflie.log import LogConfig
from cflib.positioning.motion_commander import MotionCommander
from cflib.utils import uri_helper

# This code is to set the Uri for the Crazyflie to connect to the correct radio
URI = uri_helper.uri_from_env(default='radio://0/80/2M/E7E7E7E7E7')
DEFAULT_HEIGHT = 0.5  # This is the default height used (in metres)

# Deck ready flags to show if the hardware is fitted properly
flowdeck_ready = Event()
multiranger_ready = Event()

# Obstacle flags when triggered moves away
front_blocked = False
back_blocked = False
left_blocked = False
right_blocked = False

logging.basicConfig(level=logging.INFO)

#Method to check if the flowdeck and multiranger are present
def param_deck_flow(name, value_str):
    if int(value_str) == 1:
        print("[INFO] Flowdeck is attached.")
        flowdeck_ready.set()
    else:
        print("[ERROR] Flowdeck not detected!")

def param_deck_multiranger(name, value_str):
    if int(value_str) == 1:
        print("[INFO] MultiRanger deck is attached.")
        multiranger_ready.set()
    else:
        print("[ERROR] MultiRanger deck not detected!")

#MEthod to log the values recieved by the multiranger and the flowdeck
def log_ranger_callback(timestamp, data, logconf):
    global front_blocked, back_blocked, left_blocked, right_blocked

    front = data['range.front']
    back = data['range.back']
    left = data['range.left']
    right = data['range.right']

    print("[RANGER]")
    print(f"  Front: {front:.2f} cm")
    print(f"  Back:  {back:.2f} cm")
    print(f"  Left:  {left:.2f} cm")
    print(f"  Right: {right:.2f} cm")
    print(f"  Up:    {data['range.up']:.2f} cm")

    # Set flags true if obstacle < 150 cm
    if front < 150.0: front_blocked = True
    if back < 150.0: back_blocked = True
    if left < 150.0: left_blocked = True
    if right < 150.0: right_blocked = True

def log_flow_callback(timestamp, data, logconf):
    print("[FLOW]")
    print(f"  Pos X: {data['stateEstimate.x']:.2f} m")
    print(f"  Pos Y: {data['stateEstimate.y']:.2f} m")
    print(f"  Pos Z: {data['stateEstimate.z']:.2f} m")
    print(f"  Vel X: {data['stateEstimate.vx']:.2f} m/s")
    print(f"  Vel Y: {data['stateEstimate.vy']:.2f} m/s")
    print("-" * 40)

def setup_log_configs(cf):
    # MultiRanger logging
    log_ranger = LogConfig(name='MultiRanger', period_in_ms=200)
    log_ranger.add_variable('range.front', 'float')
    log_ranger.add_variable('range.back', 'float')
    log_ranger.add_variable('range.left', 'float')
    log_ranger.add_variable('range.right', 'float')
    log_ranger.add_variable('range.up', 'float')
    cf.log.add_config(log_ranger)
    log_ranger.data_received_cb.add_callback(log_ranger_callback)
    log_ranger.start()

    # Flowdeck logging
    log_flow = LogConfig(name='FlowLog', period_in_ms=200)
    log_flow.add_variable('stateEstimate.x', 'float')
    log_flow.add_variable('stateEstimate.y', 'float')
    log_flow.add_variable('stateEstimate.z', 'float')
    log_flow.add_variable('stateEstimate.vx', 'float')
    log_flow.add_variable('stateEstimate.vy', 'float')
    cf.log.add_config(log_flow)
    log_flow.data_received_cb.add_callback(log_flow_callback)
    log_flow.start()

#method for the obstacle detection and hover
def hover(scf):
    global front_blocked, back_blocked, left_blocked, right_blocked
    with MotionCommander(scf, default_height=DEFAULT_HEIGHT) as mc:
        print("[INFO] Hovering... Press Ctrl+C to land manually.")

        try:
            #If obstacle found, moves away from it and resets the flag for continous flow
            while True:
                if front_blocked:
                    print("[AVOID] Obstacle in front (<150cm). Moving backward 0.5m")
                    mc.back(0.1)
                    front_blocked = False

                if back_blocked:
                    print("[AVOID] Obstacle at back (<150cm). Moving forward 0.5m")
                    mc.forward(0.1)
                    back_blocked = False

                if left_blocked:
                    print("[AVOID] Obstacle on left (<150cm). Moving right 0.5m")
                    mc.right(0.1)
                    left_blocked = False

                if right_blocked:
                    print("[AVOID] Obstacle on right (<150cm). Moving left 0.5m")
                    mc.left(0.1)
                    right_blocked = False

                time.sleep(0.01)  # 10ms loop
        except KeyboardInterrupt:
            print("[INFO] Manual stop received. Landing...") #To stop the code


if __name__ == '__main__':
    cflib.crtp.init_drivers()

    with SyncCrazyflie(URI, cf=Crazyflie(rw_cache='./cache')) as scf:
        scf.cf.param.add_update_callback(group='deck', name='bcFlow2', cb=param_deck_flow)
        scf.cf.param.add_update_callback(group='deck', name='bcMultiranger', cb=param_deck_multiranger)

        print("[INFO] Waiting for deck detection...")
        time.sleep(2)

        flowdeck_ready.wait(timeout=5)
        multiranger_ready.wait(timeout=5)

        print("[INFO] Giving time for log TOC to populate...")
        time.sleep(2)

        setup_log_configs(scf.cf)
        hover(scf)
        time.sleep(1)
