import signal
import sysv_ipc
import sys
import os
from multiprocessing import shared_memory
import time

from stoppable_thread import StoppableThread

myCards = []
pid = -1
messageQueue = ""
sharedMemory = ""
mqThread = ""
gameIsReady = False

def readMq(mq):
    global gameIsReady
    while True:
        try:
            message, t = mq.receive(True, 1)
            value = message.decode()
            if value == "terminate":
                print("Server decided to close the connection.")
                sharedMemory.close()
                os._exit(0)
            if value == "ready":
                gameIsReady = True
            print("Game is talking to me")
        except sysv_ipc.ExistentialError:
            print("MessageQueue has been destroyed, connection has been closed.")
            sharedMemory.close()
            os._exit(1)

def send(msg):
    print("Sending to server : " + msg)
    msg = msg.encode()
    messageQueue.send(msg, True, 2)

def terminate():
    global mqThread
    print("Stopping mqReading thread")
    mqThread.terminate() # Terminate the thread readMq which read the messageQueue as we're going to destroy the mq
    print("Telling the server i want to leave...")
    send("goodbye") # Tells the server i want to leave
    time.sleep(1)
    sharedMemory.close()
    print("SharedMemory closed")
    print("Closing...")
    os._exit(0)

def keyboardInterruptHandler(signal, frame):
   terminate()

def initPlayer():
    global pid
    global messageQueue
    global sharedMemory
    global mqThread
    try:
        pid = int(sys.argv[1])
    except ValueError:
        print("Incorrect pid passed.")
        os.Exit(2)
   
    mq_key = 128+pid
    try:
        messageQueue = sysv_ipc.MessageQueue(mq_key)
    except sysv_ipc.ExistentialError:
        print("Game process do not accept your Player ID.")
        os._exit(1)
    print("Connected to MessageQueue")
    msg = "hello "+str(pid)
    send(msg)
    print("Message '"+msg+"' sended")

    print("Waiting for my cards")
    message, t = messageQueue.receive(True, 1)
    value = message.decode()
    print("Received "+value)
    value = value.split(" ")
    cards_string = value[1].split(",")
    for card in cards_string:
        myCards.append(card)
    shm_key = value[0]
    sharedMemory = shared_memory.SharedMemory(shm_key)
    print("Connected to shared mem")
    mqThread = StoppableThread(target=readMq, args = (messageQueue,))
    mqThread.start()
    print("Thread started")
    signal.signal(signal.SIGINT, keyboardInterruptHandler)

def faireOffre():
    pass

def game():
    while gameIsReady:
        print("Que voulez-vous faire ?")
        action = input()
        match action:
            case 'faireOffre':
                faireOffre()
            case _:
                pass

print("Starting player process")
initPlayer()
print("En attente des joueurs...")
while not gameIsReady:
    pass
print("Game is ready to start!")
nonBlockingInput = StoppableThread(target=game)
nonBlockingInput.start()
#while gameIsReady:
    