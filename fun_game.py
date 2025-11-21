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

import pygame
from pygame.locals import*
import sys 

pygame.init()

while True:
    for event in pygame.event.get():
        if event.type == QUIT:
            pygame.quit()
            sys.exit()


    # Responsible for updating your game window with any changes that have been made within that specific iteration of the game loop. 
    pygame.display.update()