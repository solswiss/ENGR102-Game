# By submitting this assignment, I agree to the following:
#   "Aggies do not lie, cheat, or steal, or tolerate those who do."
#   "I have not given or received any unauthorized aid on this assignment."
#
# Names:        Kennady Bunn
#               Milo Sun
#               Ruth Ellen Bowling
#               Andrew Justin
# Section:      511
# Assignment:   Lab 12 - 2 (TEAM)
# Date:         20 November 2025

import pygame, sys
from pygame.locals import*
import random


pygame.init()

# Frames per second #
FPS = pygame.time.Clock()
FPS.tick(60)


# Screen #
info = pygame.display.Info()

# Get current display info
desktop_width = info.current_w
desktop_height = info.current_h

# Create initial screen size
initial_width = int(desktop_width * 0.8)
initial_height = int(desktop_height * 0.8)

# Create a resizable screen
screen = pygame.display.set_mode((initial_width, initial_height), pygame.RESIZABLE)





## Game loop ##
while True:

    # Quitting the game loop
    for event in pygame.event.get():
        if event.type == QUIT:
            pygame.quit()
            sys.exit()


    # Updating game
    pygame.display.update()