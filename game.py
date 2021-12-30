from multiprocessing import Process, Queue
from multiprocessing.process import current_process
import os
import sys

game_is_finished = False

def player(messageQueue, pid):
    current_process().name = "Player-" + str(pid)
    print("PID = " + str(pid) + " and name = " + current_process().name)

if __name__ == '__main__':
    current_process().name = "Game"
    if len(sys.argv) != 2:
        print("Incorrect amount of arguments")
        sys.exit(2)
    number = sys.argv[1]
    try:
        number = int(number)
    except ValueError:
        print("Incorrect number of players.")
        sys.exit(2)
    messageQueue = Queue()
    processes = []
    for i in range(number):
        p = Process(target=player, args=(messageQueue,i+1))
        processes.append(p)
        p.start()
    #while not game_is_finished:
        # things