from time import sleep
from random import uniform
import threading
import pydirectinput
import cv2
from playsound import playsound
from ctypes import windll
from numpy import array
from PIL import ImageGrab, Image
from win32gui import GetForegroundWindow, GetWindowText, GetWindowRect
from win32api import GetKeyState

WINDOW_NAME = "New World"
VERBOSE = False
DEBUG = False
MASK_BOX = (0.3, 0, 0.7, 1) # L T R B
COMPASS_BOX = (0.30, 0, 0.7, 0.07) # L T R B
AFK_BOX = (0.705, 0.035, .96, 0.175) # L T R B
MOUSE_SHIFT = (26, -13)
LMB = 0x01 # https://docs.microsoft.com/en-us/windows/win32/inputdev/virtual-key-codes
CTRL = 0x11 # https://docs.microsoft.com/en-us/windows/win32/inputdev/virtual-key-codes
F9 = 0x78 # https://docs.microsoft.com/en-us/windows/win32/inputdev/virtual-key-codes
first_pass = True
afk_status = False
mouse_status = False
moved_mouse = [0,0]
pause = True
last_str = ''
states = [
    {   
        'status': 'hook',
        'threshold' : 70.0,
        'result' : 0.0,
        'template': 'templates/color_hook.png', 
        'location': (0,0),
    },
    {   
        'status': 'reel bad',
        'threshold' : 70.0,
        'result' : 0.0,      
        'template': 'templates/color_reel_bad.png',
        'location': (0,0),
    },
    {   
        'status': 'reel good',
        'threshold' : 75.0,
        'result' : 0.0,      
        'template': 'templates/color_reel_good.png',
        'location': (0,0),
    },
    {   
        'status': 'cast',
        'threshold' : 63.0,
        'result' : 0.0,
        'template': 'templates/color_cast.png',
        'location': (0,0),
    },
    {   
        'status': 'bobber',
        'threshold' : 80.0,
        'result' : 0.0,
        'template': 'templates/color_bobber.png',
        'location': (0,0),
    },
]
afk = {   
        'threshold' : 80.0,
        'result' : 0.0,
        'template': 'templates/color_afk.png',
        'location': (0,0),
}
compass = {
        'threshold' : 5,
        'results' : 0.0,
        'image': 'templates/color_map_pin.png',
        'location': (0,0),
}

def state_update(str):
    global last_str
    if str != last_str:
        print(str)
        last_str = str
        
def play_sound():
    playsound('assets/audio/ding-sound-effect_2.mp3')

def get_new_haystack():
    ''' Fetches screen cap and crops out the main window, the compass, and the afk area'''
    # Derive a bounding box for the relevant image 
    bb_l = int(rect[2] * MASK_BOX[0])+1
    bb_t = int(rect[3] * MASK_BOX[1])+1
    bb_r = int(rect[2] * MASK_BOX[2])+1
    bb_b = int(rect[3] * MASK_BOX[3])+1
    
    if VERBOSE:  print("Compass Window Size: " + str(bb_t) +':' + str(bb_b) + ',' + str(bb_l) + ':' + str(bb_r))

    # Fetch screen and convert to usable grayscale numpy array
    haystack = ImageGrab.grab()
    haystack = convert_image(haystack)

    # Derive a compass bounding box on the already cropped main image and crop
    cb_l = int(haystack.shape[1] * COMPASS_BOX[0]) + 1
    cb_t = 0 * COMPASS_BOX[1] + 1
    cb_r = int(haystack.shape[1] *COMPASS_BOX[2]) + 1
    cb_b = int(haystack.shape[0] * COMPASS_BOX[3]) + 1
    compass = haystack[cb_t:cb_b,cb_l:cb_r]

    if VERBOSE:  print("Compass Window Size: " + str(cb_t)+':'+str(cb_b)+','+str(cb_l)+':'+str(cb_r))

    # Derive an afk bounding box on the already cropped main image and crop
    ab_l = int(rect[2] * AFK_BOX[0])+1
    ab_t = int(rect[3] * AFK_BOX[1])+1
    ab_r = int(rect[2] * AFK_BOX[2])+1
    ab_b = int(rect[3] * AFK_BOX[3])+1
    afk = haystack[ab_t:ab_b,ab_l:ab_r]

    if VERBOSE:  print("AFK Window Size: " + str(ab_t)+':'+str(ab_b)+','+str(ab_l)+':'+str(ab_r))

    # Crop main image
    haystack = haystack[bb_t:bb_b,bb_l:bb_r]

    return haystack, compass, afk

