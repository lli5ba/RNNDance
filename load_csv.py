

import itertools
import pygame
import pygame.color
import csv
import time

from pygame.color import THECOLORS
from pykinect import nui
from pykinect.nui import JointId
from pykinect.nui import SkeletonTrackingState
from pykinect.nui.structs import TransformSmoothParameters, Vector

WINDOW_SIZE = 800, 480
INPUT_FILENAME = 'predict.csv'

SKELETON_COLORS = [THECOLORS["red"],
                   THECOLORS["blue"],
                   THECOLORS["green"],
                   THECOLORS["orange"],
                   THECOLORS["purple"],
                   THECOLORS["yellow"],
                   THECOLORS["violet"]]

LEFT_ARM = (JointId.ShoulderCenter,
            JointId.ShoulderLeft,
            JointId.ElbowLeft,
            JointId.WristLeft,
            JointId.HandLeft)
RIGHT_ARM = (JointId.ShoulderCenter,
             JointId.ShoulderRight,
             JointId.ElbowRight,
             JointId.WristRight,
             JointId.HandRight)
LEFT_LEG = (JointId.HipCenter,
            JointId.HipLeft,
            JointId.KneeLeft,
            JointId.AnkleLeft,
            JointId.FootLeft)
RIGHT_LEG = (JointId.HipCenter,
             JointId.HipRight,
             JointId.KneeRight,
             JointId.AnkleRight,
             JointId.FootRight)
SPINE = (JointId.HipCenter,
         JointId.Spine,
         JointId.ShoulderCenter)

NECK = (JointId.ShoulderCenter,
         JointId.Head)

SMOOTH_PARAMS_SMOOTHING = 0.7
SMOOTH_PARAMS_CORRECTION = 0.4
SMOOTH_PARAMS_PREDICTION = 0.7
SMOOTH_PARAMS_JITTER_RADIUS = 0.1
SMOOTH_PARAMS_MAX_DEVIATION_RADIUS = 0.1
SMOOTH_PARAMS = TransformSmoothParameters(SMOOTH_PARAMS_SMOOTHING,
                                          SMOOTH_PARAMS_CORRECTION,
                                          SMOOTH_PARAMS_PREDICTION,
                                          SMOOTH_PARAMS_JITTER_RADIUS,
                                          SMOOTH_PARAMS_MAX_DEVIATION_RADIUS)

skeleton_to_depth_image = nui.SkeletonEngine.skeleton_to_depth_image


def draw_skeleton_data(dispInfo, screen, skeleton_position, index, positions, width = 4):
    start = skeleton_position[positions[0]]

    for position in itertools.islice(positions, 1, None):
        next = skeleton_position[position.value]

        curstart = skeleton_to_depth_image(start, dispInfo.current_w, dispInfo.current_h)
        curend = skeleton_to_depth_image(next, dispInfo.current_w, dispInfo.current_h)

        pygame.draw.line(screen, SKELETON_COLORS[index], curstart, curend, width)

        start = next

def draw_skeletons(dispInfo, screen, skeleton_position):
    # clean the screen
    screen.fill(pygame.color.THECOLORS["black"])

    index = 0
    # draw the Head
    HeadPos = skeleton_to_depth_image(skeleton_position[JointId.Head], dispInfo.current_w, dispInfo.current_h)
    draw_skeleton_data(dispInfo, screen, skeleton_position, index, SPINE, 10)
    draw_skeleton_data(dispInfo, screen, skeleton_position, index, NECK, 5)
    pygame.draw.circle(screen, SKELETON_COLORS[index], (int(HeadPos[0]), int(HeadPos[1])), 20, 0)

    # drawing the limbs
    draw_skeleton_data(dispInfo, screen, skeleton_position, index, LEFT_ARM)
    draw_skeleton_data(dispInfo, screen, skeleton_position, index, RIGHT_ARM)
    draw_skeleton_data(dispInfo, screen, skeleton_position, index, LEFT_LEG)
    draw_skeleton_data(dispInfo, screen, skeleton_position, index, RIGHT_LEG)

def main():
    """Initialize and run the game."""
    pygame.init()

    # Initialize PyGame
    screen = pygame.display.set_mode(WINDOW_SIZE, 0, 16)
    pygame.display.set_caption('PyKinect Skeleton')
    screen.fill(pygame.color.THECOLORS["black"])

    # open csv file
    f = open(INPUT_FILENAME, 'rb')
    reader = csv.reader(f)
    header = next(reader)
    x = 1
    # Main game loop
    while True:
        event = pygame.event.poll()
        time.sleep(0.05)
        if event.type == pygame.QUIT:
            f.close()
            break
        else:
            skeleton_positions = []
            for i in range(0, 20):
                line = next(reader)
                x = float(line[3])
                y = float(line[4])
                z = float(line[5])
                w = 1
                skeleton_positions.append(Vector(x, y, z, w))
            draw_skeletons(pygame.display.Info(), screen, skeleton_positions)
            pygame.display.update()
            pass
    f.close()



if __name__ == '__main__':
    main()