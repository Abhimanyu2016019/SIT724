import time
from threading import Event
import random

import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
from cflib.crazyflie.log import LogConfig
from cflib.positioning.motion_commander import MotionCommander
from cflib.utils import uri_helper

# This code is to set the Uri for the Crazyflie to connect to the correct radio
URI = uri_helper.uri_from_env(default='radio://0/80/2M/E7E7E7E7E7')
DEFAULT_HEIGHT = 0.5 # This is the default height used (in metres)
OBSTACLE_THRESHOLD = 150.0  # The minimum distance between crazyflie and obstacle 
MOVE_SPEED = 0.2  # meters per step
MOVE_DELAY = 0.5  # seconds per step
MIN_MOVE_DURATION = 4.0  # Minimum duration I want to drone to fly in one direction

flowdeck_ready = Event()
multiranger_ready = Event()


distance = {
    'front': 1000.0,
    'back': 1000.0,
    'left': 1000.0,
    'right': 1000.0
}

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
    distance['front'] = data['range.front']
    distance['back'] = data['range.back']
    distance['left'] = data['range.left']
    distance['right'] = data['range.right']
    print(f"[LOG] F: {distance['front']:.1f} cm | B: {distance['back']:.1f} cm | L: {distance['left']:.1f} cm | R: {distance['right']:.1f} cm")

# This is to setup the log values
def setup_log_ranger(cf):
    lg = LogConfig(name='ranger', period_in_ms=100)
    lg.add_variable('range.front', 'float')
    lg.add_variable('range.back', 'float')
    lg.add_variable('range.left', 'float')
    lg.add_variable('range.right', 'float')
    cf.log.add_config(lg)
    lg.data_received_cb.add_callback(log_ranger_callback)
    lg.start()

# Method used for the crazyflie to roam with obstacle detection
def roam_with_avoidance(scf):
    with MotionCommander(scf, default_height=DEFAULT_HEIGHT) as mc:
        print("[INFO] Taking off and roaming...")
        try:
            while True:
                # Randomize direction order
                directions = ['front', 'left', 'back', 'right']
                random.shuffle(directions)

                moved = False
                for direction in directions:
                    if distance[direction] > OBSTACLE_THRESHOLD:
                        print(f"[MOVE] Moving {direction}...")
                        start_time = time.time()
                        while time.time() - start_time < MIN_MOVE_DURATION:
                            if distance[direction] <= OBSTACLE_THRESHOLD:
                                print(f"[STOP] Obstacle detected in {direction}.")
                                break

                            if direction == 'front':
                                mc.forward(MOVE_SPEED)
                            elif direction == 'back':
                                mc.back(MOVE_SPEED)
                            elif direction == 'left':
                                mc.left(MOVE_SPEED)
                            elif direction == 'right':
                                mc.right(MOVE_SPEED)

                            time.sleep(MOVE_DELAY)
                        moved = True
                        break

                if not moved:
                    print("[WAIT] All directions blocked. Hovering in place.")
                    time.sleep(1)

        except KeyboardInterrupt:
            print("[INFO] Manual interrupt. Landing...")
        finally:
            print("[INFO] Landing...")

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
        setup_log_ranger(scf.cf)
        roam_with_avoidance(scf)
