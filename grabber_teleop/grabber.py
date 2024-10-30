from bplprotocol import BPLProtocol, PacketID, PacketReader
import time
import sys
import tty
import termios
import serial

# Device IDs and Serial Port setup
wrist_device_id = 0x02
gripper_device_id = 0x01
serial_port_name = '/dev/ttyUSB0'

serial_port = serial.Serial(serial_port_name, baudrate=115200, parity=serial.PARITY_NONE,
                            stopbits=serial.STOPBITS_ONE, timeout=0)

packet_reader = PacketReader()
# Initial settings
wrist_velocity = 1.0
velocity_step = 0.1  # Step to increase/decrease velocity
grip_velocity = 1.0  # 0 for release, 1 for grip
request_timeout = 0.05  # Timeout for request

# Capture keyboard input without enter key press
def getch():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
        if ch == '\x1b':  # Arrow keys are a 3-character sequence starting with '\x1b'
            ch += sys.stdin.read(2)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch

# Send velocity command
def send_velocity(device_id, velocity):
    packet = BPLProtocol.encode_packet(device_id, PacketID.VELOCITY, BPLProtocol.encode_floats([velocity]))
    serial_port.write(packet)

# Check wrist joint position
def request_position(device_id):
    serial_port.write(BPLProtocol.encode_packet(device_id, PacketID.REQUEST, bytes([PacketID.POSITION])))
    start_time = time.time()

    position = None
    while True:
        time.sleep(0.0001)
        try:
            read_data = serial_port.read()
        except BaseException:
            read_data = b''
        if read_data != b'':
            packets = packet_reader.receive_bytes(read_data)
            if packets:
                for packet in packets:
                    read_device_id, read_packet_id, data_bytes = packet
                    if read_device_id == device_id and read_packet_id == PacketID.POSITION:

                        # Decode floats, because position is reported in floats
                        position = BPLProtocol.decode_floats(data_bytes)[0]
                        return position
                if position is not None:
                    break

        # Timeout if no response is seen from the device.
        if time.time() - start_time > request_timeout:
            print("Request for Position timed out")
            break

    time.sleep(0.001)


#Print instructions
print("Control the arm with keys:")
print("Arrow Up: Increase wrist velocity")
print("Arrow Down: Decrease wrist velocity")
print("Arrow Left: Rotate wrist anti-clockwise")
print("Arrow Right: Rotate wrist clockwise")
print("'G': Grip")
print("'R': Release")
print("'Q': Quit")

try:
    while True:
        # Capture keyboard input
        key = getch()

        # Update velocities or states based on key press
        if key == '\x1b[A':  # Arrow Up: increase velocity setting
            wrist_velocity += velocity_step
            wrist_velocity = round(wrist_velocity, 2)
            print(f"Velocity set to: {wrist_velocity}")

        elif key == '\x1b[B':  # Arrow Down: decrease velocity setting
            if wrist_velocity == 0:
                print("Velocity is already set to zero")
                continue
            wrist_velocity -= velocity_step
            wrist_velocity = round(wrist_velocity, 2)
            if wrist_velocity < 0:
                wrist_velocity = 0
            print(f"Velocity set to: {wrist_velocity}")

        elif key == '\x1b[C':  # Arrow Right: rotate wrist right
            if wrist_velocity == 0:
                print("Velocity is set to zero, increase velocity first")
                continue
            else:
                position = request_position(wrist_device_id)
                if position < 0.02:
                    print("Wrist joint is at min joint limit, cannot rotate further")
                    continue
                else:
                    send_velocity(wrist_device_id, -wrist_velocity)
                    print(f"Rotating Wrist clockwise with Velocity: {wrist_velocity}")

        elif key == '\x1b[D':  # Arrow Left: rotate wrist left
            if wrist_velocity == 0:
                print("Velocity is set to zero, increase velocity first")
                continue
            else:
                position = request_position(wrist_device_id)
                if position > 5.6:
                    print("Wrist joint is at max joint limit, cannot rotate further")
                    continue
                else:
                    send_velocity(wrist_device_id, wrist_velocity)
                    print(f"Rotating Wrist anti-clockwise with Velocity: {wrist_velocity}")


        elif key.lower() == 'g':  # Grip
            send_velocity(gripper_device_id, -grip_velocity)
            print("Gripping...")
        elif key.lower() == 'r':  # Release
            send_velocity(gripper_device_id, grip_velocity)
            print("Releasing grip...")
        elif key.lower() == 'q':  # Quit
            print("Exiting...")
            break
        else:
            continue

        time.sleep(0.01)  # Adjust to control command rate

except KeyboardInterrupt:
    print("Interrupted, exiting...")
finally:
    serial_port.close()