def find_needle_in_haystack(haystack, needle):
    if VERBOSE: print(haystack.shape)
    if VERBOSE: print(needle.shape)
    result = cv2.matchTemplate(haystack, needle, cv2.TM_CCOEFF_NORMED)
    (minVal, maxVal, minLoc, maxLoc) = cv2.minMaxLoc(result)
    return (minVal, maxVal, minLoc, maxLoc)

def convert_image(img):
    ''' Converts img to a usable format '''
    img_array = array(img.convert('RGB'))
    img_cv = img_array[:, :, ::-1].copy()  # -1 does RGB -> BGR
    return cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)

def compass_before(comp):
    ''' Capture the compass data before the process '''
    global compass
    # # Crop out the compass [t:b,l:r]
    compass['before'] = comp
    needle = Image.open(compass['image'])
    needle = convert_image(needle)

    (minVal, maxVal, minLoc, maxLoc) = find_needle_in_haystack(comp, needle)

    # Store beforeresults in compass array
    compass['before_results'] = maxLoc

def compass_after(comp):
    ''' Capture the compass data after the process '''
    global compass
    # # Crop out the compass [t:b,l:r]
    compass['after'] = comp
    needle = Image.open(compass['image'])
    needle = convert_image(needle)

    (minVal, maxVal, minLoc, maxLoc) = find_needle_in_haystack(comp, needle)

    # Store after results in compass array
    compass['after_results'] = maxLoc

def check_afk(haystack):
    ''' Check to see if afk status window popped up '''
    global afk
    needle = Image.open(afk['template'])
    needle = convert_image(needle)
    (minVal, maxVal, minLoc, maxLoc) = find_needle_in_haystack(haystack, needle)
    afk['results'] = maxVal * 100
    if VERBOSE:  print(afk['results'])
    if afk['results'] >= afk['threshold']:
        return True
    else:
        return False

def break_afk():
    pydirectinput.keyDown('s')
    sleep(0.1)
    pydirectinput.keyUp('s')
    pydirectinput.keyDown('w')
    sleep(0.1)
    pydirectinput.keyUp('w')

def check_compass_position(comp):
    ''' Returns True if compass position changes, otherwise False '''
    global compass

    compass_after(comp)

    if DEBUG: 
        cv2.imshow('Before', compass['before'])
        cv2.imshow('After', compass['after'])
        key = cv2.waitKey(1)

    weight = abs(compass['before_results'][0] - compass['after_results'][0])
    if VERBOSE: print(f"Compass Before: {compass['before_results'][0]}, Compass After: {compass['after_results'][0]}.")
    if VERBOSE: print(f"Weight: {weight}, Threshold: {compass['threshold']}.")
    if weight < compass['threshold']:
        return False
    else:
        return True

def return_camera_position():
    ''' Moves the mouse up and to the right until the camera position meets threshold '''
    global moved_mouse
    while True:
        _, comp, _ = get_new_haystack()
        compass_position = check_compass_position(comp)
        if compass_position:
            c = GetKeyState(CTRL)
            if c >= 0:
                state_update("Moving mouse...")
                pydirectinput.moveRel(MOUSE_SHIFT[0],MOUSE_SHIFT[1],relative=True)
                moved_mouse[0] += MOUSE_SHIFT[0]
                moved_mouse[1] += MOUSE_SHIFT[1]
            continue
        else:
            break

def take_action(state):
    if state == "hook":
        state_update("Got one!")
        pydirectinput.click()
    elif state == "cast":
        c = GetKeyState(LMB)
        if c < 0:
            pydirectinput.mouseUp()
        else:
            state_update("Casting...")
            duration = uniform(1.7,1.95)
            pydirectinput.mouseDown()
            sleep(duration)
            pydirectinput.mouseUp()
    elif state == "reel bad":
        state_update("Letting off...")
        pydirectinput.mouseUp()
    elif state == "reel good":
        state_update("Reeling it in...")
        c = GetKeyState(LMB)
        if c >= 0:
            pydirectinput.mouseDown()
    elif state == "bobber":
        state_update("Waiting for a bite...")
    elif state == "afk":
        state_update("AFK Detection, doing the jimmy shimmy.")
    elif state == "camera":
        state_update("Camera moved.  Repositioning...")

state_update("Paused.")
x = threading.Thread(target=play_sound)
x.start()

# Make program aware of DPI scaling
user32 = windll.user32
user32.SetProcessDPIAware()

if DEBUG:
    cv2.namedWindow('Main Window')
    cv2.namedWindow('Compass')
    cv2.namedWindow('AFK')
    cv2.namedWindow('Before')
    cv2.namedWindow('After')

while True:
    # Pause Logic
    c = GetKeyState(F9)
    if c < 0:
        if not pause:
            state_update("Paused.")
            pause = True
            x = threading.Thread(target=play_sound)
            x.start()
            sleep(2)
        else:
            state_update("Resuming in 2 seconds...")
            pause = False
            x = threading.Thread(target=play_sound)
            x.start()
            sleep(2)
            # Refresh the stored compass
            first_pass = True
            
    if not pause:
        # window = FindWindow(None, WINDOW_NAME)
        window = GetForegroundWindow()

        # Run if WINDOW_NAME is selected in the foreground
        if GetWindowText(window) == WINDOW_NAME:
            rect = GetWindowRect(window) #L T R B
            if VERBOSE: print("Window Size: " + str(rect))

            # Get the haystack so we can find a needle in it
            haystack_base, comp_base, afk_base = get_new_haystack()
            
            if DEBUG: 
                cv2.imshow('Main Window', haystack_base)
                cv2.imshow('Compass', comp_base)
                cv2.imshow('AFK', afk_base)
                
            # Check AFK status
            afk_status = check_afk(afk_base)
            if VERBOSE: print("AFK Status: " + str(afk_status))

            # Prepopulate compass
            if first_pass:
                compass_before(comp_base)
                first_pass = False

            # Reset the weights list to repopulate it
            weights = []

            # Compare the needle templates against the haystack
            for state in states:
                needle_base = Image.open(state['template'])
                needle_base = convert_image(needle_base)
                (minVal, maxVal, minLoc, maxLoc) = find_needle_in_haystack(haystack_base, needle_base)
                if VERBOSE: print(state['status'] + ": " + str(maxVal) + " (" + str(maxLoc) + ")")
                state['result'] = maxVal * 100
                state['location'] = maxLoc
            
            # Reports which element of the array templates has the highest certainty'''
                status = state['status']
                threshold = state['threshold']
                certainty = state['result']
                if VERBOSE: print(f"{status} {certainty}:{threshold}".format(status,certainty,threshold))
                weights.append(state['result'])

            # Get the highest scoring needle's index number from the array
            max_index = weights.index(max(weights))

            # Action logic
            if states[max_index]['result'] > states[max_index]['threshold']:
                if states[max_index]['status'] == 'reel': compass_before(comp_base)
                if states[max_index]['status'] == 'cast':
                    state_update('Checking to see if compass shifted...')
                    compass_position = check_compass_position(comp_base)
                    if not compass_position:
                        if VERBOSE: print("Camera hasn't moved.")
                    else:
                        if VERBOSE: print("Camera moved.")
                        mouse_status = True
                        return_camera_position()
                    if mouse_status:
                        if VERBOSE: print(f"Mouse moved X: {moved_mouse[0]} and Y: {moved_mouse[1]}.")
                        moved_mouse = [0,0]
                        mouse_status = False
                    if afk_status:
                        state_update('AFK Timer has started.  Moving to break it...')
                        break_afk()

                take_action(states[max_index]['status'])
                if VERBOSE: print(f"Status -> {states[max_index]['status']} {str(states[max_index]['result'])[:4]}:{states[max_index]['threshold']}".format(status,certainty,threshold))
            else:
                if not VERBOSE: state_update("Thinking...")
                if VERBOSE: state_update(f"No Status! Best guess is {states[max_index]['status']} - {str(states[max_index]['result'])[:4]}:{states[max_index]['threshold']}".format(status,certainty,threshold))
        else:
            state_update(f"Select the {WINDOW_NAME} window.")

        if DEBUG:
            key = cv2.waitKey(1)
